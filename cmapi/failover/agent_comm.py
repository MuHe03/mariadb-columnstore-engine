# this class handles the comm with the agent; whatever it will be

import datetime
import logging
import threading
import time


logger = logging.getLogger(__file__)


# First an agent base class
class AgentBase:

    def activateNodes(self, nodes):
        print("AgentBase: Got activateNodes({})".format(nodes))

    def deactivateNodes(self, nodes):
        print("AgentBase: Got deactivateNodes({})".format(nodes))

    def movePrimaryNode(self, placeholder):
        print("AgentBase: Got movePrimaryNode()")

    def enterStandbyMode(self):
        print("AgentBase: Got enterStandbyMode()")

    def getNodeHealth(self):
        print("AgentBase: Got getNodeHealth()")
        return 0

    def raiseAlarm(self, msg):
        print("AgentBase: Got raiseAlarm({})".format(msg))

    def startTransaction(self, extra_nodes = [], remove_nodes = []):
        print(f"AgentBase: Got startTransaction, extra_nodes={extra_nodes}, remove_nodes={remove_nodes}")
        return 0

    def commitTransaction(self, txnid, nodes):
        print("AgentBase: Got commitTransaction")

    def rollbackTransaction(self, txnid, nodes):
        print("AgentBase: Got abortTransaction")



class OpAndArgs:
    name = None   # a callable in AgentBase
    args = None   # a tuple containing the args for the callable

    def __init__(self, name, *args):
        self.name = name
        self.args = args

    def __str__(self):
        return f"{str(self.name.__qualname__)}{str(self.args)}"

    def __hash__(self):
        return hash((self.name.__qualname__, str(self.args)))

    def __eq__(self, other):
        return self.name == other.name and self.args == other.args

    def __ne__(self, other):
        return not self.__eq__(other)

    def run(self):
        self.name(*self.args)


# The AgentComm class
# Doesn't do anything but pass along events to the Agent yet
# TODO: implement an event queue and a thread to pluck events and issue them
# to the agent.
# TODO: de-dup events as they come in from the node monitor, add to the event queue
class AgentComm:

    _agent = None
    _thread = None
    _queue = None
    _deduper = None    # deduper contains queue contents, events in progress, and finished events up to 10s after they finished
    _mutex = None
    _die = False

    def __init__(self, agent = None):
        if agent is None:
            self._agent = AgentBase()
        else:
            self._agent = agent

        self._queue = []
        self._deduper = {}
        self._mutex = threading.Lock()
        self._thread = threading.Thread(target = self._runner)
        self._thread.start()

    def __del__(self):
        self.die()

    def die(self):
        self._die = True
        self._thread.join()

    # returns (len-of-event-queue, len-of-deduper)
    def getQueueSize(self):
        self._mutex.acquire()
        ret = (len(self._queue), len(self._deduper))
        self._mutex.release()
        return ret

    def activateNodes(self, nodes):
        self._addEvent(self._agent.activateNodes, (nodes))

    def deactivateNodes(self, nodes):
        self._addEvent(self._agent.deactivateNodes, (nodes))

    def movePrimaryNode(self):
        self._addEvent(self._agent.movePrimaryNode, ())

    def enterStandbyMode(self):
        # The other events are moot if this node has to enter standby mode
        self._mutex.acquire()
        op = OpAndArgs(self._agent.enterStandbyMode, ())
        self._queue = [ op ]
        self._deduper = { op : datetime.datetime.now() }
        self._mutex.release()

    def getNodeHealth(self):
        return self._agent.getNodeHealth()

    def raiseAlarm(self, msg):
        self._agent.raiseAlarm(msg)

    def _addEvent(self, name, args):
        """Interface to the event queue."""
        op = OpAndArgs(name, args)

        self._mutex.acquire()
        if op not in self._deduper:
            self._deduper[op] = None
            self._queue.append(op)
        self._mutex.release()

    def _getEvents(self):
        """
            This gets all queued events at once and prunes events older than
            10 seconds from the deduper.
        """
        self._mutex.acquire()
        ret = self._queue
        self._queue = []

        # prune events that finished more than 10 secs ago from the deduper
        tenSecsAgo = datetime.datetime.now() - datetime.timedelta(seconds = 10)
        for (op, finishTime) in list(self._deduper.items()):
            if finishTime is not None and finishTime < tenSecsAgo:
                del self._deduper[op]

        self._mutex.release()
        return ret

    def _requeueEvents(self, events):
        self._mutex.acquire()
        # events has commands issued before what is currently in _queue
        events.extend(self._queue)
        self._queue = events
        self._mutex.release()

    def _markEventsFinished(self, events):
        self._mutex.acquire()
        now = datetime.datetime.now()
        for event in events:
            self._deduper[event] = now
        self._mutex.release()

    def _runner(self):
        while not self._die:
            try:
                self.__runner()
            except Exception as e:
                logger.error(f"AgentComm.runner(): got an exception: {str(e)}")
            if not self._die:
                time.sleep(1)
        logger.info("AgentComm.runner() exiting normally...")

    def __runner(self):
        while not self._die:
            events = self._getEvents()
            if len(events) == 0:
                time.sleep(5)
                continue

            nextPollTime = datetime.datetime.now() + datetime.timedelta(seconds = 5)

            nodes_added = set()
            nodes_removed = set()

            # scan the list of events, put together the extra_nodes and remove_nodes parameters to
            # startTransaction().  Note, we could consolidate the activate / deactivate calls here,
            # but that's a minor optimization not worth doing yet.
            needs_transaction = False
            for event in events:
                #print(f"got event: {event}")

                # determine whether we need a transaction at all.
                # List the fcns that require a txn here.
                if not needs_transaction and event.name in (
                  self._agent.activateNodes,
                  self._agent.deactivateNodes,
                  self._agent.movePrimaryNode):
                    needs_transaction = True

                if event.name == self._agent.activateNodes:
                    nodes = event.args[0]
                    for node in nodes:
                        nodes_added.add(node)
                elif event.name == self._agent.deactivateNodes:
                    nodes = event.args[0]
                    for node in nodes:
                        nodes_removed.add(node)

            if needs_transaction:
                (txn_id, nodes) = self._agent.startTransaction(extra_nodes = list(nodes_added), remove_nodes = list(nodes_removed))

            # The problem with this is that it's all-or-nothing
            # It would be preferable to commit what has been done up to the point of failure
            # and discard the event that failed.
            # If the problem is with the event itself, then it may keep happening and block all
            # progress.
            try:
                for event in events:
                    #print(f"Running {event}")
                    event.run()
            except Exception as e:
                if needs_transaction:
                    logger.warning(f"AgentComm._runner(): caught an exception {str(e)}, aborting transaction {txn_id}")
                    self._agent.rollbackTransaction(txn_id, nodes = nodes)
                else:
                    logger.warning(f"AgentComm._runner(): caught an exception {str(e)}")
                # on failure, requeue the events in this batch to pick them up again on the next iteration
                self._requeueEvents(events)
            else:
                if needs_transaction:
                    self._agent.commitTransaction(txn_id, nodes = nodes)
                self._markEventsFinished(events)
            finishTime = datetime.datetime.now()
            if nextPollTime > finishTime:
                time.sleep((nextPollTime - finishTime).seconds)
