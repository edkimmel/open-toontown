from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedGardenBoxAI(DistributedLawnDecorAI):
    """A flower planter box (etc/toon.dc:2695).  Storage-only beyond the
    ownership/session base -- flowers are planted on the DistributedGardenPlot
    hard points a box groups, not on the box itself."""

    def __init__(self, air, estateAI):
        DistributedLawnDecorAI.__init__(self, air, estateAI)
        self.typeIndex = 0

    def setTypeIndex(self, typeIndex):
        self.typeIndex = typeIndex

    def getTypeIndex(self):
        return self.typeIndex
