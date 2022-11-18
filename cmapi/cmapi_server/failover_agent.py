'''
This class implements the interface used by the failover module to notify
the cluster of events like node-up / node-down, etc.
'''

import requests
requests.packages.urllib3.disable_warnings()
import logging
import time
from failover.agent_comm import AgentBase
from cmapi_server import helpers, node_manipulation
from cmapi_server.controllers.endpoints import os_dispatcher  # todo, we should make this a global somewhere...
from mcs_node_control.models.node_config import NodeConfig
from mcs_node_control.models.os_operations import OSOperations


logger = logging.getLogger(__file__)


class FailoverAgent(AgentBase):

    def activateNodes(
        self, nodes, input_config_filename=None, output_config_filename=None,
        test_mode=False
    ):
        logger.info(f'FA.activateNodes():  activating nodes: {nodes}')
        new_node_count = 0
        for node in nodes:
            try:
                logger.info(f'FA.activateNodes(): adding node {node}')
                node_manipulation.add_node(
                    node, input_config_filename, output_config_filename,
                    test_mode=test_mode
                )
                new_node_count += 1
            except Exception:
                logger.error(f'FA.activateNodes(): failed to add node {node}')
                raise
        return new_node_count


    def deactivateNodes(self, nodes, input_config_filename = None, output_config_filename = None, test_mode = False):
        logger.info(f"FA.deactivateNodes():  deactivating nodes: {nodes}")

        # to save a little typing in testing
        kwargs = {
            "cs_config_filename": input_config_filename,
            "input_config_filename" : input_config_filename,
            "output_config_filename" : output_config_filename,
            "test_mode" : test_mode
        }

        removed_node_count = 0
        for node in nodes:
            try:
                logger.info(f"FA.deactivateNodes(): deactivating node {node}")
                node_manipulation.remove_node(node, deactivate_only=True, **kwargs)
                removed_node_count += 1
            except Exception as e:
                logger.error(f"FA.deactivateNodes(): failed to deactivate node {node}, got {str(e)}")
                raise
        return removed_node_count


    # the 'hack' parameter is a placeholder.  When run by agent_comm, this function gets a first parameter
    # of ().  When that is the input_config_filename, that's bad.  Need to fix.
    def movePrimaryNode(self, hack, input_config_filename = None, output_config_filename = None, test_mode = False):
        logger.info(f"FA.movePrimaryNode(): moving primary node functionality")

        # to save a little typing in testing
        kwargs = {
            "cs_config_filename": input_config_filename,
            "input_config_filename" : input_config_filename,
            "output_config_filename" : output_config_filename,
            "test_mode" : test_mode
        }

        try:
            node_manipulation.move_primary_node(**kwargs)
        except Exception as e:
            logger.error(f"FA.movePrimaryNode(): failed to move primary node, got {str(e)}")
            raise


    def enterStandbyMode(self, test_mode = False):
        nc = NodeConfig()
        node_name = nc.get_module_net_address(nc.get_current_config_root())
        logger.info(f"FA.enterStandbyMode(): shutting down this node ({node_name})")
        oso = OSOperations()

        # this gets retried by the caller on error
        if not test_mode:
            msgs = list(oso.shutdown_node(os_dispatcher=os_dispatcher))
        else:
            msgs = []
        if len(msgs) > 0:
            logger.error(f"FA.enterStandbyMode(): caught this error: {msgs}")
        else:
            logger.info("FA.enterStandbyMode(): successful shutdown")

    def raiseAlarm(self, msg):
        logger.critical(msg)


    # The start/commit/rollback transaction fcns use the active list to decide which
    # nodes to send to; when we're adding a node the new node isn't in the active list yet
    # extra_nodes gives us add'l hostnames/addrs to send the transaction to.
    # Likewise for removing a node.  Presumably that node is not reachable, so must be
    # removed from the list to send to.
    def startTransaction(self, extra_nodes = [], remove_nodes = []):
        got_txn = False
        count = 0
        while not got_txn:
            msg = None
            try:
                (got_txn, txn_id, nodes) = helpers.start_transaction(extra_nodes = extra_nodes, remove_nodes = remove_nodes)
            except Exception as e:
                got_txn = False
                msg = f"FA.start_transaction(): attempt #{count+1}, failed to get a transaction, got {str(e)}"

            if not got_txn:
                if msg is None:
                    msg = f"FA.start_transaction(): attempt #{count+1}, failed to get a transaction"
                if count < 5:
                    logger.info(msg)
                else:
                    logger.error(msg)
                time.sleep(1)
            count += 1
        logger.info(f"FA.startTransaction(): started transaction {txn_id}")
        return (txn_id, nodes)


    # These shouldn't throw for now
    def commitTransaction(self, txn_id, nodes, **kwargs):
        try:
            helpers.update_revision_and_manager(**kwargs)
            helpers.broadcast_new_config(nodes = nodes, **kwargs)
            helpers.commit_transaction(txn_id, nodes = nodes)
        except Exception as e:
            logger.error(f"FA.commitTransaction(): failed to commit transaciton {txn_id}, got {str(e)}")
        else:
            logger.info(f"FA.commitTransaction(): committed transaction {txn_id}")


    def rollbackTransaction(self, txn_id, nodes):
        try:
            helpers.rollback_transaction(txn_id, nodes = nodes)
        except Exception as e:
            logger.error(f"FA.rollbackTransaction(): failed to rollback transaction {txn_id}, got {str(e)}")
        else:
            logger.info(f"FA.rollbackTransaction(): rolled back transaction {txn_id})")
