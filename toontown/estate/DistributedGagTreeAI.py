from toontown.estate import GardenGlobals
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI


class DistributedGagTreeAI(DistributedPlantBaseAI):
    """A planted gag tree (etc/toon.dc:2729).  `requestHarvest` (etc/toon.dc:
    2731) has no `plotEntered` session either (same finding as
    `removeItem`/`waterPlant`) -- `DistributedGagTree.doHarvesting` sends it
    directly once `isFruiting()` and `canBeHarvested()` are true
    (DistributedGagTree.py:130-138,187-194)."""

    def __init__(self, air, estateAI):
        DistributedPlantBaseAI.__init__(self, air, estateAI)
        self.wilted = 0

    def setWilted(self, wilted):
        self.wilted = wilted

    def getWilted(self):
        return self.wilted

    def requestHarvest(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.getOwnerAvId() or self.isBusy():
            return
        # Maturity: DistributedPlantBase.isFruiting (DistributedPlantBase.py:
        # 108-110).
        if self.growthLevel < self.growthThresholds[2]:
            return
        toon = self.air.doId2do.get(avId)
        if toon is None:
            return
        inventory = getattr(toon, 'inventory', None)
        if inventory is None:
            return
        track, level = GardenGlobals.getTreeTrackAndLevel(self.typeIndex)
        # The same inventory object plantGagTree spends from
        # (DistributedGardenPlotAI.plantGagTree); addItem's own max-carry
        # check (InventoryBase.py:92-118) refuses the whole harvest if the
        # toon's pack is full, same as an ordinary gag pickup would.
        if inventory.addItem(track, level) <= 0:
            return
        toon.b_setInventory(inventory.makeNetString())
        # No server-side harvest reset exists in the reference at all (same
        # missing-tick gap B5 found for growth/watering-skill) -- back to a
        # fresh seedling, the same state a newly-planted tree starts at
        # (DistributedGardenPlotAI._replaceWithGrownObject's own 0, 0).
        self.setWaterLevel(0)
        self.setGrowthLevel(0)
        self.d_setWaterLevel(0)
        self.d_setGrowthLevel(0)
        self._persistLevels()
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleHarvestExit, extraArgs=[avId])
        self.d_setMovie(GardenGlobals.MOVIE_HARVEST, avId)

    def __handleHarvestExit(self, avId):
        if self.busy != avId:
            return
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.busy = 0
        self.d_setMovie(GardenGlobals.MOVIE_CLEAR, avId)
