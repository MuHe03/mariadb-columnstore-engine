import logging
import subprocess
import os.path


MCS_INSTALL_BIN = '/usr/bin'


module_logger = logging.getLogger()


class SystemdStatus():
    """ Check the status of a service on the system."""
    def is_running(self, service: str = "Unknown_service",
                   use_sudo: bool=True):
        """Returns True if the service is running.

        : param operations: str service

        :rtype: bool
        """
        status = "systemctl --state=running"
        if use_sudo:
            status = "sudo " + status
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
        return False if str(result.stdout).find(service) == -1 else True


class SystemdServices():
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

        # TODO: remove fast fix
        if service == 'mcs-exemgr':
            exemgr_binary_path = os.path.join(MCS_INSTALL_BIN, 'ExeMgr')
            if not os.path.exists(exemgr_binary_path):
                # skip exemgr
                return True

        if SystemdStatus().is_running(service, use_sudo):
            return True
        if service == 'mcs-workernode':
            # pass in arg to run DBRM_Worker1 or DBRM_Worker2
            if is_primary:
                start = f"systemctl start {service}@1.service"
                enable = f"systemctl enable mcs-workernode@1.service"

                if use_sudo:
                    enable = "sudo " + enable
                try:
                    subprocess.run(enable, shell=True,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                except:
                    # enabling service is not critical, just log failure
                    module_logger.warning(f"failed to enable workernode")
                    pass
            else:
                start = f"systemctl start {service}@2.service"
        else:
            start = f"systemctl start {service}"

        if use_sudo:
            start = "sudo " + start
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
            return SystemdStatus().is_running(service, use_sudo)
        else:
            return True


    def stop(self, service: str="Unknown_service",
             is_primary: bool=True,
             use_sudo: bool=True):
        """Stops systemd service.

        : param operations: str service

        :rtype: bool
        """
        func_name = 'stop'

        # TODO: remove fast fix
        if service == 'mcs-exemgr':
            exemgr_binary_path = os.path.join(MCS_INSTALL_BIN, 'ExeMgr')
            if not os.path.exists(exemgr_binary_path):
                # skip exemgr
                return True

        if service == 'mcs-workernode':
            # stop any instance of mcs-workernode
            stop = f"systemctl stop {service}@1 {service}@2"
            disable = f"systemctl disable mcs-workernode@1.service"

            if use_sudo:
                disable = "sudo " + disable
            try:
                subprocess.run(disable, shell=True,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except:
                # disabling service is not critical, just log failure
                module_logger.warning(f"failed to disable workernode")
                pass
        else:
            stop = f"systemctl stop {service}"

        if use_sudo:
            stop = "sudo " + stop
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
        return not SystemdStatus().is_running(service, use_sudo)


    def restart(self, service: str = "Unknown_service",
                is_primary: bool=True,
                use_sudo: bool=True):
        """Restarts systemd service.

        : param operations: str service

        :rtype: bool
        """
        func_name = 'restart'

        # TODO: remove fast fix
        if service == 'mcs-exemgr':
            exemgr_binary_path = os.path.join(MCS_INSTALL_BIN, 'ExeMgr')
            if not os.path.exists(exemgr_binary_path):
                # skip exemgr
                return True

        restart = f"systemctl restart {service}"
        if use_sudo:
            restart = "sudo " + restart
        module_logger.debug(f'{func_name} running {restart}')
        try:
            result = subprocess.run(restart, shell = True,
                            stdout = subprocess.DEVNULL,
                            stderr = subprocess.DEVNULL)
        except (OSError, ValueError):
            module_logger.error(f"{func_name} Cannot find {restart}.")
            return False
        except subprocess.CalledProcessError:
            module_logger.error(f"{func_name} Error in return code.")
            return False

        if result.returncode != 0:
            return False
        return SystemdStatus().is_running(service, use_sudo)


    # TODO: remove because not used 
    def reload(self, service: str = "Unknown_service",
               is_primary: bool=True,
               use_sudo: bool=True):
        """Reloads systemd service.

        : param operations: str service

        :rtype: bool
        """
        reload = f"systemctl reload {service}"
        if use_sudo:
            reload = "sudo " + reload
        try:
            subprocess.run(reload, shell=True)
        except (OSError, ValueError):
            return False
        except subprocess.CalledProcessError:
            return False

        return SystemdStatus().is_running(service, use_sudo)

dispatcher = {'start': SystemdServices().start,
              'stop': SystemdServices().stop,
              'restart': SystemdServices().restart,
              'noop': SystemdServices().noop,}
