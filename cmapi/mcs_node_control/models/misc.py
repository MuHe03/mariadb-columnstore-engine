import logging
from pathlib import Path

from lxml import etree

from cmapi_server.constants import (
    DEFAULT_MCS_CONF_PATH, MCS_DATA_PATH, MCS_MODULE_FILE_PATH,
)


module_logger = logging.getLogger()


def read_module_id():
    """Retrieves module ID from MCS_MODULE_FILE_PATH.

    :rtype: int : seconds
    """
    module_file = Path(MCS_MODULE_FILE_PATH)
    return int(module_file.read_text()[2:])


def set_module_id(module_id: int = 1):
    """Sets current module ID from MCS_MODULE_FILE_PATH.

    :rtype: int : seconds

    """
    module_file = Path(MCS_MODULE_FILE_PATH)
    return module_file.write_text(f'pm{module_id}\n')


def get_dbroots_list(path: str = MCS_DATA_PATH):
    """searches for services

    The method returns numeric ids of dbroots available.

    :rtype: generator of ints
    """
    func_name = 'get_dbroots_list'
    path = Path(path)
    for child in path.glob('data[1-9]*'):
        dir_list = str(child).split('/') # presume Linux only
        dbroot_id = int(''.join(list(filter(str.isdigit, dir_list[-1]))))
        module_logger.debug(f'{func_name} The node has dbroot {dbroot_id}')
        yield dbroot_id


def get_workernodes_list(root):
    """Get workernodes list

    Returns a list of network address of all workernodes this is an equivalent of all nodes.

    :rtype: set of strings
    """
    func_name = 'get_workernodes_list'
    addrs = set()
    ports = []
    num = 1
    while True:
        node = root.find(f"./DBRM_Worker{num}/IPAddr")
        if node is None:
            break
        if node.text != "0.0.0.0":
            addrs.add(node.text)
            try:
                port = int(root.find(f"./DBRM_Worker{num}/Port").text)
            except ValueError:
                module_logger.error(f'{func_name} Invalid port value {port}')
                port = 8700
            ports.append(8700)
            ports[len(addrs)-1] = port
        num += 1

    for addr, port in zip(addrs, ports):
        yield {'IPAddr': addr, 'Port': port}


def get_dbrm_master(root=None):
    return {'IPAddr': root.find("./DBRM_Controller/IPAddr").text,
            'Port': root.find("./DBRM_Controller/Port").text}


def current_config_root(config_filename: str = DEFAULT_MCS_CONF_PATH):
    """Retrievs current configuration

    Read the config and returns Element

    :rtype: lxml.Element
    """
    parser = etree.XMLParser(load_dtd=True)
    tree = etree.parse(config_filename, parser=parser)
    return tree.getroot()


def dequote(s):
    """
    If a string has single or double quotes around it, remove them.
    Make sure the pair of quotes match.
    If a matching pair of quotes is not found, return the string unchanged.
    """
    if (len(s) >= 2 and s[0] == s[-1]) and s.startswith(("'", '"')):
        return s[1:-1]
    return s
