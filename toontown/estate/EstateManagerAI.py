from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

class EstateManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estate = {}
        self.zoneId2owner = {}
        self.owner2estateZone = {}

    def getOwnerFromZone(self, zoneId):
        return self.zoneId2owner.get(zoneId)

    def getEstateZones(self, ownerId):
        zoneId = self.owner2estateZone.get(ownerId)
        if zoneId is None:
            return []
        return [zoneId]

    def getEstateHouseZones(self, ownerId):
        return []

    def getEstateZone(self, avId, name):
        senderId = self.air.getAvatarIdFromSender()
        self.notify.debug('getEstateZone from %s for avId %s name %s' % (senderId, avId, name))

    def exitEstate(self):
        senderId = self.air.getAvatarIdFromSender()
        self.notify.debug('exitEstate from %s' % senderId)
