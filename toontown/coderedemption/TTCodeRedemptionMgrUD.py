from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD

CodeDoesntExist = 1

class TTCodeRedemptionMgrUD(DistributedObjectGlobalUD):
    notify = DirectNotifyGlobal.directNotify.newCategory('TTCodeRedemptionMgrUD')

    def redeemCode(self, context, code):
        sender = self.air.getMsgSender()
        if not self.air.getAvatarIdFromSender():
            return
        self.sendUpdateToChannel(sender, 'redeemCodeResult', [context, CodeDoesntExist, 0])
