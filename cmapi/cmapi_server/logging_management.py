import json
import logging
import logging.config

import cherrypy

from cmapi_server.constants import CMAPI_LOG_CONF_PATH


class AddIpFilter(logging.Filter):
    """Filter to add IP address to logging record."""
    def filter(self, record):
        record.ip = cherrypy.request.headers.get('Remote-Addr', '127.0.0.1')
        return True


def dict_config(config_filepath: str):
    with open(config_filepath, 'r', encoding='utf-8') as json_config:
        config_dict = json.load(json_config)
    logging.config.dictConfig(config_dict)


def config_cmapi_server_logging():
    #reconfigure cherrypy.access log message format
    cherrypy._cplogging.LogManager.access_log_format = (
        '{h} ACCESS "{r}" code {s}, bytes {b}, user-agent "{a}"'
    )
    dict_config(CMAPI_LOG_CONF_PATH)
