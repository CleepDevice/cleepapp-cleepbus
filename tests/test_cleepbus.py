import unittest
import logging
import sys
sys.path.append('../')
from backend.cleepbus import Cleepbus
from raspiot.utils import InvalidParameter, MissingParameter, CommandError, Unauthorized
from raspiot.libs.tests import session
import os
import time
from mock import Mock

class TestActions(unittest.TestCase):

    def setUp(self):
        self.session = session.Session(logging.CRITICAL)
        _cleepbus = Cleepbus
        self.module = self.session.setup(_cleepbus)

    def tearDown(self):
        self.session.clean()

if __name__ == "__main__":
    unittest.main()
    
