from direct.directnotify import DirectNotifyGlobal

from toontown.effects.DistributedFireworkShowAI import DistributedFireworkShowAI

class FireworkManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('FireworkManagerAI')

    def __init__(self, air):
        self.air = air
        # zoneId -> the show currently running in that zone
        self.fireworkShows = {}

    def startShow(self, zoneId, showId, style):
        # one show at a time per zone; the caller gets None when there is
        # already one playing there
        if zoneId in self.fireworkShows:
            return None

        self.notify.debug('startShow: zoneId: %s, showId: %s, style: %s' % (zoneId, showId, style))
        show = DistributedFireworkShowAI(self.air, self)
        show.generateWithRequired(zoneId)
        self.fireworkShows[zoneId] = show
        show.d_startShow(showId, style)
        return show

    def isShowRunning(self, zoneId):
        return zoneId in self.fireworkShows

    def stopShow(self, zoneId):
        show = self.fireworkShows.pop(zoneId, None)
        if show is None:
            return

        self.notify.debug('stopShow: zoneId: %s' % zoneId)
        show.requestDelete()
