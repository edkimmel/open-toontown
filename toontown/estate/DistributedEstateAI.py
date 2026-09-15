import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import HouseGlobals
from toontown.estate.EstateProvisioner import NUM_HOUSE_SLOTS, fieldValue


class DistributedEstateAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedEstateAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estateType = 0
        self.dawnTime = 0
        self.clouds = 0
        self.decorData = []
        self.lastEpochTimeStamp = 0
        self.rentalTimeStamp = 0
        self.rentalType = 0
        self.slotToonIds = [0] * NUM_HOUSE_SLOTS
        self.slotItems = [[] for _ in range(NUM_HOUSE_SLOTS)]

    def loadFromDb(self, fields):
        fields = fields or {}
        self.estateType = fieldValue(fields, 'setEstateType', self.estateType)
        self.decorData = fieldValue(fields, 'setDecorData', self.decorData)
        self.lastEpochTimeStamp = fieldValue(fields, 'setLastEpochTimeStamp', self.lastEpochTimeStamp)
        self.rentalTimeStamp = fieldValue(fields, 'setRentalTimeStamp', self.rentalTimeStamp)
        self.rentalType = fieldValue(fields, 'setRentalType', self.rentalType)
        for slot in range(NUM_HOUSE_SLOTS):
            self.slotToonIds[slot] = fieldValue(fields, 'setSlot%dToonId' % slot, 0)
            self.slotItems[slot] = fieldValue(fields, 'setSlot%dItems' % slot, [])

    def setEstateType(self, estateType):
        self.estateType = estateType

    def getEstateType(self):
        return self.estateType

    def setDawnTime(self, dawnTime):
        self.dawnTime = dawnTime

    def getDawnTime(self):
        return self.dawnTime

    def setClouds(self, clouds):
        self.clouds = clouds

    def getClouds(self):
        return self.clouds

    def setDecorData(self, decorData):
        self.decorData = decorData

    def getDecorData(self):
        return self.decorData

    def setLastEpochTimeStamp(self, timeStamp):
        self.lastEpochTimeStamp = timeStamp

    def getLastEpochTimeStamp(self):
        return self.lastEpochTimeStamp

    def setRentalTimeStamp(self, timeStamp):
        self.rentalTimeStamp = timeStamp

    def getRentalTimeStamp(self):
        return self.rentalTimeStamp

    def setRentalType(self, rentalType):
        self.rentalType = rentalType

    def getRentalType(self):
        return self.rentalType

    def setSlot0ToonId(self, avId):
        self.slotToonIds[0] = avId

    def getSlot0ToonId(self):
        return self.slotToonIds[0]

    def setSlot0Items(self, items):
        self.slotItems[0] = items

    def getSlot0Items(self):
        return self.slotItems[0]

    def setSlot1ToonId(self, avId):
        self.slotToonIds[1] = avId

    def getSlot1ToonId(self):
        return self.slotToonIds[1]

    def setSlot1Items(self, items):
        self.slotItems[1] = items

    def getSlot1Items(self):
        return self.slotItems[1]

    def setSlot2ToonId(self, avId):
        self.slotToonIds[2] = avId

    def getSlot2ToonId(self):
        return self.slotToonIds[2]

    def setSlot2Items(self, items):
        self.slotItems[2] = items

    def getSlot2Items(self):
        return self.slotItems[2]

    def setSlot3ToonId(self, avId):
        self.slotToonIds[3] = avId

    def getSlot3ToonId(self):
        return self.slotToonIds[3]

    def setSlot3Items(self, items):
        self.slotItems[3] = items

    def getSlot3Items(self):
        return self.slotItems[3]

    def setSlot4ToonId(self, avId):
        self.slotToonIds[4] = avId

    def getSlot4ToonId(self):
        return self.slotToonIds[4]

    def setSlot4Items(self, items):
        self.slotItems[4] = items

    def getSlot4Items(self):
        return self.slotItems[4]

    def setSlot5ToonId(self, avId):
        self.slotToonIds[5] = avId

    def getSlot5ToonId(self):
        return self.slotToonIds[5]

    def setSlot5Items(self, items):
        self.slotItems[5] = items

    def getSlot5Items(self):
        return self.slotItems[5]

    def requestServerTime(self):
        avId = self.air.getAvatarIdFromSender()
        serverTime = int(time.time() % HouseGlobals.DAY_NIGHT_PERIOD)
        self.sendUpdateToAvatarId(avId, 'setServerTime', [serverTime])
