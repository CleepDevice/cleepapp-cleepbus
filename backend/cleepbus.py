# !/usr/bin/env python
#  -*- coding: utf-8 -*-

import json
import time
import uuid
from collections import deque
from cleep.core import CleepExternalBus
from cleep.libs.configs.hostname import Hostname
from cleep import __version__ as VERSION
from cleep.common import MessageRequest, MessageResponse, PeerInfos
import cleep.libs.internals.tools as Tools

# pylint: disable=E0402
from .pyrebus import PyreBus

__all__ = ["Cleepbus"]


class Cleepbus(CleepExternalBus):
    """
    Cleepbus is the external bus to communicate with other Cleep devices
    """

    MODULE_AUTHOR = "Cleep"
    MODULE_VERSION = "2.3.3"
    MODULE_CATEGORY = "APPLICATION"
    MODULE_DEPS = []
    MODULE_DESCRIPTION = "Enables communications between all your Cleep devices through your home network"
    MODULE_LONGDESCRIPTION = "Application that enables communication between devices"
    MODULE_TAGS = ["bus", "communication"]
    MODULE_URLINFO = "https://github.com/CleepDevice/cleepapp-cleepbus/"
    MODULE_URLHELP = None
    MODULE_URLSITE = None
    MODULE_URLBUGS = "https://github.com/CleepDevice/cleepapp-cleepbus/issues"

    MODULE_CONFIG_FILE = "cleepbus.conf"
    DEFAULT_CONFIG = {"uuid": None}

    # Timeout for inventory get_modules when building peer headers at bus start
    PEER_INFOS_MODULES_TIMEOUT = 3.0
    # Avoid restart storms when network flaps or $TERM repeats
    RESTART_BACKOFF = 30.0
    # Ring buffer of recent bus activity for the config/debug page
    BUS_LOG_SIZE = 20

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Args:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): flag to set debug level to logger
        """
        CleepExternalBus.__init__(self, bootstrap, debug_enabled)

        # members
        self.external_bus = PyreBus(
            self._on_message_received,
            self._on_peer_connected,
            self._on_peer_disconnected,
            Cleepbus._decode_peer_infos,
            debug_enabled,
            self.crash_report,
        )
        # peers list::
        #   {
        #       peer uuid (string): {
        #           peer_id (string): current peer identifier
        #           peer_ip (string): current peer ip
        #           ... peer infos from received infos
        #       },
        #       ...
        #   }
        self.peers = {}
        self.hostname = Hostname(self.cleep_filesystem)
        self.uuid = None
        self.__last_restart_attempt = 0.0
        self.__restart_pending = False
        # Recent activity (newest last). Entries::
        #   {ts, kind, summary, detail}
        self.__bus_log = deque(maxlen=self.BUS_LOG_SIZE)

    def _configure(self):
        """
        Configure module
        """
        # set device uuid if not setted yet
        self.uuid = self._get_config_field("uuid")
        if self.uuid is None:
            self.logger.debug("Set device uuid")
            self.uuid = str(uuid.uuid4())
            self._set_config_field("uuid", self.uuid)

    def get_peer_infos(self):
        """
        Current peer infos to set at bus init (values must be in string format)

        Returns:
            dict: infos values (only string supported)::

            {
                uuid (string): device uuid
                version (string): installed Cleep version
                hostname (string): device hostname
                port (string): device http port
                macs (string): list of mac addresses
                ssl (string): "0" if ssl disabled, "1" otherwise
                auth (str): "1" if auth enabled, "0" otherwise
                cleepdesktop (string): "1" if device is cleepdesktop, "0" otherwise
                apps (string): list of installed applications
                hwmodel (string): board model
                pcbrevision (string): board pcb revision
                hwmemory (string): board memory amount
                hwaudio (string): "1" if audio on the board
                hwethernet (string): "1" if ethernet on the board
                hwwireless (string): "1" if wireless on the board
                hwrevision (string): board revision
            }

        """
        # get mac addresses
        macs = self.external_bus.get_mac_addresses()

        # get installed modules
        modules = {}
        resp = self.send_command(
            "get_modules", "inventory", timeout=self.PEER_INFOS_MODULES_TIMEOUT
        )
        if not resp.error:
            modules = resp.data

        # get device hardware infos
        hardware = Tools.raspberry_pi_infos()

        return {
            "uuid": self.uuid,
            "version": VERSION,
            "hostname": self.hostname.get_hostname(),
            "port": str(self.rpc_config.get("port", 80)),
            "ssl": "1" if self.rpc_config.get("ssl") else "0",
            "auth": "1" if self.rpc_config.get("auth") else "0",
            "cleepdesktop": "0",
            "apps": json.dumps(list(modules.keys())),
            "macs": json.dumps(macs),
            "hwmodel": f"{hardware['model']}",
            "pcbrevision": f"{hardware['pcbrevision']}",
            "hwmemory": f"{hardware['memory']}",
            "hwaudio": "1" if hardware["audio"] else "0",
            "hwwireless": "1" if hardware["wireless"] else "0",
            "hwethernet": "1" if hardware["ethernet"] else "0",
            "hwrevision": f"{hardware['revision']}",
        }

    @staticmethod
    def _decode_peer_infos(infos):
        """
        Decode peer infos

        It is used to transform peer connection infos to appropriate python type (all values in infos are string).

        Args:
            infos (dict): dict of decoded values

        Returns:
            PeerInfos: peer informations
        """
        peer_infos = PeerInfos()
        peer_infos.uuid = infos.get("uuid", None)
        peer_infos.hostname = infos.get("hostname", None)
        peer_infos.port = int(infos.get("port", peer_infos.port))
        peer_infos.ssl = Cleepbus._as_bool(infos.get("ssl"), peer_infos.ssl)
        peer_infos.cleepdesktop = Cleepbus._as_bool(
            infos.get("cleepdesktop"), peer_infos.cleepdesktop
        )
        peer_infos.macs = json.loads(infos.get("macs", "[]"))
        peer_infos.extra = {
            key: value
            for key, value in infos.items()
            if key not in ["uuid", "hostname", "port", "ssl", "cleepdesktop", "macs"]
        }

        return peer_infos

    @staticmethod
    def _as_bool(value, default=False):
        """
        Coerce peer-header values to bool (ZRE headers are strings).

        Replaces the former ``str2bool`` dependency. Accepts bool/int and common
        string forms (``1``/``0``, ``true``/``false``, ``yes``/``no``, …).
        """
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in ("1", "true", "t", "yes", "y", "on"):
            return True
        if text in ("0", "false", "f", "no", "n", "off", ""):
            return False
        return default

    def _on_stop(self):
        """
        Stop module
        """
        # stop bus
        self.logger.trace("Stop module requested")
        self._stop_external_bus(clear_restart=True)

    def _on_process(self):
        """
        Custom process for cleep bus: get new message on external bus.

        Must stay short: BusClient pulls internal messages after this call.
        If the pyre node signals death ($TERM / beacon gone), restart discovery.
        """
        if self.external_bus.is_running():
            try:
                still_running = self.external_bus.run_once()
            except Exception:
                self.logger.exception(
                    "External bus poll failed unexpectedly, restarting discovery"
                )
                still_running = False

            if not still_running:
                self.logger.warning(
                    "External bus stopped unexpectedly (discovery dead), restarting"
                )
                self._log_bus(
                    "system",
                    "Discovery stopped unexpectedly ($TERM / empty / poll fail)",
                )
                self.__restart_pending = True
                try:
                    # Always tear down so is_running() is False (no silent zombie)
                    self._stop_external_bus()
                except Exception:
                    self.logger.exception(
                        "Error while stopping dead external bus before restart"
                    )

        if self.__restart_pending:
            self._restart_external_bus()

    def _start_external_bus(self):
        """
        Start external bus
        """
        self.external_bus.start(self.get_peer_infos())
        self.__restart_pending = False
        endpoint = getattr(self.external_bus, "endpoint", None)
        self._log_bus("system", "External bus started", endpoint)

    def _stop_external_bus(self, clear_restart=False):
        """
        Stop external bus

        Args:
            clear_restart (bool): if True, cancel a pending auto-restart (network down)
        """
        self.logger.debug("Stop external bus")
        was_running = self.external_bus.is_running()
        self.external_bus.stop()
        if clear_restart:
            self.__restart_pending = False
        if was_running:
            self._log_bus("system", "External bus stopped")

    def _restart_external_bus(self):
        """
        Start the external bus again after an unexpected death or IP change (with backoff).
        """
        self.__restart_pending = True
        now = time.time()
        if now - self.__last_restart_attempt < self.RESTART_BACKOFF:
            self.logger.debug(
                "External bus restart deferred (backoff %.0fs)", self.RESTART_BACKOFF
            )
            return

        self.__last_restart_attempt = now
        self.logger.info("Restarting external bus")
        self._log_bus("system", "Restarting external bus")
        try:
            if self.external_bus.is_running():
                self._stop_external_bus()
        except Exception:
            self.logger.exception("Error while stopping external bus before restart")

        try:
            self._start_external_bus()
        except Exception:
            self.logger.exception("Error while restarting external bus")
            self._log_bus("system", "External bus restart failed")
            # Keep pending so the next process cycle retries after backoff
            self.__restart_pending = True

    def _find_existing_peer(self, peer_infos):
        """
        Based on specified peer_infos content mac adresses) this function tries to find an exiting peer.

        Args:
            peer_infos (PeerInfos): peer informations

        Returns:
            string: peer uuid if existing peer exists
        """
        for peer_uuid, infos in self.peers.items():
            if len(set(infos.macs) & set(peer_infos.macs)) != 0:
                # some mac addresses are identicals, we can consider it is the same peer
                return peer_uuid

        return None

    def get_peers(self):
        """
        Return all Cleep peers found on the network

        Returns:
            dict: list of peers::

            {
                peer uuid (string): {
                    peer infos formatted fields
                    online (bool): True if peer is online
                    peer_id (string): peer id. Volatile, renewed after device connection
                },
                ...
            }

        """
        return {
            peer_uuid: peer_infos.to_dict()
            for peer_uuid, peer_infos in self.peers.items()
        }

    def _log_bus(self, kind, summary, detail=None):
        """
        Append an entry to the recent bus activity log (config page).

        Args:
            kind (str): ``in`` (inbound), ``out`` (outbound), or ``system``
            summary (str): short human-readable line
            detail (str|None): optional extra context (truncated)
        """
        if detail is not None:
            detail = str(detail)
            if len(detail) > 240:
                detail = detail[:237] + "..."
        self.__bus_log.append(
            {
                "ts": time.time(),
                "kind": kind,
                "summary": str(summary)[:200],
                "detail": detail,
            }
        )

    def get_bus_status(self):
        """
        Return Pyre connection status and recent bus activity for the config UI.

        Returns:
            dict::

            {
                running (bool): True if external bus is up
                restart_pending (bool): True if auto-restart is scheduled
                endpoint (str|None): ZRE TCP endpoint (tcp://ip:port)
                uuid (str): this device uuid
                hostname (str): this device hostname
                peers_online (int): online peers count
                peers_total (int): known peers count
                peers (list): compact peer rows
                    [{uuid, hostname, ip, online, cleepdesktop}, ...]
                messages (list): last BUS_LOG_SIZE activity entries, newest first
                    [{ts, kind, summary, detail}, ...]
            }
        """
        peers_rows = []
        online = 0
        for peer_uuid, peer_infos in self.peers.items():
            row = {
                "uuid": peer_uuid,
                "hostname": peer_infos.hostname,
                "ip": peer_infos.ip,
                "online": bool(peer_infos.online),
                "cleepdesktop": bool(peer_infos.cleepdesktop),
            }
            peers_rows.append(row)
            if peer_infos.online:
                online += 1
        peers_rows.sort(key=lambda p: (not p["online"], p["hostname"] or ""))

        return {
            "running": self.external_bus.is_running(),
            "restart_pending": self.__restart_pending,
            "endpoint": getattr(self.external_bus, "endpoint", None),
            "uuid": self.uuid,
            "hostname": self.hostname.get_hostname(),
            "peers_online": online,
            "peers_total": len(self.peers),
            "peers": peers_rows,
            "messages": list(reversed(self.__bus_log)),
        }

    def _on_message_received(self, peer_id, message):
        """
        Handle received message from external bus

        Args:
            peer_id (string): peer identifier
            message (MessageRequest): message from external bus

        Returns:
            MessageResponse if message is a command executed synchronously, else None.
            Inbound commands are executed asynchronously to avoid blocking the
            module/_on_process path; response is sent back to the peer by the task.
        """
        self.logger.trace("Raw message received on external bus: %s", message)
        # fill message with peer infos
        peer_infos = self._get_peer_infos_from_peer_id(peer_id)
        if not peer_infos:
            self.logger.warning(
                'Received message from unknown peer "%s", drop it: %s', peer_id, message
            )
            self._log_bus("in", f"Dropped message from unknown peer {peer_id}")
            return None
        message.peer_infos = peer_infos
        self.logger.debug("Message received on external bus: %s", message)
        peer_label = peer_infos.hostname or peer_infos.uuid or peer_id
        if message.is_command():
            self._log_bus(
                "in",
                f"CMD {message.command} from {peer_label}",
                f"to={message.to}",
            )
        else:
            self._log_bus(
                "in",
                f"EVT {message.event} from {peer_label}",
            )

        if message.is_command():
            # Offload to a background task: send_command is blocking and would
            # starve the BusClient loop / ZRE poll if run inline.
            task = self.task_factory.create_task(
                None, self._execute_inbound_command, task_args=[message]
            )
            task.start()
            return None

        # send event
        self.send_event(message.event, message.params, to=message.to)
        return None

    def _inbound_command_timeout(self, message):
        """
        Compute internal timeout for an inbound peer command.

        Args:
            message (MessageRequest): inbound command

        Returns:
            float: timeout in seconds
        """
        if message.timeout is not None and message.timeout >= 5.0:
            return message.timeout - 2.0
        return 5.0

    def _execute_inbound_command(self, message):
        """
        Execute inbound peer command and whisper the response back.

        Args:
            message (MessageRequest): inbound command (peer_infos already set)
        """
        try:
            response = self.send_command(
                message.command,
                message.to,
                message.params,
                self._inbound_command_timeout(message),
            )
            if not isinstance(response, MessageResponse):
                # Robustness: wrap unexpected return types
                wrapped = MessageResponse()
                if isinstance(response, dict):
                    wrapped.fill_from_dict(response)
                else:
                    wrapped.error = True
                    wrapped.message = "Invalid command response type"
                response = wrapped

            self.external_bus._send_command_response_to_peer(message, response)
        except Exception:
            self.logger.exception(
                'Failed to execute inbound peer command "%s" for peer %s:',
                message.command,
                message.peer_infos.uuid if message.peer_infos else None,
            )
            try:
                error_response = MessageResponse(
                    error=True, message="Inbound command execution failed"
                )
                self.external_bus._send_command_response_to_peer(
                    message, error_response
                )
            except Exception:
                self.logger.exception(
                    "Unable to send inbound command error response to peer"
                )

    def _on_peer_connected(self, peer_id, peer_infos):
        """
        Device is connected

        Args:
            peer_id (string): peer identifier
            peer_infos (PeerInfos): peer informations (ip, port, ssl...)
        """
        # find existing peer
        existing_peer_uuid = self._find_existing_peer(peer_infos)

        if existing_peer_uuid:
            # remove existing one
            del self.peers[existing_peer_uuid]

        # save new one
        peer_infos.online = True
        self.peers[peer_infos.uuid] = peer_infos
        self.logger.debug("Peer %s connected: %s", peer_id, str(peer_infos))
        self._log_bus(
            "system",
            f"Peer connected: {peer_infos.hostname or peer_infos.uuid}",
            f"ip={peer_infos.ip} ident={peer_id}",
        )

    def _on_peer_disconnected(self, peer_id):
        """
        Device is disconnected
        """
        self.logger.debug("Peer %s disconnected", peer_id)
        peer_infos = self._get_peer_infos_from_peer_id(peer_id)
        if not peer_infos:
            self.logger.warning('Peer "%s" is unknown', peer_id)
            self._log_bus("system", f"Unknown peer disconnected: {peer_id}")
            return

        peer_infos.online = False
        self._log_bus(
            "system",
            f"Peer disconnected: {peer_infos.hostname or peer_infos.uuid}",
            f"ident={peer_id}",
        )

    def _get_peer_infos_from_peer_id(self, peer_id):
        """
        Search in peers dict for peer_id and returns its informations

        Args:
            peer_id (string): peer identifier

        Returns:
            dict: peer informations or None
        """
        filtered = [peer for peer in self.peers.values() if peer.ident == peer_id]
        return filtered[0] if len(filtered) > 0 else None

    def on_event(self, event):
        """
        Automatically broadcast received events from internal bus to external bus

        Args:
            event (MessageRequest): event data
        """
        # handle received event and transfer it to external buf if necessary
        self.logger.debug("Received event %s", event)

        # network events to start or stop bus properly and avoid invalid ip address in pyre bus
        if event["event"] == "network.status.up" and not self.external_bus.is_running():
            self._log_bus("system", "Network up — starting external bus")
            self._start_external_bus()
            return

        if event["event"] == "network.status.down" and self.external_bus.is_running():
            self.logger.trace("Stop requested by network down event")
            self._log_bus("system", "Network down — stopping external bus")
            self._stop_external_bus(clear_restart=True)
            return

        if event["event"] == "network.status.update":
            # IP / interface change without full down/up: rebind discovery
            params = event.get("params") or {}
            new_ip = params.get("ipaddress")
            if self.external_bus.is_running():
                endpoint = getattr(self.external_bus, "endpoint", None) or ""
                if new_ip and endpoint and new_ip not in endpoint:
                    self.logger.info(
                        "Network IP changed to %s (endpoint was %s), restarting external bus",
                        new_ip,
                        endpoint,
                    )
                    self._log_bus(
                        "system",
                        f"IP changed to {new_ip} — restarting bus",
                        f"was {endpoint}",
                    )
                    self._restart_external_bus()
            elif new_ip and not self.__restart_pending:
                self.logger.info(
                    "Network updated with IP %s while bus stopped, starting external bus",
                    new_ip,
                )
                self._log_bus("system", f"Network updated ({new_ip}) — starting bus")
                self._start_external_bus()
            return

        if (not event["startup"] if "startup" in event else True) and (
            event["propagate"] if "propagate" in event else False
        ):
            # broadcast events to external bus that are allowed to go outside of the device
            message = MessageRequest()
            message.event = event.get("event")
            message.params = event.get("params")
            message.sender = event.get("sender")
            event_name = event.get("event") or "?"
            sender = event.get("sender") or "?"
            self._log_bus("out", f"EVT {event_name} (broadcast)", f"sender={sender}")
            self.external_bus.send_message(message)

        else:
            # drop current event
            self.logger.debug("Received event %s dropped", event["event"])

    def _send_command_to_peer(
        self, command, to, peer_uuid, params=None, timeout=8.0, manual_response=None
    ):
        """
        Send command to specified peer

        Args:
            command (string): command name
            to (string): module name to send command to
            peer_uuid (string): peer uuid to send command to
            params (dict): command parameters. Default None
            timeout (float): command timeout. Should be greater than 3.0 seconds. Default 8.0
            manual_response (function): function to call after command response was received
        """
        # check parameters
        self._check_parameters(
            [
                {"name": "command", "type": str, "value": command},
                {"name": "to", "type": str, "value": to},
                {"name": "peer_uuid", "type": str, "value": peer_uuid},
                {
                    "name": "peer_uuid",
                    "type": str,
                    "value": peer_uuid,
                    "validator": lambda val: val in self.peers,
                    "message": f'Specified peer "{peer_uuid}" does not exist',
                },
                {
                    "name": "peer_uuid",
                    "type": str,
                    "value": peer_uuid,
                    "validator": lambda val: self.peers[val].online,
                    "message": f'Specified peer "{peer_uuid}" is not online',
                },
                {"name": "params", "type": dict, "value": params, "none": True},
                {
                    "name": "timeout",
                    "type": float,
                    "value": timeout,
                    "validator": lambda val: val > 3.0,
                    "message": "Timeout must be greater than 3.0 seconds",
                },
            ]
        )

        # prepare message
        message = MessageRequest()
        message.to = to
        message.command = command
        message.params = params
        message.peer_infos = self.peers[peer_uuid]
        message.timeout = timeout

        peer_label = message.peer_infos.hostname or peer_uuid
        self._log_bus("out", f"CMD {command} to {peer_label}", f"module={to}")
        self.external_bus.send_message(message, timeout, manual_response)

    def _send_event_to_peer(self, event_name, peer_uuid, params=None):
        """
        Send event to specified peer through external bus implementation

        Args:
            event_name (string): event name
            peer_uuid (string): peer uuid
            params (dict): event parameters. Default None
        """
        self._check_parameters(
            [
                {"name": "event_name", "type": str, "value": event_name},
                {"name": "peer_uuid", "type": str, "value": peer_uuid},
                {
                    "name": "peer_uuid",
                    "type": str,
                    "value": peer_uuid,
                    "validator": lambda val: val in self.peers,
                    "message": f'Specified peer "{peer_uuid}" does not exist',
                },
                {
                    "name": "peer_uuid",
                    "type": str,
                    "value": peer_uuid,
                    "validator": lambda val: self.peers[val].online,
                    "message": f'Specified peer "{peer_uuid}" is not online',
                },
                {"name": "params", "type": dict, "value": params, "none": True},
            ]
        )

        # prepare message
        message = MessageRequest()
        message.event = event_name
        message.params = params
        message.peer_infos = self.peers[peer_uuid]

        peer_label = message.peer_infos.hostname or peer_uuid
        self._log_bus("out", f"EVT {event_name} to {peer_label}")
        self.external_bus.send_message(message)
