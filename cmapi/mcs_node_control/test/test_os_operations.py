import sys
import os
import time
import unittest

from mcs_node_control.models.systemd import SystemdServices, SystemdStatus
from mcs_node_control.models.systemd import dispatcher as os_dispatcher
from mcs_node_control.models.os_operations import OSOperations
from mcs_node_control.models.misc import *


LOADDBRM_SERVICE = 'mcs-loadbrm.service'
CONTROLLERNODE_SERVICE = 'mcs-controllernode.service'
# unknown service
UNKNOWN_SERVICE = 'unknown_service'
SYSTEMCTL = 'sudo systemctl'


class BaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        if SystemdStatus().is_running(CONTROLLERNODE_SERVICE):
            self.controller_node_cmd = 'start'
        else:
            self.controller_node_cmd = 'stop'
        # prevent to get 'start-limit-hit' systemd error, see MCOL-5186
        os.system(f'{SYSTEMCTL} reset-failed')
        return super().setUp()

    def tearDown(self) -> None:
        os.system(
            f'{SYSTEMCTL} {self.controller_node_cmd} {CONTROLLERNODE_SERVICE}'
        )
        return super().tearDown()

class SystemdTest(BaseTestCase):

    def test_systemd_status_start(self):
        os.system(f'{SYSTEMCTL} stop {LOADDBRM_SERVICE}')
        self.assertFalse(SystemdStatus().is_running(LOADDBRM_SERVICE))
        result = SystemdServices().start(LOADDBRM_SERVICE)
        self.assertTrue(result)

        os.system(f'{SYSTEMCTL} stop {CONTROLLERNODE_SERVICE}')
        self.assertFalse(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))
        result = SystemdServices().start(CONTROLLERNODE_SERVICE)
        self.assertTrue(result)
        self.assertTrue(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))

    def test_systemd_status_stop(self):
        os.system(f'{SYSTEMCTL} start {CONTROLLERNODE_SERVICE}')
        self.assertTrue(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))
        self.assertTrue(SystemdServices().stop(CONTROLLERNODE_SERVICE))
        self.assertFalse(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))

    def test_systemd_status_restart(self):
        os.system(f'{SYSTEMCTL} start {CONTROLLERNODE_SERVICE}')
        self.assertTrue(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))
        self.assertTrue(SystemdServices().restart(CONTROLLERNODE_SERVICE))
        self.assertTrue(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))

        os.system(f'{SYSTEMCTL} stop {CONTROLLERNODE_SERVICE}')
        self.assertFalse(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))
        self.assertTrue(SystemdServices().restart(CONTROLLERNODE_SERVICE))
        self.assertTrue(SystemdStatus().is_running(CONTROLLERNODE_SERVICE))


class OSOperationsTest(BaseTestCase):

    def test_osoperations_apply(self):
        os.system(f'{SYSTEMCTL} stop {CONTROLLERNODE_SERVICE}')
        kwargs = {'use_sudo': True,
                  'dispatcher': os_dispatcher,
                  'config_root': current_config_root(),
                  'timeout': 0,}
        result = list(OSOperations().apply(
            [
                {'operation': 'start', 'service': CONTROLLERNODE_SERVICE},
                {'operation': 'stop', 'service': CONTROLLERNODE_SERVICE},
                {'operation': 'start', 'service': CONTROLLERNODE_SERVICE},
                {'operation': 'restart', 'service': CONTROLLERNODE_SERVICE}
            ],
            **kwargs
        ))
        self.assertEqual(len(result), 0)

        os.system(f'{SYSTEMCTL} stop {CONTROLLERNODE_SERVICE}')
        result = list(OSOperations().apply(
            [
                {'operation': 'start', 'service': UNKNOWN_SERVICE},
                {'operation': 'stop', 'service': UNKNOWN_SERVICE},
                {'operation': 'start', 'service': UNKNOWN_SERVICE},
                {'operation': 'restart', 'service': UNKNOWN_SERVICE}
            ],
            **kwargs
        ))
        self.assertEqual(len(result), 4)


if __name__ == '__main__':
    unittest.main()
