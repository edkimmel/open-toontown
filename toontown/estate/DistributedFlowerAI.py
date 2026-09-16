from toontown.estate import GardenGlobals
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI
from toontown.estate.FlowerBase import FlowerBase


class DistributedFlowerAI(DistributedPlantBaseAI):
    """A planted flower (etc/toon.dc:2724).  `DistributedFlower.doPicking`
    (DistributedFlower.py:124-132) sends the same generic `removeItem` every
    other lawn-decor subclass uses -- there is no maturity/wilt gate on the
    RPC itself, so a pick is credited regardless of growth stage, matching
    the reference (`handlePicking`'s wilted/unblooming/basket-full dialogs
    are all click-through warnings, DistributedFlower.py:85-112)."""

    def __init__(self, air, estateAI):
        DistributedPlantBaseAI.__init__(self, air, estateAI)
        self.variety = 0

    def setVariety(self, variety):
        self.variety = variety

    def getVariety(self):
        return self.variety

    def removeItem(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.getOwnerAvId():
            self.notify.debug('removeItem refused for %s' % avId)
            return
        toon = self.air.doId2do.get(avId)
        if toon is not None:
            self._collectFlower(toon)
        self.d_setMovie(GardenGlobals.MOVIE_REMOVE, avId)
        self._removeFromGarden()

    def _collectFlower(self, toon):
        # `addFlowerToBasket` already caps at `maxFlowerBasket` and silently
        # drops the flower past that (DistributedToonAI.py:3465-3475) -- the
        # pick still happens (the flower is dug up either way), matching the
        # reference's own shape.
        added = toon.addFlowerToBasket(self.typeIndex, self.variety)
        collection = getattr(toon, 'flowerCollection', None)
        if added and collection is not None:
            newFlower = FlowerBase(self.typeIndex, self.variety)
            if collection.collectFlower(newFlower) == GardenGlobals.COLLECT_NEW_ENTRY:
                toon.b_setFlowerCollection(*collection.getNetLists())
            # One shovel skill point per pick -- like the watering can (B5),
            # nothing in the reference ever calls b_setShovelSkill either;
            # `handlePicking`'s skill-up dialog text is the only reference
            # cue this exists at all (DistributedFlower.py:98-109).
            toon.b_setShovelSkill(toon.getShovelSkill() + 1)
