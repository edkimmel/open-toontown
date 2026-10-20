from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectUD import DistributedObjectUD

CodeDoesntExist = 1

class TTCodeRedemptionMgrUD(DistributedObjectUD):
    notify = DirectNotifyGlobal.directNotify.newCategory('TTCodeRedemptionMgrUD')

    def redeemCode(self, context, code):
        sender = self.air.getMsgSender()
        if not self.air.getAvatarIdFromSender():
            return
        self.sendUpdateToChannel(sender, 'redeemCodeResult', [context, CodeDoesntExist, 0])
