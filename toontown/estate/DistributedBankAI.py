from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI


class DistributedBankAI(DistributedFurnitureItemAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBankAI')
