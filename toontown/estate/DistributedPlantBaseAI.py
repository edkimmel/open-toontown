from toontown.estate import GardenGlobals
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedPlantBaseAI(DistributedLawnDecorAI):
    """A planted flower or gag tree (etc/toon.dc:2716).

    Unlike `plotEntered`/`removeItem`, watering has no server-side
    request/grant handshake in the reference: the client only ever sends
    `waterPlant` directly when the player is standing in range with a
    watering can out (`DistributedPlantBase.handleEnterPlot` overrides the
    base's collision handler and never sends `plotEntered`,
    DistributedPlantBase.py:86-89,99-104).  `waterPlant` establishes its
    own one-avatar session on `self.busy` (inherited from
    `DistributedLawnDecorAI`) for the duration of the watering movie, and
    `waterPlantDone` (etc/toon.dc:2719) releases it -- the same busy/
    avatar-exit-hook shape `plotEntered`/`movieDone` already use, just
    entered by a different RPC.
    """

    def __init__(self, air, estateAI):
        DistributedLawnDecorAI.__init__(self, air, estateAI)
        self.typeIndex = 0
        self.waterLevel = 0
        self.growthLevel = 0
        self.maxWaterLevel = GardenGlobals.getMaxWateringCanPower()
        self.minWaterLevel = -2
        self.growthThresholds = (1, 1, 1)

    def setTypeIndex(self, typeIndex):
        self.typeIndex = typeIndex
        attrib = GardenGlobals.PlantAttributes.get(typeIndex, {})
        self.maxWaterLevel = attrib.get('maxWaterLevel', self.maxWaterLevel)
        self.minWaterLevel = attrib.get('minWaterLevel', self.minWaterLevel)
        self.growthThresholds = attrib.get('growthThresholds', self.growthThresholds)

    def getTypeIndex(self):
        return self.typeIndex

    def setWaterLevel(self, waterLevel):
        self.waterLevel = waterLevel

    def getWaterLevel(self):
        return self.waterLevel

    def d_setWaterLevel(self, waterLevel):
        self.sendUpdate('setWaterLevel', [waterLevel])

    def setGrowthLevel(self, growthLevel):
        self.growthLevel = growthLevel

    def getGrowthLevel(self):
        return self.growthLevel

    def waterPlant(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.getOwnerAvId() or self.isBusy():
            return
        toon = self.air.doId2do.get(avId)
        if toon is None:
            return
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleWaterExit, extraArgs=[avId])
        power = GardenGlobals.getWateringCanPower(toon.getWateringCan(),
                                                   toon.getWateringCanSkill())
        newLevel = min(self.waterLevel + power, self.maxWaterLevel)
        self.setWaterLevel(newLevel)
        self.d_setWaterLevel(newLevel)
        self._persistLevels()
        self.d_setMovie(GardenGlobals.MOVIE_WATER, avId)
        # The watering-can skill promotion machinery already exists on
        # DistributedToonAI (`b_setWateringCanSkill`, DistributedToonAI.py:
        # 3529-3552) but nothing in the reference ever calls it -- the same
        # kind of unwired gap B1 found in GardenGlobals' own validators.
        # One skill point per successful watering is this task's own rule.
        toon.b_setWateringCanSkill(toon.getWateringCanSkill() + 1)

    def waterPlantDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.busy:
            return
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0
        self.d_setMovie(GardenGlobals.MOVIE_CLEAR, avId)

    def __handleWaterExit(self, avId):
        if self.busy != avId:
            return
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0
        self.d_setMovie(GardenGlobals.MOVIE_CLEAR, avId)

    def _persistLevels(self):
        # The only persistence path for a planted item is its lawnItem
        # tuple (type, hardPoint, waterLevel, growthLevel, optional) inside
        # estateAI.slotItems[ownerIndex] -- DistributedGardenPlotAI's own
        # comment, unchanged since B4.
        items = list(self.estateAI.slotItems[self.ownerIndex])
        for i, item in enumerate(items):
            if item[1] == self.plot:
                items[i] = (item[0], item[1], self.waterLevel, self.growthLevel, item[4])
                break
        self.estateAI.b_setSlotItems(self.ownerIndex, items)
