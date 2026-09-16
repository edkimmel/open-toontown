from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedGardenPlotAI(DistributedLawnDecorAI):
    """An empty garden hard point (etc/toon.dc:2687).  `setPlot` is the hard
    point index into `GardenGlobals.estatePlots[ownerIndex]`, the same pair
    `whatCanBePlanted(ownerIndex, plot)` (GardenGlobals.py:1277) reads to
    decide what may grow here.  Planting
    (plantFlower/plantGagTree/plantStatuary/plantToonStatuary/plantNothing)
    is a later task; this class is storage-only for now."""
    pass
