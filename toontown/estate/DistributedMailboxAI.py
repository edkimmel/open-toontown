from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedMailboxAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedMailboxAI')

    def __init__(self, air, house):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.fullIndicator = 0

    def getHouseId(self):
        # the client compares this against its own houseId before it accepts
        # the collision (toontown/estate/DistributedMailbox.py:37-38)
        return self.house.doId

    def getHousePos(self):
        return self.house.getHousePos()

    def getName(self):
        return self.house.getName()

    def getFullIndicator(self):
        return self.fullIndicator

    def b_setFullIndicator(self, full):
        self.fullIndicator = full
        self.sendUpdate('setFullIndicator', [full])
