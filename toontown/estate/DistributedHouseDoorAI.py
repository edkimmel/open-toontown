from toontown.building import DistributedDoorAI


class DistributedHouseDoorAI(DistributedDoorAI.DistributedDoorAI):
    """A house door carries the house's doId as its block, which is what the
    client reads back out of setZoneIdAndBlock
    (toontown/estate/DistributedHouseDoor.py:25-27)."""

    def __init__(self, air, houseId, doorType, doorIndex=0, lockValue=0, swing=3):
        DistributedDoorAI.DistributedDoorAI.__init__(self, air, houseId, doorType,
                                                     doorIndex, lockValue, swing)
