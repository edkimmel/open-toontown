from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedPlantBaseAI(DistributedLawnDecorAI):
    """A planted flower or gag tree (etc/toon.dc:2716).  `waterPlant`/
    `waterPlantDone` and growth are a later task (B5); this class is
    storage-only so B4's planting RPCs can generate one."""

    def __init__(self, air, estateAI):
        DistributedLawnDecorAI.__init__(self, air, estateAI)
        self.typeIndex = 0
        self.waterLevel = 0
        self.growthLevel = 0

    def setTypeIndex(self, typeIndex):
        self.typeIndex = typeIndex

    def getTypeIndex(self):
        return self.typeIndex

    def setWaterLevel(self, waterLevel):
        self.waterLevel = waterLevel

    def getWaterLevel(self):
        return self.waterLevel

    def setGrowthLevel(self, growthLevel):
        self.growthLevel = growthLevel

    def getGrowthLevel(self):
        return self.growthLevel
