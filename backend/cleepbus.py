# !/usr/bin/env python
#  -*- coding: utf-8 -*-

import json
import uuid
from distutils.util import strtobool
from cleep.core import CleepExternalBus
from cleep.libs.configs.hostname import Hostname
from cleep import __version__ as VERSION
from cleep.common import MessageRequest, PeerInfos
import cleep.libs.internals.tools as Tools
# pylint: disable=E0402
from .pyrebus import PyreBus

__all__ = ['Cleepbus']

class Cleepbus(CleepExternalBus):
    """
    Cleepbus is the external bus to communicate with other Cleep devices
    """
    MODULE_AUTHOR = 'Cleep'
    MODULE_VERSION = '2.0.2'
    MODULE_CATEGORY = 'APPLICATION'
    MODULE_PRICE = 0
    MODULE_DEPS = []
    MODULE_DESCRIPTION = 'Enables communications between all your Cleep devices through your home network'
    MODULE_LONGDESCRIPTION = 'Application that enables communication between devices'
    MODULE_TAGS = ['bus', 'communication']
    MODULE_COUNTRY = None
    MODULE_URLINFO = 'https://github.com/tangb/cleepmod-cleepbus/'
    MODULE_URLHELP = None
    MODULE_URLSITE = None
    MODULE_URLBUGS = 'https://github.com/tangb/cleepmod-cleepbus/issues'

    MODULE_CONFIG_FILE = 'cleepbus.conf'
    DEFAULT_CONFIG = {
        'uuid': None
    }

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
            self.crash_report
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

    def _configure(self):
        """
        Configure module
        """
        # set device uuid if not setted yet
        self.uuid = self._get_config_field('uuid')
        if self.uuid is None:
            self.logger.debug('Set device uuid')
            self.uuid = str(uuid.uuid4())
            self._set_config_field('uuid', self.uuid)

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
                ssl (string): '0' if ssl disabled, '1' otherwise
                cleepdesktop (string): '1' if device is cleepdesktop, '0' otherwise
                apps (string): list of installed applications
                hwmodel (string): board model
                pcbrevision (string): board pcb revision
                hwmemory (string): board memory amount
                hwaudio (string): '1' if audio on the board
                hwethernet (string): '1' if ethernet on the board
                hwwireless (string): '1' if wireless on the board
                hwrevision (string): board revision
            }

        """
        # get mac addresses
        macs = self.external_bus.get_mac_addresses()

        # get installed modules
        modules = {}
        resp = self.send_command('get_modules', 'inventory', timeout=10.0)
        if not resp.error:
            modules = resp.data

        # get device hardware infos
        hardware = Tools.raspberry_pi_infos()

        # TODO handle here port and ssl when security implemented
        return {
            'uuid': self.uuid,
            'version': VERSION,
            'hostname': self.hostname.get_hostname(),
            'port': '80',
            'macs': json.dumps(macs),
            'ssl': '0',
            'cleepdesktop': '0',
            'apps': json.dumps(list(modules.keys())),
            'hwmodel': '%s' % hardware['model'],
            'pcbrevision': '%s' % hardware['pcbrevision'],
            'hwmemory': '%s' % hardware['memory'],
            'hwaudio': '1' if hardware['audio'] else '0',
            'hwwireless': '1' if hardware['wireless'] else '0',
            'hwethernet': '1' if hardware['ethernet'] else '0',
            'hwrevision': hardware['revision'],
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
        peer_infos.uuid = infos.get('uuid', None)
        peer_infos.hostname = infos.get('hostname', None)
        peer_infos.port = int(infos.get('port', peer_infos.port))
        peer_infos.ssl = bool(strtobool(infos.get('ssl', '%s' % peer_infos.ssl)))
        peer_infos.cleepdesktop = bool(strtobool(infos.get('cleepdesktop', '%s' % peer_infos.cleepdesktop)))
        peer_infos.macs = json.loads(infos.get('macs', '[]'))
        peer_infos.extra = {
            key: value
            for key, value in infos.items()
            if key not in ['uuid', 'hostname', 'port', 'ssl', 'cleepdesktop', 'macs']
        }

        return peer_infos

    def _on_stop(self):
        """
        Stop module
        """
        # stop bus
        self.logger.trace('Stop module requested')
        self._stop_external_bus()

    def _on_process(self):
        """
        Custom process for cleep bus: get new message on external bus
        """
        if self.external_bus.is_running():
            self.external_bus.run_once()

    def _start_external_bus(self):
        """
        Start external bus
        """
        self.external_bus.start(self.get_peer_infos())

    def _stop_external_bus(self):
        """
        Stop external bus
        """
        self.logger.debug('Stop external bus')
        self.external_bus.stop()

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
        return {peer_uuid: peer_infos.to_dict() for peer_uuid, peer_infos in self.peers.items()}

    def _on_message_received(self, peer_id, message):
        """
        Handle received message from external bus

        Args:
            peer_id (string): peer identifier
            message (MessageRequest): message from external bus

        Returns:
            MessageResponse if message is a command
        """
        self.logger.trace('Raw message received on external bus: %s' % message)
        # fill message with peer infos
        peer_infos = self._get_peer_infos_from_peer_id(peer_id)
        if not peer_infos:
            self.logger.warning('Received message from unknown peer "%s", drop it: %s' % (peer_id, message))
            return None
        message.peer_infos = peer_infos
        self.logger.debug('Message received on external bus: %s' % message)

        if message.is_command():
            # send command and return response
            return self.send_command(
                message.command,
                message.to,
                message.params,
                (message.timeout - 2.0) if message.timeout is not None and message.timeout >= 5.0 else 5.0
            )

        # send event
        self.send_event(message.event, message.params, to=message.to)
        return None

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
        self.logger.info('Peer %s connected: %s' % (peer_id, str(peer_infos)))

    def _on_peer_disconnected(self, peer_id):
        """
        Device is disconnected
        """
        self.logger.debug('Peer %s disconnected' % peer_id)
        peer_infos = self._get_peer_infos_from_peer_id(peer_id)
        if not peer_infos:
            self.logger.warning('Peer "%s" is unknown' % peer_id)
            return

        peer_infos.online = False

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
        self.logger.debug('Received event %s' % event)

        # network events to start or stop bus properly and avoid invalid ip address in pyre bus (workaround)
        if event['event'] == 'network.status.up' and not self.external_bus.is_running():
            # start external bus
            self._start_external_bus()
            return

        if event['event'] == 'network.status.down' and self.external_bus.is_running():
            # stop external bus
            self.logger.trace('Stop requested by network down event')
            self._stop_external_bus()
            return

        if (not event['startup'] if 'startup' in event else True) and (event['propagate'] if 'propagate' in event else False):
            # broadcast events to external bus that are allowed to go outside of the device
            message = MessageRequest()
            message.event = event.get('event')
            message.params = event.get('params')
            message.sender = event.get('sender')
            self.external_bus.send_message(message)

        else:
            # drop current event
            self.logger.debug('Received event %s dropped' % event['event'])

    def _send_command_to_peer(self, command, to, peer_uuid, params=None, timeout=5.0, manual_response=None):
        """
        Send command to specified peer

        Args:
            command (string): command name
            to (string): module name to send command to
            peer_uuid (string): peer uuid to send command to
            params (dict): command parameters. Default None
            timeout (float): command timeout. Should be greater than 3.0 seconds. Default 5.0
            manual_response (function): function to call to send command response
        """
        # check parameters
        self._check_parameters([
            {'name': 'command', 'type': str, 'value': command},
            {'name': 'to', 'type': str, 'value': to},
            {'name': 'peer_uuid', 'type': str, 'value': peer_uuid},
            {
                'name': 'peer_uuid',
                'type': str,
                'value': peer_uuid,
                'validator': lambda val: val in self.peers,
                'message': 'Specified peer "%s" does not exist' % peer_uuid
            },
            {
                'name': 'peer_uuid',
                'type': str,
                'value': peer_uuid,
                'validator': lambda val: self.peers[val].online,
                'message': 'Specified peer "%s" is not online' % peer_uuid
            },
            {'name': 'params', 'type': dict, 'value': params, 'none': True},
            {
                'name': 'timeout',
                'type': float,
                'value': timeout,
                'validator': lambda val: val > 3.0,
                'message': 'Timeout must be greater than 3.0 seconds',
            },
        ])

        # prepare message
        message = MessageRequest()
        message.to = to
        message.command = command
        message.params = params
        message.peer_infos = self.peers[peer_uuid]
        message.timeout = timeout

        self.external_bus.send_message(message, timeout, manual_response)

    def _send_event_to_peer(self, event_name, peer_uuid, params=None):
        """
        Send event to specified peer through external bus implementation

        Args:
            event_name (string): event name
            peer_uuid (string): peer uuid
            params (dict): event parameters. Default None
        """
        # prepare message
        message = MessageRequest()
        message.event = event_name
        message.params = params
        message.peer_infos = self.peers[peer_uuid]

        self.external_bus.send_message(message, peer_uuid, params=None)

