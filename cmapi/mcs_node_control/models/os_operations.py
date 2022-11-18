import logging
import socket
import subprocess
from configparser import ConfigParser
from time import sleep

from cmapi_server.constants import CMAPI_CONF_PATH
from mcs_node_control.models.dbrm import DBRM
from mcs_node_control.models.misc import (
    get_workernodes_list, current_config_root, get_dbrm_master, dequote
)
from mcs_node_control.models.dbrm_socket import SOCK_TIMEOUT
from mcs_node_control.models.process import Process


CONTROLLER_MAX_DELAY = 30


module_logger = logging.getLogger()


class OSOperations:
    """Class to run OS level operations.

    Class to run OS level operations,
    e.g. re/-start or stop systemd services, run executable.
    """

    # Note: the container.sh script doesn't currently honor
    # the actions run by this function. Changes here should be reflected
    # in container.sh, until we rewrite how services are managed
    # in the container environment.
    def apply(self, operations: list = None,
              use_sudo=None,
              dispatcher=None,
              config_root=None,
              timeout=0,
              is_primary=False,
              **kwargs):
        """Applies the list of the operations.

        Executes operations using different backends.
        When timeout > 0 this method sleeps timeout secs.
        The cluster has been already set to readonly.

        Note: We don't honor timeout yet.

        : param operations: list of dicts
        """
        func_name = 'apply'
        if dispatcher is None:
            module_logger.error(
                f'{self.apply.__name__} There is no dispatcher to '
                'execute operations.'
            )
            yield {'error': 'No dispatcher defined.'}
            return

        if config_root is None:
            module_logger.error(
                f'{self.apply.__name__} There is no XML root to '
                'execute operations.'
            )
            yield {'error': 'No XML root.'}
            return

        for oper in operations:
            op_name = oper.get("operation", "noop")
            service_name = oper.get("service", '')

            if service_name == 'mcs-controllernode' and op_name == 'start':
                module_logger.debug(
                    f'{func_name} Waiting for all workernodes to come up '
                    'before starting controllernode on the primary.'
                )
                check_to = CONTROLLER_MAX_DELAY
                workernodes = list(get_workernodes_list(config_root))
                while check_to > 0 and len(workernodes) > 0:
                    module_logger.debug(f'{func_name} Trying...')
                    success = False
                    for num, worker in enumerate(workernodes):
                        try:
                            sock = socket.socket(
                                socket.AF_INET, socket.SOCK_STREAM
                            )
                            sock.settimeout(SOCK_TIMEOUT)
                            result = sock.connect_ex(
                                (worker['IPAddr'], worker['Port'])
                            )
                            if result == 0:
                                del workernodes[num]
                                success = True
                        except socket.timeout:
                            pass
                        else:
                            sock.close()
                    if len(workernodes) > 0:
                        sleep(1)
                    check_to -= 1

                if len(workernodes) > 0:
                    module_logger.error(
                        f'{func_name} Workernode/-s {str(workernodes)} '
                        f'is/are not reachable after {CONTROLLER_MAX_DELAY} '
                        'seconds. Starting mcs-controllernode anyway.'
                    )

            if ((service_name == 'mcs-dmlproc' or
                 service_name == 'mcs-ddlproc') and op_name == 'start'):
                module_logger.debug(
                    f'{func_name} Waiting for controllernode to come up '
                    'before starting ddlproc/dmlproc on non-primary nodes.'
                )
                check_to = CONTROLLER_MAX_DELAY
                controllernode = get_dbrm_master(config_root)
                success = False
                while check_to > 0:
                    module_logger.debug(f'{func_name} Trying...')
                    try:
                        sock = socket.socket(
                            socket.AF_INET, socket.SOCK_STREAM
                        )
                        sock.settimeout(SOCK_TIMEOUT)
                        result = sock.connect_ex(
                            (
                                controllernode['IPAddr'],
                                int(controllernode['Port'])
                            )
                        )
                        if result == 0:
                            success = True
                            sock.close()
                            break
                    except socket.timeout:
                        pass
                    else:
                        sock.close()
                    if success is False:
                        sleep(1)
                    check_to -= 1

                if not success:
                    module_logger.error(
                        f'{func_name} Controllernode {str(controllernode)} '
                        f'is not reachable after {CONTROLLER_MAX_DELAY} '
                        'seconds. Starting mcs-dmlproc/mcs-ddlproc anyway.'
                    )

            module_logger.debug(
                f'{func_name} Running {op_name} on {service_name}. '
                f'With sudo {use_sudo} and is_primary {is_primary}'
            )

            if dispatcher[op_name](
                service_name, is_primary, use_sudo) is not True:
                yield {'error': 'Error occured running operation.',
                       'service': oper.get('service', 'Unknown servce'),
                       'operation': oper.get('operation')}

            # attempt to run dbbuilder on primary node
            # e.g., s3 was setup after columnstore install
            if (is_primary is True and
                op_name == 'start' and service_name == 'mcs-ddlproc'):
                config = ConfigParser()
                config.read(CMAPI_CONF_PATH)
                dispatcher_name = 'systemd'
                try:
                    dispatcher_section = config['Dispatcher']
                except KeyError:
                    dispatcher_section = None

                if dispatcher_section is not None:
                    try:
                        dispatcher_name = dequote(dispatcher_section['name'])
                    except KeyError:
                        pass

                # TODO: remove conditional once container dispatcher will
                #       use non-root by default
                if dispatcher_name == 'systemd':
                    args = [
                        'su', '-s', '/bin/sh',
                        '-c', '/usr/bin/dbbuilder 7', 'mysql'
                    ]
                else:
                    args = ['/usr/bin/dbbuilder', '7']
                retcode = subprocess.run(args)


    def start_node(self, os_dispatcher,
                   use_sudo:bool=True,
                   is_primary:bool=True):
        """Routine to start a node's services.

        This routine starts services in order.

        """
        kwargs = {
            'use_sudo': use_sudo,
            'dispatcher': os_dispatcher,
            'config_root': current_config_root(),
            'timeout': 0,
            'is_primary': is_primary,
        }

        for msg in self.apply(
            [{'operation': 'start', 'service': 'mcs-workernode'}],
            **kwargs,
        ):
            yield msg
        if is_primary:
            for msg in self.apply(
                [{'operation': 'start', 'service': 'mcs-controllernode'}],
                **kwargs,
            ):
                yield msg
        for msg in self.apply(
            [
                {'operation': 'start', 'service': 'mcs-primproc'},
                {'operation': 'start', 'service': 'mcs-exemgr'},
                {'operation': 'start', 'service': 'mcs-writeengineserver'},
            ],
            **kwargs,
        ):
            yield msg

        if is_primary:
            for msg in self.apply(
                [
                    {'operation': 'start', 'service': 'mcs-dmlproc'},
                    {'operation': 'start', 'service': 'mcs-ddlproc'},
                ],
                **kwargs
            ):
                yield msg

    def shutdown_node(self, os_dispatcher,
                      timeout: int=10,
                      use_sudo=True,
                      is_primary: bool=True,
                      force: bool=False ):
        """Routine to shutdown a node's services.

        This routine shutdowns services in order.

        """
        config_root = current_config_root()
        kwargs = {
            'use_sudo': use_sudo,
            'dispatcher': os_dispatcher,
            'config_root': config_root,
            'timeout': timeout,
            'is_primary': is_primary,
            'force' : force
        }

        if not force and is_primary:
            try:
                with DBRM() as dbrm:
                    dbrm.set_system_state(
                        ["SS_ROLLBACK", "SS_SHUTDOWN_PENDING"]
                    )
            except (ConnectionRefusedError, RuntimeError):
                module_logger.error(
                    "Cannot set SS_ROLLBACK and SS_SHUTDOWN_PENDING"
                )
                force = True

        dmlproc_command = {'operation': 'stop', 'service': 'mcs-dmlproc'}

        commands = [
            {'operation': 'stop', 'service': 'mcs-ddlproc'},
            {'operation': 'stop', 'service': 'mcs-primproc'},
            {'operation': 'stop', 'service': 'mcs-writeengineserver'},
            {'operation': 'stop', 'service': 'mcs-exemgr'},
            {'operation': 'stop', 'service': 'mcs-controllernode'},
            {'operation': 'stop', 'service': 'mcs-workernode'},
            {'operation': 'stop', 'service': 'mcs-storagemanager'},
        ]

        if not force and is_primary:
            module_logger.info(
                f"Waiting for DMLProc to stop on timeout {timeout}"
            )
            while timeout > 0:
                if not Process.check_process_alive("dmlproc"):
                    module_logger.info(f"DMLProc stopped")
                    break
                sleep(1)
                timeout -= 1
                module_logger.info("Waiting for DMLProc to stop")
            else:
                module_logger.error(
                    f'DMLProc did not stopped gracefully within '
                    f'timeout {timeout} using force mode'
                )
                force = True

        if force:
            commands.insert(1, dmlproc_command)

        for msg in self.apply(
            commands,
            **kwargs,
        ):
            yield msg
