"""Module contains base process dispatcher class implementation.

Formally this is must have interface for subclasses.
"""

import logging
import subprocess
from typing import Tuple


class BaseDispatcher:
    """Class with base interfaces for dispatchers."""

    @staticmethod
    def exec_command(command: str, silent: bool = False) -> Tuple[bool, str]:
        """Run subpocess.

        :param command: command to run
        :type command: str
        :param silent: prevent error logs on non-zero exit status,
                       defaults to False
        :type silent: bool, optional
        :return: tuple with success status and output from finished command
        :rtype: Tuple[bool, str]
        """
        try:
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=True, check=True, encoding='utf-8'
            )
        except subprocess.CalledProcessError as exc:
            if not silent:
                logging.error(
                    f'Calling "{exc.cmd}" finished with non zero return code: '
                    f'"{exc.returncode}" and stderr+stdout "{exc.output}".'
                )
            return False, exc.output
        return True, result.stdout

    @staticmethod
    def noop(*args, **kwargs) -> bool:
        """No operation. TODO: looks like useless."""
        return True

    @classmethod
    def is_service_running(cls, service: str, use_sudo: bool) -> bool:
        """Check if systemd proceess/service is running."""
        raise NotImplementedError

    @classmethod
    def start(cls, service: str, is_primary: bool, use_sudo: bool) -> bool:
        """Start process/service."""
        raise NotImplementedError

    @classmethod
    def stop(cls, service: str, is_primary: bool, use_sudo: bool) -> bool:
        """Stop process/service."""
        raise NotImplementedError

    @classmethod
    def restart(cls, service: str, is_primary: bool, use_sudo: bool) -> bool:
        """Restart process/service."""
        raise NotImplementedError

    @classmethod
    def reload(cls, service: str, is_primary: bool, use_sudo: bool) -> bool:
        """Reload process/service."""
        raise NotImplementedError
