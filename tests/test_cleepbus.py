import unittest
import logging
import sys
import json
import copy
sys.path.append('../')
from backend.cleepbus import Cleepbus
from cleep.exception import InvalidParameter, MissingParameter, CommandError, Unauthorized
from cleep.libs.internals.externalbus import ExternalBusMessage
from cleep.libs.tests import session
import os
import time
from mock import Mock, patch, ANY

mock_hostname = Mock()
mock_pyrebus = Mock()
mock_tools = Mock()

@patch('backend.cleepbus.Hostname', mock_hostname)
@patch('backend.cleepbus.VERSION', '6.6.6')
@patch('backend.cleepbus.PyreBus', mock_pyrebus)
@patch('backend.cleepbus.Tools', mock_tools)
class TestCleepbus(unittest.TestCase):

    GET_MODULES = {
        'mod1': {},
        'mod2': {},
        'mod3': {},
    }
    GET_RASPBERRY_INFOS = {
        'date': '2020',
        'model': 'B',
        'pcbrevision': '1.2',
        'ethernet': False,
        'wireless': True,
        'audio': False,
        'gpiopins': 666,
        'memory': '1 GB',
        'notes': 'no notes',
        'revision': 'a020d3',
    }

    def setUp(self):
        self.session = session.TestSession(self)
        logging.basicConfig(level=logging.DEBUG, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')

        mock_hostname.return_value.get_hostname.return_value = 'testhostname'
        mock_tools.raspberry_pi_infos.return_value = self.GET_RASPBERRY_INFOS

    def tearDown(self):
        self.session.clean()
        mock_hostname.reset_mock()
        mock_pyrebus.reset_mock()

    def init_session(self, start_module=True):
        self.module = self.session.setup(Cleepbus)
        if start_module:
            self.session.start_module(self.module)
            self.session.add_mock_command(self.session.make_mock_command('get_modules', self.GET_MODULES))

    def make_header(self):
        return {
            'ssl': '0',
            'hwmodel': self.GET_RASPBERRY_INFOS['model'],
            'macs': '["00:00:00:00:00:00"]',
            'hwethernet': '1' if self.GET_RASPBERRY_INFOS['ethernet'] else '0',
            'hwwireless': '1' if self.GET_RASPBERRY_INFOS['wireless'] else '0',
            'hwaudio': '1' if self.GET_RASPBERRY_INFOS['audio'] else '0',
            'hwmemory': self.GET_RASPBERRY_INFOS['memory'],
            'pcbrevision': self.GET_RASPBERRY_INFOS['pcbrevision'],
            'hwrevision': self.GET_RASPBERRY_INFOS['revision'],
            'version': '6.6.6',
            'apps': json.dumps(list(self.GET_MODULES.keys())),
            'port': '80',
            'hostname': 'testhostname',
            'uuid': '123-456-789',
            'cleepdesktop': '0',
        }

    def test_configure(self):
        self.init_session(False)
        self.module._get_config_field = Mock(return_value=None)
        self.module._set_config_field = Mock()

        self.session.start_module(self.module)
        
        mock_pyrebus.assert_called_with(
            self.module._on_message_received,
            self.module._on_peer_connected,
            self.module._on_peer_disconnected,
            self.module._decode_bus_header,
            ANY,
            ANY
        )
        self.module._set_config_field.assert_called_with('uuid', self.module.uuid)

    def test_configure_no_uuid_update(self):
        self.init_session(False)
        self.module._get_config_field = Mock(return_value='123-456-789')
        self.module._set_config_field = Mock()

        self.session.start_module(self.module)
        
        mock_pyrebus.assert_called_with(
            self.module._on_message_received,
            self.module._on_peer_connected,
            self.module._on_peer_disconnected,
            self.module._decode_bus_header,
            ANY,
            ANY
        )
        self.assertFalse(self.module._set_config_field.called)

    def test_get_bus_header(self):
        self.init_session()
        mock_pyrebus.return_value.get_mac_addresses.return_value = ['00:00:00:00:00:00']

        header = self.module.get_bus_header()
        logging.debug('Header: %s' % header)

        self.assertDictEqual(header, {
            'ssl': '0',
            'hwmodel': self.GET_RASPBERRY_INFOS['model'],
            'macs': '["00:00:00:00:00:00"]',
            'hwethernet': '1' if self.GET_RASPBERRY_INFOS['ethernet'] else '0',
            'hwwireless': '1' if self.GET_RASPBERRY_INFOS['wireless'] else '0',
            'hwaudio': '1' if self.GET_RASPBERRY_INFOS['audio'] else '0',
            'hwmemory': self.GET_RASPBERRY_INFOS['memory'],
            'pcbrevision': self.GET_RASPBERRY_INFOS['pcbrevision'],
            'hwrevision': self.GET_RASPBERRY_INFOS['revision'],
            'version': '6.6.6',
            'apps': json.dumps(list(self.GET_MODULES.keys())),
            'port': '80',
            'hostname': 'testhostname',
            'uuid': self.module.uuid,
            'cleepdesktop': '0',
        })

        mock_pyrebus.return_value.get_mac_addresses = Mock()

    def test_get_bus_header_exception(self):
        self.init_session()
        mock_pyrebus.return_value.get_mac_addresses.return_value = ['00:00:00:00:00:00']
        self.session.set_mock_command_no_response('get_modules')

        header = self.module.get_bus_header()
        logging.debug('Header: %s' % header)

        self.assertDictEqual(header, {
            'ssl': '0',
            'hwmodel': self.GET_RASPBERRY_INFOS['model'],
            'macs': '["00:00:00:00:00:00"]',
            'hwethernet': '1' if self.GET_RASPBERRY_INFOS['ethernet'] else '0',
            'hwwireless': '1' if self.GET_RASPBERRY_INFOS['wireless'] else '0',
            'hwaudio': '1' if self.GET_RASPBERRY_INFOS['audio'] else '0',
            'hwmemory': self.GET_RASPBERRY_INFOS['memory'],
            'pcbrevision': self.GET_RASPBERRY_INFOS['pcbrevision'],
            'hwrevision': self.GET_RASPBERRY_INFOS['revision'],
            'version': '6.6.6',
            'apps': '[]',
            'port': '80',
            'hostname': 'testhostname',
            'uuid': self.module.uuid,
            'cleepdesktop': '0',
        })

        mock_pyrebus.return_value.get_mac_addresses = Mock()

    def test_decode_bus_header(self):
        self.init_session()

        header = self.module._decode_bus_header({
            'field1': 'value1',
            'cleepdesktop': '1',
            'field2': 'value2',
            'ssl': '0',
            'port': '1666',
            'macs': '["00:00:00:00:00","11:11:11:11:11"]',
        })
        logging.debug('Header: %s' % header)

        self.assertDictEqual(header, {
            'field1': 'value1',
            'field2': 'value2',
            'cleepdesktop': True,
            'ssl': False,
            'port': 1666,
            'macs': ['00:00:00:00:00', '11:11:11:11:11'],
        })

    def test_on_stop(self):
        self.init_session()
        self.module._stop_external_bus = Mock()

        self.module._on_stop()

        self.module._stop_external_bus.assert_called()

    def test_on_process(self):
        self.init_session()

        self.module._on_process()

        mock_pyrebus.return_value.run_once.assert_called()

    def test_start_external_bus(self):
        self.init_session()

        self.module._start_external_bus()

        mock_pyrebus.return_value.start.assert_called()

    def test_stop_external_bus(self):
        self.init_session()

        self.module._stop_external_bus()

        mock_pyrebus.return_value.stop.assert_called()

    def test_get_peers(self):
        self.init_session()
        self.module.peers = {
            'peer1': {},
            'peer2': {},
        }

        peers = self.module.get_peers()

        self.assertDictEqual(peers, self.module.peers)

    def test_on_message_received(self):
        self.init_session()
        msg = ExternalBusMessage()
        msg.event = 'my.dummy.event'
        msg.to = 'dummy'
        msg.params = {
            'param1': 'value1',
        }
        msg.peer_hostname = 'dummyhostname'
        msg.peer_ip = '1.1.1.1'
        msg.device_id = '123-456-789'
        msg.peer_macs = ['00:00:00:00:00']
        self.module.send_external_event = Mock()

        self.module._on_message_received(msg)

        self.module.send_external_event.assert_called_with(
            'my.dummy.event',
            {'param1': 'value1'},
            {'hostname': 'dummyhostname', 'ip': '1.1.1.1', 'device_id': '123-456-789', 'macs': ['00:00:00:00:00']}
        )

    def test_on_peer_connected(self):
        self.init_session()

        header = self.make_header()
        self.module._on_peer_connected('987-654-321', copy.deepcopy(header))
        logging.debug('Peers: %s' % self.module.peers)

        header.update({
            'online': True,
            'peer_id': '987-654-321',
        })
        self.assertDictEqual(self.module.peers, {
            '123-456-789': header,
        })

    def test_on_peer_connected_peer_reconnection(self):
        self.init_session()

        header = self.make_header()
        self.module._on_peer_connected('987-654-320', copy.deepcopy(header))
        logging.debug('Peers: %s' % self.module.peers)

        header.update({
            'online': True,
            'peer_id': '987-654-320',
        })
        self.assertDictEqual(self.module.peers, {
            '123-456-789': header,
        })

    def test_on_peer_disconnected(self):
        self.init_session()

        header = self.make_header()
        self.module.peers['123-456-789'] = header
        header.update({
            'online': True,
            'peer_id': '987-654-321'
        })

        self.module._on_peer_disconnected('987-654-321')

        self.assertFalse(self.module.peers['123-456-789']['online'])

    def test_on_peer_disconnected_peer_not_found(self):
        self.init_session()

        header = self.make_header()
        self.module.peers['123-456-789'] = header
        header.update({
            'online': True,
            'peer_id': '987-654-320'
        })

        self.module._on_peer_disconnected('987-654-321')

        self.assertTrue(self.module.peers['123-456-789']['online'])

    def test_event_received(self):
        self.init_session()

        self.module.event_received({
            'startup': False,
            'event': 'my.dummy.event',
            'params': {'param1': 'value1'},
            'core_event': False,
            'device_id': '123-456-789',
        })

        mock_pyrebus.return_value.broadcast_event.assert_called_with(
            'my.dummy.event',
            {'param1': 'value1'},
            '123-456-789',
        )

    def test_event_received_drop_core_event(self):
        self.init_session()

        self.module.event_received({
            'startup': False,
            'event': 'my.dummy.event',
            'params': {'param1': 'value1'},
            'core_event': True,
            'device_id': '123-456-789',
        })

        self.assertFalse(mock_pyrebus.return_value.broadcast_event.called)

    def test_event_received_handle_network_up(self):
        self.init_session()
        mock_pyrebus.return_value.is_running.return_value = False
        self.module._start_external_bus = Mock()

        self.module.event_received({
            'startup': False,
            'event': 'network.status.up',
            'params': {'param1': 'value1'},
            'core_event': True,
            'device_id': '123-456-789',
        })

        self.module._start_external_bus.assert_called()

        mock_pyrebus.return_value.is_running = Mock()

    def test_event_received_handle_network_down(self):
        self.init_session()
        mock_pyrebus.return_value.is_running.return_value = True
        self.module._stop_external_bus = Mock()

        self.module.event_received({
            'startup': False,
            'event': 'network.status.down',
            'params': {'param1': 'value1'},
            'core_event': True,
            'device_id': '123-456-789',
        })

        self.module._stop_external_bus.assert_called()

        mock_pyrebus.return_value.is_running = Mock()

if __name__ == "__main__":
    # coverage run --omit="*lib/python*/*","test_*" --concurrency=thread test_cleepbus.py; coverage report -m -i
    unittest.main()

    
