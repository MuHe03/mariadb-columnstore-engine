import configparser
import logging
import subprocess

from cmapi_server.constants import CMAPI_CONF_PATH
from mcs_node_control.models.misc import dequote


module_logger = logging.getLogger()


config = configparser.ConfigParser()
config.read(CMAPI_CONF_PATH)
try:
    dispatcher_section = config['Dispatcher']
except KeyError:
    dispatcher_section = None
dispatcher_path = ''
if dispatcher_section is not None:
    try:
        dispatcher_path = dequote(dispatcher_section['path'])
    except KeyError:
        dispatcher_path = ''

if len(dispatcher_path) == 0:
    module_logger.debug(f'The configuration lacks Dispatcher.path setting to use Container dispatcher')
    sys.exit(1)

services_dictionary = {'mcs-storagemanager': 'StorageManager',
                       'mcs-loadbrm': 'mcs-loadbrm.py',
                       'mcs-workernode': 'workernode',
                       'mcs-controllernode': 'controllernode',
                       'mcs-primproc': 'PrimProc',
                       'mcs-exemgr': 'ExeMgr',
                       'mcs-writeengineserver': 'WriteEngineServ',
                       'mcs-ddlproc': 'DDLProc',
                       'mcs-dmlproc': 'DMLProc',}


class ContainerStatus():
    """ Check the status of a service on the system."""
    def is_running(self, service: str = "Unknown_service"):
        """Returns True if the service is running.

        : param operations: str service

        :rtype: bool
        """
        proc_name = services_dictionary.get(service, 'noop314159')
        status = f"pgrep -x {proc_name}"
        try:
            result = subprocess.run(status,
                                     shell=True,
                                     stdout=subprocess.PIPE)
        except (OSError, ValueError):
            return False
        except subprocess.CalledProcessError:
            return False

        if result.returncode != 0:
            return False
        return True


def get_services_list():
    for skey in services_dictionary.keys():
        if skey not in ['mcs-loadbrm']:
            yield skey


class ContainerServices():
    """Manipulates with systemd services."""
    def noop(self, service: str = "Unknown_service",
             is_primary: bool=True,
             use_sudo: bool=True):
        return True


    """Manipulates with systemd services."""
    def start(self, service: str="Unknown_service",
              is_primary: bool=True,
              use_sudo: bool=True):
        """Starts systemd service.

        : param operations: str service

        :rtype: bool
        """
        func_name = 'start'
        if ContainerStatus().is_running(service):
            return True
        start = f"{dispatcher_path} start {service} {int(is_primary)}"
        module_logger.debug(f'{func_name} running {start}')
        try:
            subprocess.run(start, shell=True,
                           stdout=subprocess.DEVNULL,
                           stderr = subprocess.DEVNULL)
        except (OSError, ValueError):
            module_logger.error(f"{func_name} Cannot find {start}.")
            return False
        except subprocess.CalledProcessError:
            module_logger.error(f"{func_name} Error in return code.")
            return False

        # This dispatcher checks all services at once.
        if service == 'mcs-dmlproc' and is_primary is True:
            for sname in get_services_list():
                if not ContainerStatus().is_running(sname):
                    module_logger.error(f"{func_name} {sname} is not working.")
                    return False
        elif service == 'mcs-ddlproc' and is_primary is False:
            for sname in get_services_list():
                if not ContainerStatus().is_running(sname) \
and sname not in ['mcs-controllernode', 'mcs-dmlproc']:
                    module_logger.error(f"{func_name} {sname} is not working.")
                    return False
        return True


    def stop(self, service: str = "Unknown_service",
             is_primary: bool=True,
             use_sudo: bool=True):
        """Stops systemd service.

        : param operations: str service

        :rtype: bool
        """
        func_name = 'stop'
        stop = f"{dispatcher_path} stop {service} {int(is_primary)}"
        module_logger.debug(f'{func_name} running {stop}')
        try:
            result = subprocess.run(stop, shell = True,
                            stdout = subprocess.DEVNULL,
                            stderr = subprocess.DEVNULL)
        except (OSError, ValueError):
            module_logger.error(f"{func_name} Cannot find {stop}.")
            return False
        except subprocess.CalledProcessError:
            module_logger.error(f"{func_name} Error in return code.")
            return False

        if result.returncode != 0:
            return False

        # This dispatcher checks all services at once.
        if is_primary is True and service == 'mcs-controllernode':
            for sname in get_services_list():
                if ContainerStatus().is_running(sname):
                    module_logger.error(f"{func_name} {sname} is still working.")
                    return False
        elif is_primary is False and service == 'mcs-workernode':
            for sname in get_services_list():
                if ContainerStatus().is_running(sname):
                    module_logger.error(f"{func_name} {sname} is still working.")
                    return False

        return True

    def restart(self, service: str = "Unknown_service",
             is_primary: bool=True,
             use_sudo: bool=True):
        """Restarts systemd service.

        : param operations: str service

        :rtype: bool
        """
        func_name = 'restart'
        stop = f"{dispatcher_path} stop {service} {int(is_primary)}"
        start = f"{dispatcher_path} start {service} {int(is_primary)}"
        module_logger.debug(f'{func_name} running {stop}')
        try:
            result = subprocess.run(stop, shell = True,
                            stdout = subprocess.DEVNULL,
                            stderr = subprocess.DEVNULL)
        except (OSError, ValueError):
            module_logger.error(f"{func_name} Cannot find {stop}.")
            return False
        except subprocess.CalledProcessError:
            module_logger.error(f"{func_name} Error in return code.")
            return False

        if result.returncode != 0:
            module_logger.debug(f"{func_name} Error in return code.")

        module_logger.debug(f'{func_name} running {start}')
        try:
            subprocess.run(start, shell=True,
                           stdout=subprocess.DEVNULL,
                           stderr = subprocess.DEVNULL)
        except (OSError, ValueError):
            module_logger.error(f"{func_name} Cannot find {start}.")
            return False
        except subprocess.CalledProcessError:
            module_logger.error(f"{func_name} Error in return code.")
            return False

        # Workaround for oneshot in mcs-loadbrm
        if 'mcs-loadbrm' not in service:
            return ContainerStatus().is_running(service)
        else:
            return True


dispatcher = {'restart':ContainerServices().restart,
              'start': ContainerServices().start,
              'stop': ContainerServices().stop,
              'noop': ContainerServices().noop,}
