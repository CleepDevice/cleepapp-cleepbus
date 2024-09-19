from cleep.libs.tests import session, lib
import unittest
import logging
import sys
import json
import copy
sys.path.append("../")
from backend.cleepbus import Cleepbus
from backend.pyrebus import PyreBus
from cleep.exception import (
    InvalidParameter,
    MissingParameter,
    CommandError,
    Unauthorized,
)
from cleep.common import PeerInfos, MessageRequest
import os
import time
from uuid import UUID
from unittest.mock import Mock, patch, ANY
from threading import Timer

mock_hostname = Mock()
mock_pyrebus = Mock()
mock_tools = Mock()


@patch("backend.cleepbus.Hostname", mock_hostname)
@patch("backend.cleepbus.VERSION", "6.6.6")
@patch("backend.cleepbus.PyreBus", mock_pyrebus)
@patch("backend.cleepbus.Tools", mock_tools)
class TestsCleepbus(unittest.TestCase):

    GET_MODULES = {
        "mod1": {},
        "mod2": {},
        "mod3": {},
    }
    GET_RASPBERRY_INFOS = {
        "date": "2020",
        "model": "B",
        "pcbrevision": "1.2",
        "ethernet": False,
        "wireless": True,
        "audio": False,
        "gpiopins": 666,
        "memory": "1 GB",
        "notes": "no notes",
        "revision": "a020d3",
    }

    def setUp(self):
        self.session = session.TestSession(self)
        logging.basicConfig(
            level=logging.FATAL,
            format=u"%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s",
        )

        mock_hostname.return_value.get_hostname.return_value = "testhostname"
        mock_tools.raspberry_pi_infos.return_value = self.GET_RASPBERRY_INFOS

    def tearDown(self):
        self.session.clean()
        mock_hostname.reset_mock()
        mock_pyrebus.reset_mock()

    def init_session(self, start_module=True):
        self.module = self.session.setup(Cleepbus, mock_on_start=False, mock_on_stop=False)
        if start_module:
            self.session.start_module(self.module)
            self.session.add_mock_command(
                self.session.make_mock_command("get_modules", self.GET_MODULES)
            )

    def make_header(self):
        return {
            "ssl": "0",
            "hwmodel": self.GET_RASPBERRY_INFOS["model"],
            "macs": '["00:00:00:00:00:00"]',
            "hwethernet": "1" if self.GET_RASPBERRY_INFOS["ethernet"] else "0",
            "hwwireless": "1" if self.GET_RASPBERRY_INFOS["wireless"] else "0",
            "hwaudio": "1" if self.GET_RASPBERRY_INFOS["audio"] else "0",
            "hwmemory": self.GET_RASPBERRY_INFOS["memory"],
            "pcbrevision": self.GET_RASPBERRY_INFOS["pcbrevision"],
            "hwrevision": self.GET_RASPBERRY_INFOS["revision"],
            "version": "6.6.6",
            "apps": json.dumps(list(self.GET_MODULES.keys())),
            "port": "80",
            "hostname": "testhostname",
            "uuid": "123-456-789",
            "cleepdesktop": "0",
        }

    def make_peer_infos(self):
        infos = PeerInfos()
        infos.hostname = "testhostname"
        infos.uuid = "123-456-789"
        infos.ident = "987-654-321"
        infos.ip = "127.0.0.1"
        infos.port = 80
        infos.ssl = False
        infos.macs = ["00:00:00:00:00:00"]
        infos.extra = {
            "hwethernet": "1" if self.GET_RASPBERRY_INFOS["ethernet"] else "0",
            "hwwireless": "1" if self.GET_RASPBERRY_INFOS["wireless"] else "0",
            "hwaudio": "1" if self.GET_RASPBERRY_INFOS["audio"] else "0",
            "hwmemory": self.GET_RASPBERRY_INFOS["memory"],
            "pcbrevision": self.GET_RASPBERRY_INFOS["pcbrevision"],
            "hwrevision": self.GET_RASPBERRY_INFOS["revision"],
            "version": "6.6.6",
            "apps": json.dumps(list(self.GET_MODULES.keys())),
        }
        return infos

    def test_configure(self):
        self.init_session(False)
        self.module._get_config_field = Mock(return_value=None)
        self.module._set_config_field = Mock()

        self.session.start_module(self.module)

        mock_pyrebus.assert_called_with(
            self.module._on_message_received,
            self.module._on_peer_connected,
            self.module._on_peer_disconnected,
            self.module._decode_peer_infos,
            ANY,
            ANY,
        )
        self.module._set_config_field.assert_called_with("uuid", self.module.uuid)

    def test_configure_no_uuid_update(self):
        self.init_session(False)
        self.module._get_config_field = Mock(return_value="123-456-789")
        self.module._set_config_field = Mock()

        self.session.start_module(self.module)

        mock_pyrebus.assert_called_with(
            self.module._on_message_received,
            self.module._on_peer_connected,
            self.module._on_peer_disconnected,
            self.module._decode_peer_infos,
            ANY,
            ANY,
        )
        self.assertFalse(self.module._set_config_field.called)

    def test_get_peer_infos(self):
        self.init_session()
        mock_pyrebus.return_value.get_mac_addresses.return_value = ["00:00:00:00:00:00"]

        infos = self.module.get_peer_infos()
        logging.debug("Infos: %s" % infos)

        self.assertEqual(
            infos,
            {
                "ssl": "0",
                "hwmodel": self.GET_RASPBERRY_INFOS["model"],
                "macs": '["00:00:00:00:00:00"]',
                "hwethernet": "1" if self.GET_RASPBERRY_INFOS["ethernet"] else "0",
                "hwwireless": "1" if self.GET_RASPBERRY_INFOS["wireless"] else "0",
                "hwaudio": "1" if self.GET_RASPBERRY_INFOS["audio"] else "0",
                "hwmemory": self.GET_RASPBERRY_INFOS["memory"],
                "pcbrevision": self.GET_RASPBERRY_INFOS["pcbrevision"],
                "hwrevision": self.GET_RASPBERRY_INFOS["revision"],
                "version": "6.6.6",
                "apps": json.dumps(list(self.GET_MODULES.keys())),
                "port": "80",
                "hostname": "testhostname",
                "uuid": self.module.uuid,
                "cleepdesktop": "0",
                "auth": "0",
            },
        )

        mock_pyrebus.return_value.get_mac_addresses = Mock()

    def test_get_peer_infos_exception(self):
        self.init_session()
        mock_pyrebus.return_value.get_mac_addresses.return_value = ["00:00:00:00:00:00"]
        self.session.set_mock_command_no_response("get_modules")

        infos = self.module.get_peer_infos()
        logging.debug("Infos: %s" % infos)

        self.assertDictEqual(
            infos,
            {
                "ssl": "0",
                "hwmodel": self.GET_RASPBERRY_INFOS["model"],
                "macs": '["00:00:00:00:00:00"]',
                "hwethernet": "1" if self.GET_RASPBERRY_INFOS["ethernet"] else "0",
                "hwwireless": "1" if self.GET_RASPBERRY_INFOS["wireless"] else "0",
                "hwaudio": "1" if self.GET_RASPBERRY_INFOS["audio"] else "0",
                "hwmemory": self.GET_RASPBERRY_INFOS["memory"],
                "pcbrevision": self.GET_RASPBERRY_INFOS["pcbrevision"],
                "hwrevision": self.GET_RASPBERRY_INFOS["revision"],
                "version": "6.6.6",
                "apps": "[]",
                "port": "80",
                "hostname": "testhostname",
                "uuid": self.module.uuid,
                "cleepdesktop": "0",
                "auth": "0",
            },
        )

        mock_pyrebus.return_value.get_mac_addresses = Mock()

    def test_decode_peer_infos(self):
        self.init_session()

        peer_infos = self.module._decode_peer_infos(
            {
                "field1": "value1",
                "cleepdesktop": "1",
                "hostname": "dummy",
                "ssl": "0",
                "field2": "value2",
                "port": "1666",
                "macs": '["00:00:00:00:00","11:11:11:11:11"]',
            }
        )
        logging.debug("Peer infos: %s" % peer_infos.to_dict(True))

        self.assertDictEqual(
            peer_infos.to_dict(True),
            {
                "ssl": False,
                "port": 1666,
                "macs": ["00:00:00:00:00", "11:11:11:11:11"],
                "hostname": "dummy",
                "ip": None,
                "uuid": None,
                "ident": None,
                "cleepdesktop": True,
                "online": False,
                "extra": {
                    "field1": "value1",
                    "field2": "value2",
                },
            },
        )

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
        mock_pyrebus.return_value.get_mac_addresses.return_value = ["00:00:00:00:00:00"]

        self.module._start_external_bus()

        mock_pyrebus.return_value.start.assert_called()
        mock_pyrebus.return_value.get_mac_addresses = Mock()

    def test_stop_external_bus(self):
        self.init_session()

        self.module._stop_external_bus()

        mock_pyrebus.return_value.stop.assert_called()

    def test_get_peers(self):
        self.init_session()
        self.module.peers = {
            "peer1": PeerInfos(
                uuid="123",
                ident="666",
                cleepdesktop=False,
                port=8000,
                macs=["00:00:00:00:00"],
            ),
            "peer2": PeerInfos(
                uuid="456", ident="999", cleepdesktop=True, hostname="dummy"
            ),
        }

        peers = self.module.get_peers()

        self.assertDictEqual(
            peers,
            {
                "peer1": {
                    "cleepdesktop": False,
                    "uuid": "123",
                    "ident": "666",
                    "ip": None,
                    "macs": ["00:00:00:00:00"],
                    "ssl": False,
                    "port": 8000,
                    "hostname": None,
                    "online": False,
                },
                "peer2": {
                    "cleepdesktop": True,
                    "uuid": "456",
                    "ident": "999",
                    "ip": None,
                    "macs": None,
                    "ssl": False,
                    "port": 80,
                    "hostname": "dummy",
                    "online": False,
                },
            },
        )

    def test_on_message_received_event(self):
        self.init_session()
        peer_infos = PeerInfos(
            uuid="123-456-789",
            ident="1234567890",
            hostname="dummyhostname",
            ip="1.1.1.1",
            macs=["00:00:00:00:00"],
        )
        self.module.peers = {
            "123-456-789": peer_infos,
        }
        msg = MessageRequest()
        msg.event = "my.dummy.event"
        msg.to = "dummy"
        msg.params = {
            "param1": "value1",
        }
        msg.device_id = "123-456-789"
        msg.peer_infos = peer_infos
        self.module.send_event = Mock()
        self.module.send_command = Mock()

        self.module._on_message_received("1234567890", msg)

        self.assertFalse(self.module.send_command.called)
        self.module.send_event.assert_called_with(
            "my.dummy.event",
            {"param1": "value1"},
            to="dummy",
        )

    def test_on_message_received_command(self):
        self.init_session()
        peer_infos = PeerInfos(
            uuid="123-456-789",
            ident="1234567890",
            hostname="dummyhostname",
            ip="1.1.1.1",
            macs=["00:00:00:00:00"],
        )
        self.module.peers = {
            "123-456-789": peer_infos,
        }
        msg = MessageRequest()
        msg.command = "my_command"
        msg.to = "dummy"
        msg.params = {
            "param1": "value1",
        }
        msg.peer_infos = peer_infos
        self.module.send_event = Mock()
        resp = {
            "error": False,
            "message": "",
            "data": {
                "resp1": "val1",
            },
        }
        self.module.send_command = Mock(return_value=resp)

        self.module._on_message_received("1234567890", msg)

        self.module.send_command.assert_called_with(
            "my_command", "dummy", {"param1": "value1"}, 5.0
        )
        self.assertFalse(self.module.send_event.called)

    def test_on_message_received_from_unknown_peer(self):
        self.init_session()
        peer_infos = PeerInfos(
            uuid="123-456-789",
            ident="1234567890",
            hostname="dummyhostname",
            ip="1.1.1.1",
            macs=["00:00:00:00:00"],
        )
        self.module.peers = {
            "123-456-789": peer_infos,
        }
        msg = MessageRequest()
        msg.event = "my.dummy.event"
        msg.to = "dummy"
        msg.params = {
            "param1": "value1",
        }
        msg.device_id = "123-456-789"
        msg.peer_infos = peer_infos
        self.module.send_event = Mock()

        self.module._on_message_received("1234567899", msg)

        self.assertFalse(self.module.send_event.called)

    def test_on_peer_connected(self):
        self.init_session()

        peer_infos = self.make_peer_infos()
        self.module._on_peer_connected("987-654-321", peer_infos)
        logging.debug("Peers: %s" % self.module.peers["123-456-789"].to_dict(True))

        self.assertDictEqual(
            self.module.peers["123-456-789"].to_dict(True),
            {
                "uuid": "123-456-789",
                "ident": "987-654-321",
                "ip": "127.0.0.1",
                "port": 80,
                "hostname": "testhostname",
                "macs": ["00:00:00:00:00:00"],
                "ssl": False,
                "cleepdesktop": False,
                "online": True,
                "extra": {
                    "hwethernet": "1" if self.GET_RASPBERRY_INFOS["ethernet"] else "0",
                    "hwwireless": "1" if self.GET_RASPBERRY_INFOS["wireless"] else "0",
                    "hwaudio": "1" if self.GET_RASPBERRY_INFOS["audio"] else "0",
                    "hwmemory": self.GET_RASPBERRY_INFOS["memory"],
                    "pcbrevision": self.GET_RASPBERRY_INFOS["pcbrevision"],
                    "hwrevision": self.GET_RASPBERRY_INFOS["revision"],
                    "version": "6.6.6",
                    "apps": json.dumps(list(self.GET_MODULES.keys())),
                },
            },
        )

    def test_on_peer_connected_peer_reconnection(self):
        self.init_session()

        peer_infos = self.make_peer_infos()
        peer_infos.online = False
        self.module.peers = {
            peer_infos.uuid: peer_infos,
        }
        self.module._on_peer_connected("987-654-321", peer_infos)
        logging.debug("Peers: %s" % self.module.peers["123-456-789"].to_dict(True))

        self.assertDictEqual(
            self.module.peers["123-456-789"].to_dict(True),
            {
                "uuid": "123-456-789",
                "ident": "987-654-321",
                "ip": "127.0.0.1",
                "port": 80,
                "hostname": "testhostname",
                "macs": ["00:00:00:00:00:00"],
                "ssl": False,
                "cleepdesktop": False,
                "online": True,  # ==> should be True
                "extra": {
                    "hwethernet": "1" if self.GET_RASPBERRY_INFOS["ethernet"] else "0",
                    "hwwireless": "1" if self.GET_RASPBERRY_INFOS["wireless"] else "0",
                    "hwaudio": "1" if self.GET_RASPBERRY_INFOS["audio"] else "0",
                    "hwmemory": self.GET_RASPBERRY_INFOS["memory"],
                    "pcbrevision": self.GET_RASPBERRY_INFOS["pcbrevision"],
                    "hwrevision": self.GET_RASPBERRY_INFOS["revision"],
                    "version": "6.6.6",
                    "apps": json.dumps(list(self.GET_MODULES.keys())),
                },
            },
        )

    def test_on_peer_disconnected(self):
        self.init_session()
        peer_infos = self.make_peer_infos()
        peer_infos.online = True
        self.module.peers = {
            peer_infos.uuid: peer_infos,
        }

        self.module._on_peer_disconnected("987-654-321")

        self.assertFalse(self.module.peers["123-456-789"].online)

    def test_on_peer_disconnected_peer_not_found(self):
        self.init_session()
        peer_infos = self.make_peer_infos()
        peer_infos.online = True
        self.module.peers = {
            peer_infos.uuid: peer_infos,
        }

        self.module._on_peer_disconnected("111-111-111")
        logging.debug("Peers: %s" % self.module.peers[peer_infos.uuid])

        self.assertTrue(self.module.peers[peer_infos.uuid].online)

    def test_on_event(self):
        self.init_session()

        self.module.on_event(
            {
                "startup": False,
                "event": "my.dummy.event",
                "params": {"param1": "value1"},
                "sender": "mod1",
                "propagate": True,
                "device_id": "123-456-789",
            }
        )

        mock_pyrebus.return_value.send_message.assert_called()
        call_args = mock_pyrebus.return_value.send_message.call_args
        logging.debug("Call args: %s" % call_args.args[0])
        self.assertEqual(call_args.args[0].event, "my.dummy.event")
        self.assertEqual(call_args.args[0].params, {"param1": "value1"})
        self.assertEqual(call_args.args[0].command_uuid, None)
        self.assertEqual(call_args.args[0].peer_infos, None)
        self.assertEqual(call_args.args[0].to, None)

    def test_on_event_drop_propagate(self):
        self.init_session()

        self.module.on_event(
            {
                "startup": False,
                "event": "my.dummy.event",
                "params": {"param1": "value1"},
                "propagate": False,
                "device_id": "123-456-789",
            }
        )

        self.assertFalse(mock_pyrebus.return_value.send_message.called)

    def test_on_event_handle_network_up(self):
        self.init_session()
        mock_pyrebus.return_value.is_running.return_value = False
        self.module._start_external_bus = Mock()

        self.module.on_event(
            {
                "startup": False,
                "event": "network.status.up",
                "params": {"param1": "value1"},
                "propagate": True,
                "device_id": "123-456-789",
            }
        )

        self.module._start_external_bus.assert_called()

        mock_pyrebus.return_value.is_running = Mock()

    def test_on_event_handle_network_down(self):
        self.init_session()
        mock_pyrebus.return_value.is_running.return_value = True
        self.module._stop_external_bus = Mock()

        self.module.on_event(
            {
                "startup": False,
                "event": "network.status.down",
                "params": {"param1": "value1"},
                "propagate": True,
                "device_id": "123-456-789",
            }
        )

        self.module._stop_external_bus.assert_called()

        mock_pyrebus.return_value.is_running = Mock()

    def test_send_command_to_peer(self):
        self.init_session()
        peer_infos = self.make_peer_infos()
        peer_infos.online = True
        self.module.peers = {
            peer_infos.uuid: peer_infos,
        }

        self.module._send_command_to_peer(
            "my_command", "dummy", peer_infos.uuid, {"param1": "value1"}
        )

        mock_pyrebus.return_value.send_message.assert_called()
        msg = mock_pyrebus.return_value.send_message.call_args.args[0]
        logging.debug("Msg: %s" % msg)
        self.assertEqual(msg.command, "my_command")
        self.assertEqual(msg.to, "dummy")
        self.assertDictEqual(msg.params, {"param1": "value1"})
        self.assertDictEqual(msg.peer_infos.to_dict(), peer_infos.to_dict())
        self.assertEqual(msg.timeout, 8.0)

    def test_send_command_to_peer_check_parameters(self):
        self.init_session()
        peer_infos = self.make_peer_infos()
        peer_infos.online = True
        self.module.peers = {
            peer_infos.uuid: peer_infos,
        }

        with self.assertRaises(MissingParameter) as cm:
            self.module._send_command_to_peer(
                None, "dummy", peer_infos.uuid, {"param1": "value1"}
            )
        self.assertEqual(str(cm.exception), 'Parameter "command" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module._send_command_to_peer(
                "my_command", None, peer_infos.uuid, {"param1": "value1"}
            )
        self.assertEqual(str(cm.exception), 'Parameter "to" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module._send_command_to_peer(
                "my_command", "dummy", None, {"param1": "value1"}
            )
        self.assertEqual(str(cm.exception), 'Parameter "peer_uuid" is missing')

        with self.assertRaises(InvalidParameter) as cm:
            self.module._send_command_to_peer(
                "", "dummy", peer_infos.uuid, {"param1": "value1"}
            )
        self.assertEqual(
            str(cm.exception), 'Parameter "command" is invalid (specified="")'
        )
        with self.assertRaises(InvalidParameter) as cm:
            self.module._send_command_to_peer(
                "my_command", "", peer_infos.uuid, {"param1": "value1"}
            )
        self.assertEqual(str(cm.exception), 'Parameter "to" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            self.module._send_command_to_peer(
                "my_command", "dummy", "", {"param1": "value1"}
            )
        self.assertEqual(
            str(cm.exception), 'Parameter "peer_uuid" is invalid (specified="")'
        )
        with self.assertRaises(InvalidParameter) as cm:
            self.module._send_command_to_peer(
                "my_command", "dummy", "123-123-123", {"param1": "value1"}
            )
        self.assertEqual(
            str(cm.exception), 'Specified peer "123-123-123" does not exist'
        )
        peer_infos.online = False
        with self.assertRaises(InvalidParameter) as cm:
            self.module._send_command_to_peer(
                "my_command", "dummy", peer_infos.uuid, {"param1": "value1"}
            )
        self.assertEqual(
            str(cm.exception), 'Specified peer "%s" is not online' % peer_infos.uuid
        )
        peer_infos.online = True

    def test_send_event_to_peer(self):
        self.init_session()
        peer_infos = self.make_peer_infos()
        peer_infos.online = True
        self.module.peers = {
            peer_infos.uuid: peer_infos,
        }

        self.module._send_event_to_peer(
            "my_event", peer_infos.uuid, {"param1": "value1"}
        )

        mock_pyrebus.return_value.send_message.assert_called()
        msg = mock_pyrebus.return_value.send_message.call_args.args[0]
        logging.debug("Msg: %s" % msg)
        self.assertEqual(msg.event, "my_event")
        self.assertEqual(msg.to, None)
        self.assertDictEqual(msg.params, {"param1": "value1"})
        self.assertDictEqual(msg.peer_infos.to_dict(), peer_infos.to_dict())
        self.assertEqual(msg.timeout, None)


class TestsFunctionnalCleepbus(unittest.TestCase):

    GET_MODULES = {
        "mod1": {},
        "mod2": {},
        "mod3": {},
    }

    def setUp(self):
        self.session = session.TestSession(self)
        logging.basicConfig(
            level=logging.FATAL,
            format=u"%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s",
        )

    def tearDown(self):
        self.session.clean()

    def init_session(self):
        self.module = self.session.setup(Cleepbus, mock_on_start=False, mock_on_stop=False)
        self.module.get_peer_infos = Mock(
            return_value={
                "uuid": "123-456-789",
                "version": "0.0.0",
                "hostname": "test",
                "port": "80",
                "ssl": "1",
                "cleepdesktop": "0",
                "macs": '["00:00:00:00:00:00"]',
            }
        )

        self.session.start_module(self.module)
        self.session.add_mock_command(
            self.session.make_mock_command("get_modules", self.GET_MODULES)
        )
        self.module.on_event({"event": "network.status.up"})

    def test_send_event_to_peers(self):
        self.init_session()
        mock_whisper = Mock()
        self.module.external_bus.node.whisper = mock_whisper
        mock_shout = Mock()
        self.module.external_bus.node.shout = mock_shout

        self.module.on_event(
            {
                "event": "my.dummy.event",
                "params": {"param1": "value1"},
                "propagate": True,
                "device_id": "123-456-789",
                "sender": "mod1",
            }
        )

        time.sleep(1.0)

        mock_shout.assert_called()
        call_args = mock_shout.call_args[0]
        call_args_dict = json.loads(call_args[1].decode("utf8"))
        logging.debug("Call args: %s" % call_args_dict)
        self.assertDictEqual(
            call_args_dict,
            {
                "event": "my.dummy.event",
                "params": {"param1": "value1"},
                "propagate": False,
                "sender": "mod1",
                "to": None,
                "device_id": None,
            },
        )
        self.assertFalse(mock_whisper.called)

    def test_send_command_to_peer(self):
        self.init_session()
        mock_whisper = Mock()
        self.module.external_bus.node.whisper = mock_whisper
        mock_shout = Mock()
        self.module.external_bus.node.shout = mock_shout

        peer_uuid = "19038bd4-fa38-42a0-ae39-1460a65bf471"
        peer_ident = "8bd91d82-3265-40d0-9417-f08c46468d25"
        peer_infos = PeerInfos(
            uuid=peer_uuid, ident=peer_ident, ip="0.0.0.0", macs=["00:00:00:00:00:00"]
        )
        peer_infos.online = True
        self.module.peers = {
            peer_uuid: peer_infos,
        }

        self.module.send_command_to_peer(
            command="acommand",
            to="mod",
            peer_uuid=peer_uuid,
            params={"param": "value"},
        )
        time.sleep(1.0)

        mock_whisper.assert_called_with(UUID(peer_ident), ANY)
        call_args = mock_whisper.call_args[0]
        call_args_dict = json.loads(call_args[1].decode("utf8"))
        logging.debug("Call args: %s" % call_args_dict)
        self.maxDiff = None
        self.assertDictEqual(
            call_args_dict,
            {
                "command": "acommand",
                "params": {"param": "value"},
                "command_uuid": ANY,
                "to": "mod",
                "timeout": 5.0,
                "sender": ANY,
            },
        )
        self.assertIsNotNone(call_args_dict["command_uuid"])
        self.assertFalse(mock_shout.called)


class TestsPyrebus(unittest.TestCase):

    GET_IFADDRS = [
        {
            "ens37": {
                17: {"addr": "00:0c:29:20:7d:5f"},
                2: {
                    "addr": "192.168.40.128",
                    "netmask": "255.255.255.0",
                    "broadcast": "192.168.40.255",
                },
                10: {
                    "addr": "fe80::136a:cf3d:9c98:2ffc",
                    "scope": 2,
                    "netmask": "ffff:ffff:ffff:ffff::",
                },
            }
        },
        {
            "ens37no17": {
                2: {
                    "addr": "192.168.40.128",
                    "netmask": "255.255.255.0",
                    "broadcast": "192.168.40.255",
                },
                10: {
                    "addr": "fe80::136a:cf3d:9c98:2ffc",
                    "scope": 2,
                    "netmask": "ffff:ffff:ffff:ffff::",
                },
            }
        },
        {
            "ens37noaddr": {
                17: {"addr": "00:0c:29:20:7d:5f"},
                2: {"netmask": "255.255.255.0", "broadcast": "192.168.40.255"},
            }
        },
        {
            "ens37nomac": {
                17: {"dummy": "dummy"},
                2: {
                    "addr": "192.168.40.128",
                    "netmask": "255.255.255.0",
                    "broadcast": "192.168.40.255",
                },
                10: {
                    "addr": "fe80::136a:cf3d:9c98:2ffc",
                    "scope": 2,
                    "netmask": "ffff:ffff:ffff:ffff::",
                },
            }
        },
        {"br-858bcb464b98": {17: {"addr": "02:42:72:50:50:7e"}}},
        {"docker0": {17: {"addr": "02:42:3e:2f:05:f6"}}},
        {
            "veth30b3b80": {
                17: {"addr": "c6:28:75:af:c6:f1"},
                10: {
                    "addr": "fe80::c428:75ff:feaf:c6f1",
                    "scope": 6,
                    "netmask": "ffff:ffff:ffff:ffff::",
                },
            }
        },
        {
            "lo": {
                17: {"addr": "00:0c:29:20:7d:5f"},
                2: {"addr": "127.0.0.1", "netmask": "255.0.0.0"},
                10: {
                    "addr": "::1",
                    "netmask": "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
                },
            }
        },
        {
            "eth1": {
                17: {"addr": "54:04:a6:cc:b3:b6"},
                2: {
                    "addr": "82.64.200.227",
                    "netmask": "255.255.255.0",
                    "broadcast": "82.64.200.255",
                },
                10: {
                    "addr": "fe80::5604:a6ff:fecc:b3b6",
                    "scope": 2,
                    "netmask": "ffff:ffff:ffff:ffff::",
                },
            }
        },
    ]

    def setUp(self):
        lib.TestLib(self)
        logging.basicConfig(
            level=logging.FATAL,
            format=u"%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s",
        )

        self.messages = []
        self.peers = {}
        self.online = {}
        self.mock_crashreport = Mock()
        self.peer_infos = PeerInfos(
            uuid="123-456-789", ident="987-654-321", ip="1.2.3.4"
        )
        self.decode_peer_infos = Mock(return_value=self.peer_infos)

    def tearDown(self):
        self.messages.clear()
        self.peers.clear()
        self.online.clear()
        self.mock_crashreport.reset_mock()

    def init_lib(self, debug=False):
        self.lib = PyreBus(
            self.on_message_received,
            self.on_peer_connected,
            self.on_peer_disconnected,
            self.decode_peer_infos,
            debug,
            self.mock_crashreport,
        )
        if not debug:
            self.lib.logger.setLevel(logging.FATAL)

    def on_message_received(self, peer_id, message):
        self.messages.append(
            {
                "peer_id": peer_id,
                "message": message,
            }
        )

    def on_peer_connected(self, peer_id, peer_infos):
        self.peers[peer_id] = peer_infos
        self.online[peer_id] = True

    def on_peer_disconnected(self, peer_id):
        self.online[peer_id] = False

    def test_init(self):
        self.init_lib(True)

        log = logging.getLogger("pyre")
        self.assertEqual(log.getEffectiveLevel(), logging.DEBUG)

    def test_init_log_disabled(self):
        self.init_lib(False)

        log = logging.getLogger("pyre")
        self.assertEqual(log.getEffectiveLevel(), logging.WARN)

    @patch("backend.pyrebus.zhelper_get_ifaddrs")
    def test_get_mac_addresses(self, mock_getifaddrs):
        mock_getifaddrs.return_value = self.GET_IFADDRS
        self.init_lib()

        macs = self.lib.get_mac_addresses()
        logging.debug("Macs: %s" % macs)

        self.assertListEqual(macs, ["00:0c:29:20:7d:5f"])

    @patch("backend.pyrebus.Pyre")
    @patch("backend.pyrebus.zmq")
    def test_start(self, mock_zmq, mock_pyre):
        self.init_lib()

        self.lib.start({"field1": "value1"}, "TESTBUS", "TESTCHANNEL")

        self.assertEqual(self.lib._PyreBus__bus_name, "TESTBUS")
        self.assertEqual(self.lib._PyreBus__bus_channel, "TESTCHANNEL")
        mock_zmq.Context.assert_called()
        self.assertEqual(mock_zmq.Context.return_value.socket.call_count, 2)
        mock_pyre.assert_called_with("TESTBUS")
        mock_pyre.return_value.join.assert_called_with("TESTCHANNEL")
        mock_pyre.return_value.set_header.assert_called_with("field1", "value1")
        mock_pyre.return_value.start.assert_called()
        mock_zmq.Poller.assert_called()
        self.assertEqual(mock_zmq.Poller.return_value.register.call_count, 2)
        self.assertEqual(self.lib._PyreBus__externalbus_configured, True)

    def test_start_check_parameters(self):
        self.init_lib()

        with self.assertRaises(Exception) as cm:
            self.lib.start(None)
        self.assertEqual(
            str(cm.exception), 'Parameter "infos" is not specified or invalid'
        )
        with self.assertRaises(Exception) as cm:
            self.lib.start({})
        self.assertEqual(
            str(cm.exception), 'Parameter "infos" is not specified or invalid'
        )
        with self.assertRaises(Exception) as cm:
            self.lib.start(["hello", "ola", "bonjour"])
        self.assertEqual(
            str(cm.exception), 'Parameter "infos" is not specified or invalid'
        )
        with self.assertRaises(Exception) as cm:
            self.lib.start({"field": "value"}, "")
        self.assertEqual(
            str(cm.exception), 'Parameter "bus_name" is not specified or invalid'
        )
        with self.assertRaises(Exception) as cm:
            self.lib.start({"field": "value"}, 12.34)
        self.assertEqual(
            str(cm.exception), 'Parameter "bus_name" is not specified or invalid'
        )
        with self.assertRaises(Exception) as cm:
            self.lib.start({"field": "value"}, "bus", "")
        self.assertEqual(
            str(cm.exception), 'Parameter "bus_channel" is not specified or invalid'
        )
        with self.assertRaises(Exception) as cm:
            self.lib.start({"field": "value"}, "bus", 12.34)
        self.assertEqual(
            str(cm.exception), 'Parameter "bus_channel" is not specified or invalid'
        )

    @patch("backend.pyrebus.Pyre")
    @patch("backend.pyrebus.zmq")
    def test_is_running(self, mock_zmq, mock_pyre):
        self.init_lib()

        self.lib.start({"field1": "value1"}, "TESTBUS", "TESTCHANNEL")

        self.assertTrue(self.lib.is_running())

    def test_stop(self):
        self.init_lib()
        mock_pipein = Mock()
        self.lib.pipe_in = mock_pipein
        mock_pipeout = Mock()
        self.lib.pipe_out = mock_pipeout
        mock_node = Mock()
        self.lib.node = mock_node

        self.lib.stop()

        mock_pipein.send.assert_called_with(b'"%s"' % self.lib.BUS_STOP.encode("utf8"))
        mock_pipein.close.assert_called()
        mock_pipeout.close.assert_called()
        mock_node.stop.assert_called()
        self.assertEqual(self.lib._PyreBus__externalbus_configured, False)

    def test_stop_exception(self):
        self.init_lib()
        mock_pipein = Mock()
        self.lib.pipe_in = mock_pipein
        mock_pipeout = Mock()
        self.lib.pipe_out = mock_pipeout
        mock_node = Mock()
        mock_node.stop.side_effect = Exception("Test exception")
        self.lib.node = mock_node

        self.lib.stop()

        mock_pipein.send.assert_called_with(b'"%s"' % self.lib.BUS_STOP.encode("utf8"))
        mock_pipein.close.assert_called()
        mock_pipeout.close.assert_called()
        self.assertEqual(self.lib._PyreBus__externalbus_configured, False)

    @patch("backend.pyrebus.zmq")
    def test_run_once_message_to_send(self, mock_zmq):
        mock_zmq.POLLIN = "POLLIN"
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        mock_pipein = Mock()
        self.lib.pipe_in = mock_pipein
        mock_pipeout = Mock()
        self.lib.pipe_out = mock_pipeout
        mock_nodesocket = Mock()
        self.lib.node_socket = mock_nodesocket
        mock_poller = Mock()
        mock_poller.poll.return_value = {mock_pipeout: "POLLIN"}
        self.lib.poller = mock_poller
        self.lib._message_to_send_to_pipe = Mock(return_value=True)
        self.lib._message_to_receive_from_pipe = Mock(return_value=True)

        self.assertTrue(self.lib.run_once())

        self.lib._message_to_send_to_pipe.assert_called()
        self.assertFalse(self.lib._message_to_receive_from_pipe.called)

    @patch("backend.pyrebus.zmq")
    def test_run_once_message_to_receive(self, mock_zmq):
        mock_zmq.POLLIN = "POLLIN"
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        mock_pipein = Mock()
        self.lib.pipe_in = mock_pipein
        mock_pipeout = Mock()
        self.lib.pipe_out = mock_pipeout
        mock_nodesocket = Mock()
        self.lib.node_socket = mock_nodesocket
        mock_poller = Mock()
        mock_poller.poll.return_value = {mock_nodesocket: "POLLIN"}
        self.lib.poller = mock_poller
        self.lib._message_to_send_to_pipe = Mock(return_value=True)
        self.lib._message_to_receive_from_pipe = Mock(return_value=True)

        self.assertTrue(self.lib.run_once())

        self.assertFalse(self.lib._message_to_send_to_pipe.called)
        self.lib._message_to_receive_from_pipe.assert_called()

    def test_run_once_bus_not_configured(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = False
        self.lib._message_to_send_to_pipe = Mock(return_value=True)
        self.lib._message_to_receive_from_pipe = Mock(return_value=True)

        self.assertFalse(self.lib.run_once())

        self.assertFalse(self.lib._message_to_send_to_pipe.called)
        self.assertFalse(self.lib._message_to_receive_from_pipe.called)

    def test_run_once_exception_during_polling(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        mock_poller = Mock()
        mock_poller.poll.side_effect = Exception("Test exception")
        self.lib.poller = mock_poller
        self.lib._message_to_send_to_pipe = Mock(return_value=True)
        self.lib._message_to_receive_from_pipe = Mock(return_value=True)

        self.assertTrue(self.lib.run_once())

        self.assertFalse(self.lib._message_to_send_to_pipe.called)
        self.assertFalse(self.lib._message_to_receive_from_pipe.called)

    def test_run_once_ctrlc_during_polling(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        mock_node = Mock()
        self.lib.node = mock_node
        mock_poller = Mock()
        mock_poller.poll.side_effect = KeyboardInterrupt()
        self.lib.poller = mock_poller
        self.lib._message_to_send_to_pipe = Mock(return_value=True)
        self.lib._message_to_receive_from_pipe = Mock(return_value=True)

        self.assertFalse(self.lib.run_once())

        self.lib.node.stop.assert_called()
        self.assertFalse(self.lib._message_to_send_to_pipe.called)
        self.assertFalse(self.lib._message_to_receive_from_pipe.called)

    def test_message_to_receive_from_pipe_shout(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        message = {
            "command": "acommand",
            "params": {"key1": "val1"},
            "to": "dummy",
        }
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"SHOUT",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
            b"TESTCHANNEL",
            json.dumps(message).encode(),
        ]
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Messages: %s" % self.messages)

        self.assertEqual(len(self.peers), 0)
        self.assertEqual(len(self.messages), 1)
        self.assertEqual(self.messages[0]["peer_id"], ident)
        self.assertDictEqual(
            self.messages[0]["message"].to_dict(),
            {
                "broadcast": ANY,
                "command": message["command"],
                "params": message["params"],
                "to": message["to"],
                "sender": None,
            },
        )

    def test_message_to_receive_from_pipe_whisper(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        message = {
            "command": "acommand",
            "params": {"key1": "val1"},
            "to": "dummy",
        }
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"WHISPER",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
            json.dumps(message).encode(),
        ]
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Messages: %s" % self.messages)

        self.assertEqual(len(self.peers), 0)
        self.assertEqual(len(self.messages), 1)
        self.assertEqual(self.messages[0]["peer_id"], ident)
        self.assertDictEqual(
            self.messages[0]["message"].to_dict(),
            {
                "broadcast": ANY,
                "command": message["command"],
                "params": message["params"],
                "to": message["to"],
                "sender": None,
            },
        )

    def test_message_to_receive_from_pipe_enter(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        infos = PeerInfos()
        infos.info1 = "info1"
        infos.info2 = "info2"
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"ENTER",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
            json.dumps(infos.to_dict()).encode(),
        ]
        mock_node.peer_address.return_value = "http://192.168.1.1"
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Peers: %s" % self.peers)

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(list(self.peers.keys())), 1)
        self.assertDictEqual(self.peers[ident].to_dict(), self.peer_infos.to_dict())
        self.assertTrue(self.online[ident])

    def test_message_to_receive_from_pipe_exit(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        infos = PeerInfos()
        infos.info1 = "info1"
        infos.info2 = "info2"
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"EXIT",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
        ]
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Online: %s" % self.online)

        self.assertEqual(len(self.messages), 0)
        self.assertFalse(self.online[ident])

    def test_message_to_receive_from_pipe_other_bus(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        infos = PeerInfos()
        infos.info1 = "info1"
        infos.info2 = "info2"
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"EXIT",
            b"\x12\x34\x56\x78" * 4,
            b"OTHERBUS",
        ]
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_receive_from_pipe())

        self.assertEqual(len(self.messages), 0)
        self.assertEqual(len(self.peers), 0)

    def test_message_to_receive_from_pipe_shout_other_channel(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        message = {
            "command": "acommand",
            "params": {"key1": "val1"},
            "to": "dummy",
        }
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"SHOUT",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
            b"OTHERCHANNEL",
            json.dumps(message).encode(),
        ]
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Messages: %s" % self.messages)

        self.assertEqual(len(self.peers), 0)
        self.assertEqual(len(self.messages), 0)

    def test_message_to_receive_from_pipe_shout_on_message_exception(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        message = {
            "command": "acommand",
            "params": {"key1": "val1"},
            "to": "dummy",
        }
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"SHOUT",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
            b"TESTCHANNEL",
            json.dumps(message).encode(),
        ]
        self.lib.node = mock_node
        self.lib.on_message_received = Mock(side_effect=Exception("Test exception"))

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Messages: %s" % self.messages)

        self.assertEqual(len(self.messages), 0)

    def test_message_to_receive_from_pipe_peer_connected_exception(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        infos = PeerInfos()
        infos.info1 = "info1"
        infos.info2 = "info2"
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"ENTER",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
            json.dumps(infos.to_dict()).encode(),
        ]
        mock_node.peer_address.return_value = "http://192.168.1.1"
        self.lib.node = mock_node
        self.lib.decode_peer_infos = Mock(side_effect=Exception("Test exception"))

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Peers: %s" % self.peers)

        self.assertEqual(len(list(self.peers.keys())), 0)

    def test_message_to_receive_from_pipe_peer_disconnected_exception(self):
        self.init_lib()
        self.lib._PyreBus__bus_name = "TESTBUS"
        self.lib._PyreBus__bus_channel = "TESTCHANNEL"
        ident = "12345678-1234-5678-1234-567812345678"
        infos = PeerInfos()
        infos.info1 = "info1"
        infos.info2 = "info2"
        mock_node = Mock()
        mock_node.recv.return_value = [
            b"EXIT",
            b"\x12\x34\x56\x78" * 4,
            b"TESTBUS",
        ]
        self.lib.node = mock_node
        self.lib.on_peer_disconnected = Mock(side_effect=Exception("Test exception"))

        self.assertTrue(self.lib._message_to_receive_from_pipe())
        logging.debug("Online: %s" % self.online)

        self.assertEqual(len(list(self.peers.keys())), 0)

    def test_message_to_send_to_pipe_whisper(self):
        self.init_lib()
        peer_infos = PeerInfos()
        peer_infos.uuid = "123-456-789"
        peer_infos.ident = "12345678-1234-5678-1234-567812345678"
        message = {
            "command": "my_command",
            "to": "recipient",
            "sender": "mod1",
            "params": {"param1": "value1"},
            "peer_infos": peer_infos.to_dict(),
        }
        mock_pipeout = Mock()
        mock_pipeout.recv.return_value = json.dumps(message).encode()
        self.lib.pipe_out = mock_pipeout
        mock_node = Mock()
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_send_to_pipe())

        self.assertFalse(mock_node.shout.called)
        mock_node.whisper.assert_called()
        call_args = mock_node.whisper.call_args[0]
        self.assertEqual(call_args[0], UUID("12345678-1234-5678-1234-567812345678"))
        self.assertDictEqual(
            json.loads(call_args[1].decode("utf-8")),
            {
                "to": message["to"],
                "timeout": 5.0,
                "sender": "mod1",
                "params": message["params"],
                "command": message["command"],
                "command_uuid": None,
            },
        )

    def test_message_to_send_to_pipe_shout(self):
        self.init_lib()
        message = {
            "command": "my_command",
            "to": "recipient",
            "sender": "mod1",
            "params": {"param1": "value1"},
        }
        mock_pipeout = Mock()
        mock_pipeout.recv.return_value = json.dumps(message).encode()
        self.lib.pipe_out = mock_pipeout
        mock_node = Mock()
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_send_to_pipe())

        self.assertFalse(mock_node.whisper.called)
        mock_node.shout.assert_called()
        call_args = mock_node.shout.call_args[0]
        self.assertIsNone(call_args[0])
        self.assertDictEqual(
            json.loads(call_args[1].decode("utf-8")),
            {
                "to": message["to"],
                "command": message["command"],
                "params": message["params"],
                "sender": "mod1",
            },
        )

    def test_message_to_send_to_pipe_stop(self):
        self.init_lib()
        mock_pipeout = Mock()
        mock_pipeout.recv.return_value = json.dumps(self.lib.BUS_STOP).encode()
        self.lib.pipe_out = mock_pipeout
        mock_node = Mock()
        self.lib.node = mock_node

        self.assertFalse(self.lib._message_to_send_to_pipe())

        self.assertFalse(mock_node.whisper.called)
        self.assertFalse(mock_node.shout.called)

    def test_message_to_send_to_pipe_exception(self):
        self.init_lib()
        mock_pipeout = Mock()
        mock_pipeout.recv.side_effect = Exception("Test exception")
        self.lib.pipe_out = mock_pipeout
        mock_node = Mock()
        self.lib.node = mock_node

        self.assertTrue(self.lib._message_to_send_to_pipe())

        self.assertFalse(mock_node.whisper.called)
        self.assertFalse(mock_node.shout.called)

    def test_run(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        self.lib.run_once = Mock(side_effect=[True, True, False])

        self.lib.run()

        self.assertEqual(self.lib.run_once.call_count, 3)

    def test_run_external_bus_not_configured(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = False
        self.lib.run_once = Mock(side_effect=[False])

        def set_externabus_configured():
            self.lib._PyreBus__externalbus_configured = True

        t = Timer(1.0, set_externabus_configured)
        t.start()

        self.lib.run()

        self.assertEqual(self.lib.run_once.call_count, 1)

    def test_run_exception(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        self.lib.run_once = Mock(side_effect=[Exception("Test exception"), False])

        self.lib.run()

        self.assertEqual(self.lib.run_once.call_count, 2)

    def test_broadcast_message(self):
        self.init_lib()
        self.lib._send_message = Mock()

        self.lib._broadcast_message(MessageRequest())

        self.lib._send_message.assert_called_once()

    def test_send_message(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = True
        mock_pipein = Mock()
        self.lib.pipe_in = mock_pipein
        message = MessageRequest()
        message.event = "dummy.test.event"

        self.lib._send_message(message)

        mock_pipein.send.assert_called_with(
            json.dumps(message.to_dict()).encode("utf8")
        )

    def test_send_message_external_bus_not_configured(self):
        self.init_lib()
        self.lib._PyreBus__externalbus_configured = False
        mock_pipein = Mock()
        self.lib.pipe_in = mock_pipein
        message = MessageRequest()
        message.event = "dummy.test.event"

        self.lib._send_message(message)

        self.assertFalse(mock_pipein.send.called)


if __name__ == "__main__":
    # coverage run --include="**/backend/**/*.py" --concurrency=thread test_cleepbus.py; coverage report -m -i
    unittest.main()
