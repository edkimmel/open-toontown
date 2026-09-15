from otp.otpbase import OTPGlobals
from otp.ai import BanManagerAI
from toontown.toonbase import ToontownGlobals
from toontown.hood import ZoneUtil

def canAccess(avatarId, zoneId, function = ''):
    avatar = simbase.air.doId2do.get(avatarId)
    if avatar is None:
        return False
    if avatar.getGameAccess() == OTPGlobals.AccessFull or openToAll(zoneId, avatar):
        return True
    if function == 'DistributedBoardingPartyAI.checkBoard':
        return False
    simbase.air.writeServerEvent('suspicious', avatarId, 'User with rights: %s requesting enter for paid access content without proper rights in zone %s from %s' % (avatar.getGameAccess(), zoneId, function))
    if simbase.config.GetBool('want-ban-ispaid', True) and hasattr(simbase.air, 'banManager'):
        commentStr = 'User with rights: %s tried to gain access zone %s from function %s, an area they were not allowed to using TTInjector Hack' % (avatar.getGameAccess(), zoneId, function)
        dislId = avatar.DISLid
        simbase.air.banManager.ban(avatarId, dislId, commentStr)
    return False


def openToAll(zoneId, avatar):
    canonicalZoneId = ZoneUtil.getCanonicalHoodId(zoneId)
    allowedZones = [ToontownGlobals.ToontownCentral,
     ToontownGlobals.MyEstate,
     ToontownGlobals.GoofySpeedway,
     ToontownGlobals.Tutorial]
    if canonicalZoneId in allowedZones or avatar.isInEstate():
        return True

    specialZones = [ToontownGlobals.SellbotLobby]
    if ToontownGlobals.SELLBOT_NERF_HOLIDAY in simbase.air.holidayManager.currentHolidays:
        specialZones.append(ToontownGlobals.SellbotHQ)
    if hasattr(simbase.air, 'estateMgr'):
        ownerId = simbase.air.estateMgr.getOwnerFromZone(zoneId)
        if ownerId:
            for zone in simbase.air.estateMgr.getEstateZones(ownerId):
                specialZones.append(zone)

    if zoneId in specialZones:
        return True
    if canonicalZoneId >= ToontownGlobals.DynamicZonesBegin and not avatar.getTutorialAck():
        zoneDict = simbase.air.tutorialManager.playerDict.get(avatar.doId)
        if zoneDict:
            return True
    return False


def canWearSuit(avatarId, zoneId):
    canonicalZoneId = ZoneUtil.getCanonicalHoodId(zoneId)
    allowedSuitZones = [ToontownGlobals.LawbotHQ,
     ToontownGlobals.CashbotHQ,
     ToontownGlobals.SellbotHQ,
     ToontownGlobals.BossbotHQ]
    if canonicalZoneId in allowedSuitZones:
        return True
    elif zoneId >= ToontownGlobals.DynamicZonesBegin:
        return True
    else:
        return False
