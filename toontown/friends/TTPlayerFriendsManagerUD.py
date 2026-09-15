from direct.directnotify import DirectNotifyGlobal

from otp.friends.PlayerFriendsManagerUD import PlayerFriendsManagerUD

class TTPlayerFriendsManagerUD(PlayerFriendsManagerUD):
    """Uberdog 4687.  Mirrors the client split
    (`toontown/friends/TTPlayerFriendsManager.py`): the Toontown subclass
    exists only to flip `requestInvite`'s last argument, so the server-side
    logic belongs on the base class.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory('TTPlayerFriendsManagerUD')
