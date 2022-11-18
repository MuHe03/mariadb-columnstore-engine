"""Module contains constants values for cmapi, failover and other .py files.

TODO: move main constant paths here and replace in files in next releases.
"""
import os

# default MARIADB ColumnStore config path
MCS_ETC_PATH = '/etc/columnstore'
DEFAULT_MCS_CONF_PATH = os.path.join(MCS_ETC_PATH, 'Columnstore.xml')

# default Storage Manager config path
DEFAULT_SM_CONF_PATH = os.path.join(MCS_ETC_PATH, 'storagemanager.cnf')

# MCSDATADIR (in mcs engine code) and related paths
MCS_DATA_PATH = '/var/lib/columnstore'
MCS_MODULE_FILE_PATH = os.path.join(MCS_DATA_PATH, 'local/module')
EM_PATH_SUFFIX = 'data1/systemFiles/dbrm'
MCS_EM_PATH = os.path.join(MCS_DATA_PATH, EM_PATH_SUFFIX)
MCS_BRM_CURRENT_PATH = os.path.join(MCS_EM_PATH, 'BRM_saves_current')
S3_BRM_CURRENT_PATH = os.path.join(EM_PATH_SUFFIX, 'BRM_saves_current')
# keys file for CEJ password encryption\decryption
# (CrossEngineSupport section in Columnstore.xml)
MCS_SECRETS_FILE_PATH = os.path.join(MCS_DATA_PATH, '.secrets')

# CMAPI SERVER
CMAPI_CONFIG_FILENAME = 'cmapi_server.conf'
CMAPI_ROOT_PATH = os.path.dirname(__file__)
CMAPI_LOG_CONF_PATH =  os.path.join(CMAPI_ROOT_PATH, 'cmapi_logger.conf')
# path to CMAPI default config
CMAPI_DEFAULT_CONF_PATH = os.path.join(CMAPI_ROOT_PATH, CMAPI_CONFIG_FILENAME)
# CMAPI config path
CMAPI_CONF_PATH = os.path.join(MCS_ETC_PATH, CMAPI_CONFIG_FILENAME)

# TOTP secret key
SECRET_KEY = 'MCSIsTheBestEver'  # not just a random string! (base32)


# network constants
LOCALHOSTS = ('localhost', '127.0.0.1', '::1')

CMAPI_INSTALL_PATH = '/usr/share/columnstore/cmapi/'
CMAPI_PYTHON_BIN = os.path.join(CMAPI_INSTALL_PATH, "python/bin/python3")
CMAPI_PYTHON_DEPS_PATH = os.path.join(CMAPI_INSTALL_PATH, "deps")
CMAPI_PYTHON_BINARY_DEPS_PATH = os.path.join(CMAPI_PYTHON_DEPS_PATH, "bin")
