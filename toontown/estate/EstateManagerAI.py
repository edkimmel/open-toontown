from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate.EstateProvisioner import EstateProvisioner

class EstateManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estate = {}
        self.zoneId2owner = {}
        self.owner2estateZone = {}
        self.provisioner = EstateProvisioner(air)

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
        if avId != senderId:
            # Visiting somebody else's estate is not supported yet.
            return

        sender = self.air.doId2do.get(senderId)
        if sender is None:
            self.notify.warning('Estate request from an unknown avatar %s!' % senderId)
            return

        accountId = sender.DISLid
        if not accountId:
            self.notify.warning('Avatar %s has no account!' % senderId)
            return

        self.provisioner.provision(accountId, lambda estateId, houseIds:
                                   self.__handleEstateProvisioned(senderId, estateId, houseIds))

    def __handleEstateProvisioned(self, avId, estateId, houseIds):
        self.notify.info('Avatar %s has estate %s with houses %s' % (avId, estateId, houseIds))

    def exitEstate(self):
        senderId = self.air.getAvatarIdFromSender()
        self.notify.debug('exitEstate from %s' % senderId)
