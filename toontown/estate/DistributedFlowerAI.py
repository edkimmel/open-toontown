from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI


class DistributedFlowerAI(DistributedPlantBaseAI):
    """A planted flower (etc/toon.dc:2724).  Storage-only beyond the base --
    watering/growth/harvest are later tasks (B5/B6)."""

    def __init__(self, air, estateAI):
        DistributedPlantBaseAI.__init__(self, air, estateAI)
        self.variety = 0

    def setVariety(self, variety):
        self.variety = variety

    def getVariety(self):
        return self.variety
