from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectUD import DistributedObjectUD

class PlayerFriendsManagerUD(DistributedObjectUD):
    """Server half of `otp/friends/PlayerFriendsManager.py` (dclass
    `etc/otp.dc:464-477`).  Held deliberately at log-and-return: the
    client's `requestUnlimitedSecret`/`requestLimitedSecret` `sendUpdate`
    names (`PlayerFriendsManager.py:30-34`) have no dc field at all.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('PlayerFriendsManagerUD')

    def requestInvite(self, playerId, avId, isPlayerFriend):
        self.notify.info('requestInvite(%s, %s, %s) -- not implemented' % (
            playerId, avId, isPlayerFriend))

    def requestDecline(self, playerId, avId):
        self.notify.info('requestDecline(%s, %s) -- not implemented' % (playerId, avId))

    def requestDeclineWithReason(self, playerId, avId, reason):
        self.notify.info('requestDeclineWithReason(%s, %s, %s) -- not implemented' % (
            playerId, avId, reason))

    def requestRemove(self, playerId, avId):
        self.notify.info('requestRemove(%s, %s) -- not implemented' % (playerId, avId))
