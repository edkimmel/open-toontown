from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI


class DistributedClosetAI(DistributedFurnitureItemAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedClosetAI')
