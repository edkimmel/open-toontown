from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedClosetAI import DistributedClosetAI


class DistributedTrunkAI(DistributedClosetAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrunkAI')
