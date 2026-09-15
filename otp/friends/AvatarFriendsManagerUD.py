from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectUD import DistributedObjectUD

class AvatarFriendsManagerUD(DistributedObjectUD):
    """Server half of `otp/friends/AvatarFriendsManager.py` (uberdog 4686,
    `astron/config/astrond.yml:18-20`).  Tracks avatar presence and logs the
    three `airecv clsend` fields (`etc/otp.dc:450,451,455`); the actual
    invite handshake lives on `FriendManagerAI`.

    `avatarOnline`/`avatarOffline`/`updateAvatarName` (`etc/otp.dc:459-461`)
    are declared but have no client handler (`AvatarFriendsManager.py` ends
    its defs at `countTrueFriends`, :103) and must not be sent.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('AvatarFriendsManagerUD')

    def __init__(self, air):
        DistributedObjectUD.__init__(self, air)
        # avId -> the account connection channel that avatar is riding on.
        self.onlineAvatars = {}

    # Presence, called in-process from the login manager -- the only place
    # an avatar becomes online/offline (otp/login/AstronLoginManagerUD.py).
    def avatarCameOnline(self, avId, channel=0):
        if not avId:
            return
        self.onlineAvatars[avId] = channel
        self.notify.debug('avatarCameOnline(%s) on channel %s' % (avId, channel))

    def avatarWentOffline(self, avId):
        if avId in self.onlineAvatars:
            del self.onlineAvatars[avId]
            self.notify.debug('avatarWentOffline(%s)' % avId)

    def isAvatarOnline(self, avId):
        return avId in self.onlineAvatars

    def getOnlineAvatars(self):
        return list(self.onlineAvatars.keys())

    def getAvatarChannel(self, avId):
        return self.onlineAvatars.get(avId, 0)

    # client -> UD (airecv clsend).  Logged, not implemented: reached only
    # with base.friendMode == 1 (toontown/friends/FriendInviter.py,
    # FriendInvitee.py); Toontown's own invite flow is FriendManager's.
    def requestInvite(self, avId):
        self.notify.info('requestInvite(%s) from %s -- not implemented' % (
            avId, self.air.getAvatarIdFromSender()))

    def friendConsidering(self, avId):
        self.notify.info('friendConsidering(%s) from %s -- not implemented' % (
            avId, self.air.getAvatarIdFromSender()))

    def requestRemove(self, avId):
        self.notify.info('requestRemove(%s) from %s -- not implemented' % (
            avId, self.air.getAvatarIdFromSender()))