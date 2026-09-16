from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI


class DistributedGagTreeAI(DistributedPlantBaseAI):
    """A planted gag tree (etc/toon.dc:2729).  Storage-only beyond the base --
    `requestHarvest` is a later task (B6)."""

    def __init__(self, air, estateAI):
        DistributedPlantBaseAI.__init__(self, air, estateAI)
        self.wilted = 0

    def setWilted(self, wilted):
        self.wilted = wilted

    def getWilted(self):
        return self.wilted
