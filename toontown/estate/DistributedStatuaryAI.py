from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedStatuaryAI(DistributedLawnDecorAI):
    """A planted garden statuary item (etc/toon.dc:2699).  Storage-only --
    statuary has no growth mechanic (`GardenGlobals.PlantAttributes`'s
    statuary entries carry no `growthThresholds`), so it is always planted
    fully grown; no interaction beyond the lawn-decor base."""

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
