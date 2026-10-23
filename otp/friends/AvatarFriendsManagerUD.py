from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectUD import DistributedObjectUD
from direct.distributed.MsgTypes import CLIENTAGENT_SEND_DATAGRAM
from direct.distributed.PyDatagram import PyDatagram
from otp.distributed.OtpDoGlobals import CLIENT_FRIEND_OFFLINE, CLIENT_FRIEND_ONLINE

class AvatarFriendsManagerUD(DistributedObjectUD):
    """Server half of `otp/friends/AvatarFriendsManager.py` (uberdog 4686,
    `astron/config/astrond.yml:18-20`).  Tracks avatar presence and logs the
    three `airecv clsend` fields (`etc/otp.dc:450,451,455`); the actual
    invite handshake lives on `FriendManagerAI`.

    `avatarOnline`/`avatarOffline`/`updateAvatarName` (`etc/otp.dc:494-495`)
    are declared but have no client handler (`AvatarFriendsManager.py` ends
    its defs at `countTrueFriends`, :103) and are never sent.  What is sent
    is CLIENT_FRIEND_ONLINE / CLIENT_FRIEND_OFFLINE (a uint32 doId), the
    messages `ToontownClientRepository.handleFriendOnline` /
    `handleFriendOffline` consume, wrapped in CLIENTAGENT_SEND_DATAGRAM to
    the friend's account channel -- Astron's client agent never sends them.

    Known gap: the friend list is read from the database when the avatar
    comes online, so a friendship formed mid-session is not reflected until
    the next login.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('AvatarFriendsManagerUD')

    def __init__(self, air):
        DistributedObjectUD.__init__(self, air)
        # avId -> the account connection channel that avatar is riding on.
        self.onlineAvatars = {}
        # avId -> friend doIds read when that avatar came online.
        self.friendIds = {}

    # Presence, called in-process from the login manager -- the only place
    # an avatar becomes online/offline (otp/login/AstronLoginManagerUD.py).
    def avatarCameOnline(self, avId, channel=0):
        if not avId:
            return
        self.onlineAvatars[avId] = channel
        self.notify.debug('avatarCameOnline(%s) on channel %s' % (avId, channel))
        self.air.dbInterface.queryObject(
            self.air.dbId, avId, lambda dclass, fields: self._gotFriends(avId, fields))

    def _gotFriends(self, avId, fields):
        if avId not in self.onlineAvatars:
            return
        entries = (fields or {}).get('setFriendsList', ([],))[0] or []
        friends = [entry[0] for entry in entries]
        self.friendIds[avId] = friends
        for friendId in friends:
            if friendId in self.onlineAvatars:
                self._sendPresence(friendId, CLIENT_FRIEND_ONLINE, avId)
                self._sendPresence(avId, CLIENT_FRIEND_ONLINE, friendId)

    def _sendPresence(self, toAvId, msgType, aboutAvId):
        channel = self.onlineAvatars.get(toAvId, 0)
        if not channel:
            return
        inner = PyDatagram()
        inner.addUint16(msgType)
        inner.addUint32(aboutAvId)
        datagram = PyDatagram()
        datagram.addServerHeader(channel, self.air.ourChannel, CLIENTAGENT_SEND_DATAGRAM)
        datagram.addUint16(inner.getLength())
        datagram.appendData(inner.getMessage())
        self.air.send(datagram)

    def avatarWentOffline(self, avId):
        if avId in self.onlineAvatars:
            for friendId in self.friendIds.pop(avId, []):
                if friendId != avId:
                    self._sendPresence(friendId, CLIENT_FRIEND_OFFLINE, avId)
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