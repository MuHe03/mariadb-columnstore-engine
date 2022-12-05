import logging
import time
import threading

from .heartbeater import HeartBeater
from .config import Config
from .heartbeat_history import HBHistory
from .agent_comm import AgentComm


class NodeMonitor:

    _hb = None
    _hbHistory = None
    _agentComm = None
    _die = False
    _config = None
    samplingInterval = 0
    flakyNodeThreshold = 0    # not used yet, KI-V-SS for V1
    _inStandby = False
    _logger = None
    _testMode = False
    myName = "Knucklehead"

    def __init__(
        self, agent=None, config=None, samplingInterval=30,
        flakyNodeThreshold=0.5
    ):
        self._agentComm = AgentComm(agent)
        if config is not None:
            self._config = config
        else:
            self._config = Config()
        self._hbHistory = HBHistory()
        self.samplingInterval = samplingInterval
        self.flakyNodeThreshold = flakyNodeThreshold
        self._logger = logging.getLogger('node_monitor')
        self.myName = self._config.who_am_I()
        #self._logger.info("Using {} as my name".format(self.myName))

    def __del__(self):
        self.stop()

    def start(self):
        self._hb = HeartBeater(self._config, self._hbHistory)
        self._hb.start()
        self._runner = threading.Thread(target=self.monitor)
        self._runner.start()

    def stop(self):
        self._die = True
        self._agentComm.die()
        if not self._testMode:
            self._hb.stop()
        self._runner.join()

    def _removeRemovedNodes(self, desiredNodes):
        self._hbHistory.keepOnlyTheseNodes(desiredNodes)

    def _pickNewActor(self, nodes):
        if not nodes:
            return
        if self.myName == nodes[0]:
            self._isActorOfCohort = True
        else:
            self._isActorOfCohort = False

    def _chooseNewPrimaryNode(self):
        self._agentComm.movePrimaryNode()

    def monitor(self):
        while not self._die:
            try:
                self._logger.info('Starting the monitor logic')
                self._monitor()
            except Exception:
                self._logger.error(
                    f'monitor() caught an exception.',
                    exc_info=True
                )
            if not self._die:
                time.sleep(1)
        self._logger.info("node monitor logic exiting normally...")

    def _monitor(self):
        """
        This works like the main loop of a game.
        1) check current state
        2) identify the differences
        3) update based on the differences
        """

        (desiredNodes, activeNodes, inactiveNodes) = self._config.getAllNodes()
        self._pickNewActor(activeNodes)

        logged_idleness_msg = False
        logged_active_msg = False
        inStandbyMode = False
        while not self._die:
            # these things would normally go at the end of the loop; doing it here
            # to reduce line count & chance of missing something as we add more code
            oldActiveNodes = activeNodes
            wasActorOfCohort = self._isActorOfCohort
            time.sleep(1)

            # get config updates
            (desiredNodes, activeNodes, inactiveNodes) = self._config.getAllNodes()
            self.myName = self._config.who_am_I()
            self.primaryNode = self._config.getPrimaryNode()

            # remove nodes from history that have been removed from the cluster
            self._removeRemovedNodes(desiredNodes)

            # if there are less than 3 nodes in the cluster, do nothing
            if len(desiredNodes) < 3:
                if not logged_idleness_msg:
                    self._logger.info(
                        'Failover support is inactive; '
                        'requires at least 3 nodes and a shared storage system'
                    )
                    logged_idleness_msg = True
                    logged_active_msg = False
            elif not logged_active_msg:
                self._logger.info(
                    'Failover support is active, '
                    f'monitoring nodes {desiredNodes}'
                )
                logged_active_msg = True
                logged_idleness_msg = False

            # nothing to do in this case
            if len(desiredNodes) == 1:
                continue

            # has this node been reactivated?
            if self.myName in activeNodes:
                self._inStandby = False

            # has it been deactivated?
            else:
                self._inStandby = True
                continue    # wait to be activated

            # send heartbeats
            self._hb.sendHeartbeats()

            # decide if action is necessary based on config changes

            # get the list of nodes no longer responding to heartbeats
            # V1: only remove a node that hasn't responded to any pings in the sampling period
            deactivateSet = set()
            for node in activeNodes:
                if node == self.myName:
                    continue
                history = self._hbHistory.getNodeHistory(node, self.samplingInterval, HBHistory.GoodResponse)
                noResponses = [ x for x in history if x == HBHistory.NoResponse ]
                if len(noResponses) == self.samplingInterval:
                    deactivateSet.add(node)

            # get the list of nodes that have started responding
            # reactivate live nodes that have begun responding to heartbeats
            # V1: only reactivate a node if we have good responses for the whole sampling period
            activateSet = set()
            for node in inactiveNodes:
                history = self._hbHistory.getNodeHistory(node, self.samplingInterval, HBHistory.NoResponse)
                goodResponses = [ x for x in history if x == HBHistory.GoodResponse ]
                if len(goodResponses) == self.samplingInterval:
                    activateSet.add(node)

            # effectiveActiveNodeList can be described as activeNodes after pending config changes
            # have been applied.  Another way to view it is that it reflects current reality, whereas
            # the config file reflects a fixed point in the recent past.
            effectiveActiveNodeList = sorted((set(activeNodes) - deactivateSet) | activateSet)

            # if there was a change to the list of active nodes
            # decide if this node is the effective actor in the cohort.
            if effectiveActiveNodeList != activeNodes:
                self._pickNewActor(effectiveActiveNodeList)
                #print(f"Effective list changed, new actor is {actor}")
            elif oldActiveNodes != activeNodes:
                self._pickNewActor(activeNodes)
                #print(f"active list changed, new actor is {actor}")

            # if we are in a cohort that has <= 50% of the desired nodes, enter standby
            if len(activeNodes)/len(desiredNodes) <= 0.5 and len(effectiveActiveNodeList)/len(desiredNodes) <= 0.5:
                if not inStandbyMode:
                    msg = "Only {} out of {} nodes are active.  At least {} are required.  Entering standby mode to protect the system."\
                        .format(len(activeNodes), len(desiredNodes), int(len(desiredNodes)/2) + 1)
                    self._agentComm.raiseAlarm(msg)
                    self._logger.critical(msg)
                    self._agentComm.enterStandbyMode()
                    inStandbyMode = True
                continue
            elif inStandbyMode and len(effectiveActiveNodeList)/len(desiredNodes) > 0.5:
                self._logger.info("Exiting standby mode, waiting for config update")
                inStandbyMode = False

            # (wasActorOfCohort and not isActorOfCohort) indicates that a new Actor has come online.
            # To hand over the crown, perform one last act as Actor to add it back to the cluster
            # and synchronize its config file.

            # if not the actor, nothing else for this node to do
            if not self._isActorOfCohort and not wasActorOfCohort:
                continue

            # as of here, this node is the actor of its quorum

            if len(deactivateSet) > 0:
                self._agentComm.deactivateNodes(list(deactivateSet))

            if len(activateSet) > 0:
                self._agentComm.activateNodes(activateSet)

            # if the primary node is in this list to be deactivated, or its already on the inactive list
            # choose a new primary node.  The deadNode list is a sanity check for cases like the cluster
            # starting with the primary node already in inactive-nodes.
            deadNodeList = list(deactivateSet) + inactiveNodes
            if self.primaryNode in deadNodeList:
                self._chooseNewPrimaryNode()

    # methods for testing
    def turnOffHBResponder(self):
        self.stop()
