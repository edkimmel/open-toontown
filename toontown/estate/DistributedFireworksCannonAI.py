from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.effects.DistributedFireworkShowAI import DistributedFireworkShowAI
from . import HouseGlobals

class DistributedFireworksCannonAI(DistributedFireworkShowAI):
    """The estate fireworks prop (dclass DistributedFireworksCannon,
    etc/toon.dc:2174-2180), a single-occupant session on top of a firework
    show: the occupant gets the shooting GUI and its requestFirework is the
    show's own, so shots still run through the firework manager.

    setMovie here takes three fields -- mode, avId, timestamp (:2178) --
    unlike the two-field setMovie every other estate session object uses.

    Nothing in the reference sent FIREWORKS_MOVIE_CLEAR even though the
    client handles it (DistributedFireworksCannon.py:81-83), and the field is
    broadcast ram, so the terminal GUI mode replayed to the next avatar
    generating the prop; a release sends CLEAR the way
    DistributedClosetAI.__release does (DistributedClosetAI.py:234-251).
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFireworksCannonAI')

    def __init__(self, air, fireworkMgr=None, x=0, y=0, z=0):
        DistributedFireworkShowAI.__init__(self, air, fireworkMgr)
        self.pos = [x, y, z]
        self.avId = 0

    def delete(self):
        self.ignoreAll()
        DistributedFireworkShowAI.delete(self)

    def getPosition(self):
        return self.pos

    def setPosition(self, x, y, z):
        self.pos = [x, y, z]

    def d_setPosition(self, x, y, z):
        self.sendUpdate('setPosition', [x, y, z])

    def b_setPosition(self, x, y, z):
        self.setPosition(x, y, z)
        self.d_setPosition(x, y, z)

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId:
            self.air.writeServerEvent('suspicious', avId,
                                      'DistributedFireworksCannonAI.avatarEnter cannon already occupied')
            self.notify.warning('avatarEnter() - cannon already occupied')
            return
        self.avId = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId),
                        self.__handleUnexpectedExit, extraArgs=[avId])
        self.d_setMovie(HouseGlobals.FIREWORKS_MOVIE_GUI, avId)

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'avatarExit'):
            return
        self.freeAvatar(avId)
        self.__release()

    def freeAvatar(self, avId):
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def requestFirework(self, x, y, z, style, color1, color2):
        avId = self.air.getAvatarIdFromSender()
        if not self.__isOccupant(avId, 'requestFirework'):
            return
        DistributedFireworkShowAI.requestFirework(self, x, y, z, style,
                                                  color1, color2)

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId,
                                     globalClockDelta.getRealNetworkTime()])

    def __isOccupant(self, avId, methodName):
        if avId != 0 and avId == self.avId:
            return True
        self.air.writeServerEvent('suspicious', avId,
                                  'DistributedFireworksCannonAI.%s from a non-occupant' % methodName)
        return False

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar:' + str(avId) + ' has exited unexpectedly')
        if avId == self.avId:
            self.__release()

    def __release(self):
        avId = self.avId
        if avId:
            self.ignore(self.air.getAvatarExitEvent(avId))
        self.avId = 0
        # leave the required field idle once the GUI closes, so a later
        # generate replays a mode the client ignores instead of the GUI
        self.d_setMovie(HouseGlobals.FIREWORKS_MOVIE_CLEAR, 0)
