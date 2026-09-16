import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.task import Task
from . import FishingTargetGlobals

class DistributedFishingTargetAI(DistributedObjectAI):
    """The lure the client's bob has to reach for a cast to end at all.

    The client lerps itself to a new polar position on every `setState`
    (`DistributedFishingTarget.setState:116-121`); this half arms the loop
    that picks that position and broadcasts it, and registers with the
    pond so `DistributedFishingPondAI.hitTarget` can validate the doId a
    client names.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingTargetAI')

    def __init__(self, air, pondDoId=0):
        DistributedObjectAI.__init__(self, air)
        self.pondDoId = pondDoId
        self.pond = None
        self.state = (FishingTargetGlobals.OFF, 0, 0, 0, 0)
        # random.Random-compatible source; a test replaces this instead of
        # monkeypatching the module.
        self.rng = random

    def generate(self):
        DistributedObjectAI.generate(self)
        self.pond = self.air.doId2do.get(self.pondDoId)
        if self.pond is None:
            self.notify.warning('target %s has no pond %s' % (self.doId, self.pondDoId))
        else:
            self.pond.addTarget(self)
        self.__broadcastMove()
        self.__armStep()

    def delete(self):
        self.__clearStep()
        if self.pond is not None:
            self.pond.removeTarget(self)
            self.pond = None
        DistributedObjectAI.delete(self)

    def setPondDoId(self, pondDoId):
        self.pondDoId = pondDoId

    def getPondDoId(self):
        return self.pondDoId

    def setState(self, stateIndex, angle, radius, time, timeStamp):
        self.state = (stateIndex, angle, radius, time, timeStamp)

    def getState(self):
        return self.state

    def __stepTaskName(self):
        return self.uniqueName('fishingTargetStep')

    def __armStep(self):
        taskMgr.doMethodLater(FishingTargetGlobals.StepTime, self.__step,
                              self.__stepTaskName())

    def __clearStep(self):
        taskMgr.remove(self.__stepTaskName())

    def __step(self, task):
        self.__broadcastMove()
        self.__armStep()
        return Task.done

    def __broadcastMove(self):
        area = self.pond.getArea() if self.pond is not None else None
        maxRadius = FishingTargetGlobals.getTargetRadius(area)
        angle = self.rng.uniform(0, 2 * math.pi)
        radius = self.rng.uniform(0, maxRadius)
        timeStamp = globalClockDelta.getRealNetworkTime()
        self.setState(FishingTargetGlobals.MOVING, angle, radius,
                      FishingTargetGlobals.StepTime, timeStamp)
        self.sendUpdate('setState', list(self.state))
