from direct.directnotify import DirectNotifyGlobal
from toontown.shtiker.CogPageGlobals import (COG_BATTLED, COG_COMPLETE1,
                                              COG_COMPLETE2, COG_DEFEATED,
                                              COG_QUOTAS, COG_UNSEEN)
from toontown.suit import SuitDNA


class CogPageManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('CogPageManagerAI')

    def __init__(self, air):
        self.air = air

    def toonKilledCogs(self, toon, suitsKilled, zoneId):
        for record in suitsKilled or ():
            index = self._recordIndex(toon, record)
            if index is None:
                continue
            statuses = list(toon.getCogStatus() or [])
            counts = list(toon.getCogCount() or [])
            if len(statuses) != 32 or len(counts) != 32:
                continue
            old_status, old_count = statuses[index], counts[index]
            new_count = min(old_count + 1, COG_QUOTAS[1][index % SuitDNA.suitsPerDept])
            quota1 = COG_QUOTAS[0][index % SuitDNA.suitsPerDept]
            quota2 = COG_QUOTAS[1][index % SuitDNA.suitsPerDept]
            if new_count >= quota2:
                new_status = COG_COMPLETE2
            elif new_count >= quota1:
                new_status = COG_COMPLETE1
            else:
                new_status = max(old_status, COG_DEFEATED)
            if new_count != old_count:
                counts[index] = new_count
                toon.b_setCogCount(counts)
            if new_status != old_status:
                statuses[index] = new_status
                toon.b_setCogStatus(statuses)
            self._publishRadarUnlocks(toon, counts)

    def toonEncounteredCogs(self, toon, suitsEncountered, zoneId):
        for record in suitsEncountered or ():
            index = self._recordIndex(toon, record)
            if index is None:
                continue
            statuses = list(toon.getCogStatus() or [])
            if len(statuses) != 32 or statuses[index] != COG_UNSEEN:
                continue
            statuses[index] = COG_BATTLED
            toon.b_setCogStatus(statuses)

    @staticmethod
    def _recordIndex(toon, record):
        if not isinstance(record, dict) or not isinstance(record.get('type'), str):
            return None
        # Boss/decorative battle records carry no ordinary Cog-page credit.
        # Skelecogs intentionally remain eligible when their normal type is
        # present; the established boss flags disqualify an otherwise valid
        # type. Other special-Cog flags need a reference contract first.
        if record.get('isVP') or record.get('isCFO'):
            return None
        active = record.get('activeToons')
        if active is not None and getattr(toon, 'doId', None) not in active:
            return None
        try:
            index = SuitDNA.suitHeadTypes.index(record['type'])
        except (ValueError, TypeError):
            return None
        if index >= SuitDNA.suitsPerDept * 4:
            return None
        return index

    @staticmethod
    def _publishRadarUnlocks(toon, counts):
        if len(counts) != SuitDNA.suitsPerDept * 4:
            return
        radar = list(toon.getCogRadar() or [])
        building = list(toon.getBuildingRadar() or [])
        if len(radar) != 4 or len(building) != 4:
            return
        changed_radar = False
        changed_building = False
        for dept in range(4):
            base = dept * SuitDNA.suitsPerDept
            if all(counts[base + i] >= COG_QUOTAS[0][i] for i in range(SuitDNA.suitsPerDept)) and not radar[dept]:
                radar[dept] = 1
                changed_radar = True
            if all(counts[base + i] >= COG_QUOTAS[1][i] for i in range(SuitDNA.suitsPerDept)) and not building[dept]:
                building[dept] = 1
                changed_building = True
        if changed_radar:
            toon.b_setCogRadar(radar)
        if changed_building:
            toon.b_setBuildingRadar(building)
