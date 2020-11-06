# !/usr/bin/env python
#  -*- coding: utf-8 -*-

import json
import uuid
from distutils.util import strtobool
from cleep.core import CleepModule
from cleep.libs.configs.hostname import Hostname
from cleep import __version__ as VERSION
import cleep.libs.internals.tools as Tools
from pyrebus import PyreBus

__all__ = ['Cleepbus']

class Cleepbus(CleepModule):
    """
    Cleepbus is the external bus to communicate with other Cleep devices
    """
    MODULE_AUTHOR = 'Cleep'
    MODULE_VERSION = '1.1.1'
    MODULE_CATEGORY = 'APPLICATION'
    MODULE_PRICE = 0
    MODULE_DEPS = []
    MODULE_DESCRIPTION = 'Enables communications between all your Cleep devices through your home network'
    MODULE_LONGDESCRIPTION = 'Application that enables communication between devices'
    MODULE_TAGS = ['bus', 'communication']
    MODULE_COUNTRY = None
    MODULE_URLINFO = 'https://github.com/tangb/cleepmod-cleepbus/wiki/CleepBus-module'
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
        CleepModule.__init__(self, bootstrap, debug_enabled)

        # members
        self.external_bus = PyreBus(
            self._on_message_received,
            self._on_peer_connected,
            self._on_peer_disconnected,
            self._decode_bus_headers,
            debug_enabled,
            self.crash_report
        )
        self.devices = {}
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

    def get_bus_headers(self):
        """
        Headers to send at bus connection (values must be in string format)

        Return:
            dict: dict of headers (only string supported)
        """
        # get mac addresses
        macs = self.external_bus.get_mac_addresses()

        # get installed modules
        modules = {}
        try:
            resp = self.send_command('get_modules', 'inventory', timeout=10.0)
            if not resp['error']:
                modules = resp['data']
        except Exception:
            self.logger.exception('Error occured while getting installed modules')

        # get device hardware infos
        hardware = Tools.raspberry_pi_infos()

        # TODO handle port and ssl when security implemented
        headers = {
            'uuid': self.uuid,
            'version': VERSION,
            'hostname': self.hostname.get_hostname(),
            'port': '80',
            'macs': json.dumps(macs),
            'ssl': '0',
            'cleepdesktop': '0',
            'apps': ','.join(modules.keys()),
            'hwmodel': '%s' % hardware['model'],
            'pcbrevision': '%s' % hardware['pcbrevision'],
            'hwmemory': '%s' % hardware['memory'],
            'hwaudio': '1' if hardware['audio'] else '0',
            'hwwireless': '1' if hardware['wireless'] else '0',
            'hwethernet': '1' if hardware['ethernet'] else '0',
            'hwrevision': hardware['revision'],
        }

        return headers

    def _decode_bus_headers(self, headers):
        """
        Decode bus headers fields

        Args:
            headers (dict): dict of values as returned by bus

        Return:
            dict: dict with parsed values
        """
        if 'port' in headers:
            headers['port'] = int(headers['port'])
        if 'ssl' in headers:
            headers['ssl'] = bool(strtobool(headers['ssl']))
        if 'cleepdesktop' in headers:
            headers['cleepdesktop'] = bool(strtobool(headers['cleepdesktop']))
        if 'macs' in headers:
            headers['macs'] = json.loads(headers['macs'])

        return headers

    def _on_stop(self):
        """
        Stop module
        """
        # stop bus
        self.logger.trace('Stop module requested')
        self.__stop_external_bus()

    def _custom_process(self):
        """
        Custom process for cleep bus: get new message on external bus
        """
        if self.external_bus.is_running():
            self.external_bus.run_once()

    def __start_external_bus(self):
        """
        Start external bus
        """
        self.external_bus.start(self.get_bus_headers())

    def __stop_external_bus(self):
        """
        Stop external bus
        """
        self.logger.debug('Stop external bus')
        self.external_bus.stop()

    def get_network_devices(self):
        """
        Return all Cleep devices found on the network

        Returns:
            dict: devices
        """
        # TODO return list of online devices
        return self.devices

    def _on_message_received(self, message):
        """
        Handle received message from external bus

        Args:
            message (ExternalBusMessage): external bus message instance
        """
        self.logger.debug('Message received on external bus: %s' % message)

        # broadcast event to all modules
        peer_infos = {
            'macs': message.peer_macs,
            'ip': message.peer_ip,
            'hostname': message.peer_hostname,
            'device_id': message.device_id
        }
        self.send_external_event(message.event, message.params, peer_infos)

    def _on_peer_connected(self, peer_id, infos):
        """
        Device is connected

        Args:
            peer_id (string): peer identifier
            infos (dict): device informations (ip, port, ssl...)
        """
        self.logger.debug('Peer %s connected: %s' % (peer_id, infos))

    def _on_peer_disconnected(self, peer_id):
        """
        Device is disconnected
        """
        self.logger.debug('Peer %s disconnected' % peer_id)

    def event_received(self, event):
        """
        Automatically broadcast received events to external bus

        Args:
            event (MessageRequest): event data
        """
        # handle received event and transfer it to external buf if necessary
        self.logger.debug('Received event %s' % event)

        # network events to start or stop bus properly and avoid invalid ip address in pyre bus (workaround)
        if event['event'] == 'network.status.up' and not self.external_bus.is_running():
            # start external bus
            self.__start_external_bus()
            return

        if event['event'] == 'network.status.down' and self.external_bus.is_running():
            # stop external bus
            self.logger.trace('Stop requested by network down event')
            self.__stop_external_bus()
            return

        if ('startup' in event and not event['startup']) and ('core_event' in event and not event['core_event']):
            # broadcast non system events to external bus (based on EVENT_SYSTEM flag)
            self.external_bus.broadcast_event(event['event'], event['params'], event['device_id'])

        else:
            # drop current event
            self.logger.debug('Received event %s dropped' % event['event'])


