from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals


class HolidayManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('HolidayManagerAI')

    def __init__(self, air):
        self.air = air
        self.currentHolidays = {}

    def isHolidayRunning(self, holidayId):
        return holidayId in self.currentHolidays

    def startHoliday(self, holidayId):
        if holidayId in self.currentHolidays:
            return False
        self.currentHolidays[holidayId] = None
        self.air.newsManager.sendHolidayIdList()
        return True

    def endHoliday(self, holidayId):
        if holidayId not in self.currentHolidays:
            return False
        del self.currentHolidays[holidayId]
        self.air.newsManager.sendHolidayIdList()
        return True

    def isMoreXpHolidayRunning(self):
        return ToontownGlobals.MORE_XP_HOLIDAY in self.currentHolidays
