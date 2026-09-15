from direct.directnotify import DirectNotifyGlobal

NUM_HOUSE_SLOTS = 6


class EstateProvisionOperation:
    """Reads an account, creating its estate record and a house record for
    every occupied avatar slot if they do not exist yet."""

    notify = DirectNotifyGlobal.directNotify.newCategory('EstateProvisionOperation')

    def __init__(self, provisioner, accountId):
        self.provisioner = provisioner
        self.air = provisioner.air
        self.accountId = accountId
        self.callbacks = []
        self.avList = [0] * NUM_HOUSE_SLOTS
        self.estateId = 0
        self.houseIds = [0] * NUM_HOUSE_SLOTS
        self.slots = []
        self.slot = 0

    def addCallback(self, callback):
        if callback is not None:
            self.callbacks.append(callback)

    def start(self):
        self.air.dbInterface.queryObject(self.air.dbId, self.accountId,
                                         self.__handleAccountRetrieved)

    def __handleAccountRetrieved(self, dclass, fields):
        if dclass != self.air.dclassesByName['AstronAccountAI']:
            self.notify.warning('Could not read account %s!' % self.accountId)
            self.__finish()
            return

        avList = list(fields.get('ACCOUNT_AV_SET') or [])[:NUM_HOUSE_SLOTS]
        avList += [0] * (NUM_HOUSE_SLOTS - len(avList))
        self.avList = avList
        self.estateId = fields.get('ESTATE_ID') or 0
        if self.estateId:
            self.__provisionHouses()
            return

        self.estateId = self.provisioner.pendingEstates.get(self.accountId, 0)
        if self.estateId:
            # An earlier attempt created this record but never got its link
            # onto the account; link that one instead of making another.
            self.__linkEstate()
            return

        self.__createEstate()

    def __createEstate(self):
        fields = {'DcObjectType': 'DistributedEstate'}
        for slot in range(NUM_HOUSE_SLOTS):
            fields['setSlot%dToonId' % slot] = self.avList[slot]
            fields['setSlot%dItems' % slot] = []

        self.air.dbInterface.createObject(self.air.dbId,
                                          self.air.dclassesByName['DistributedEstateAI'],
                                          fields, self.__handleEstateCreated)

    def __handleEstateCreated(self, estateId):
        if not estateId:
            self.notify.warning('Failed to create an estate for account %s!' % self.accountId)
            self.__finish()
            return

        self.estateId = estateId
        self.provisioner.pendingEstates[self.accountId] = estateId
        self.__linkEstate()

    def __linkEstate(self):
        self.air.dbInterface.updateObject(self.air.dbId, self.accountId,
                                          self.air.dclassesByName['AstronAccountAI'],
                                          {'ESTATE_ID': self.estateId},
                                          {'ESTATE_ID': 0},
                                          self.__handleEstateLinked)

    def __handleEstateLinked(self, fields):
        if fields:
            estateId = fields.get('ESTATE_ID') or 0
            if estateId:
                # Somebody else linked an estate to this account first; that
                # one wins and the record we made is left unreferenced.
                self.estateId = estateId
                self.provisioner.pendingEstates.pop(self.accountId, None)
            else:
                # The link did not take.  Keep the record we created so the
                # next request retries the link instead of creating another.
                self.__finish()
                return
        else:
            self.provisioner.pendingEstates.pop(self.accountId, None)

        self.__provisionHouses()

    def __provisionHouses(self):
        self.slots = [slot for slot in range(NUM_HOUSE_SLOTS) if self.avList[slot]]
        self.__nextSlot()

    def __nextSlot(self):
        while self.slots:
            self.slot = self.slots.pop(0)
            avId = self.avList[self.slot]
            toon = self.air.doId2do.get(avId)
            if toon is not None:
                houseId = toon.getHouseId()
                if houseId:
                    self.houseIds[self.slot] = houseId
                    continue

                self.__createHouse()
                return

            self.air.dbInterface.queryObject(self.air.dbId, avId,
                                             self.__handleAvatarRetrieved)
            return

        self.__finish()

    def __handleAvatarRetrieved(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedToonAI']:
            self.notify.warning('Could not read avatar %s!' % self.avList[self.slot])
            self.__nextSlot()
            return

        houseId = fields.get('setHouseId') or 0
        if houseId:
            self.houseIds[self.slot] = houseId
            self.__nextSlot()
            return

        self.__createHouse()

    def __createHouse(self):
        fields = {'DcObjectType': 'DistributedHouse',
                  'setAvatarId': self.avList[self.slot],
                  'setName': '',
                  'setHouseType': 0,
                  'setGardenPos': self.slot,
                  'setColor': self.slot,
                  'setAtticItems': b'',
                  'setInteriorItems': b'',
                  'setAtticWallpaper': b'',
                  'setInteriorWallpaper': b'',
                  'setAtticWindows': b'',
                  'setInteriorWindows': b'',
                  'setDeletedItems': b''}

        self.air.dbInterface.createObject(self.air.dbId,
                                          self.air.dclassesByName['DistributedHouseAI'],
                                          fields, self.__handleHouseCreated)

    def __handleHouseCreated(self, houseId):
        if not houseId:
            self.notify.warning('Failed to create a house for avatar %s!' % self.avList[self.slot])
            self.__nextSlot()
            return

        self.houseIds[self.slot] = houseId
        avId = self.avList[self.slot]
        toon = self.air.doId2do.get(avId)
        if toon is not None:
            toon.b_setHouseId(houseId)
            self.__nextSlot()
            return

        self.air.dbInterface.updateObject(self.air.dbId, avId,
                                          self.air.dclassesByName['DistributedToonAI'],
                                          {'setHouseId': houseId},
                                          {'setHouseId': 0},
                                          self.__handleHouseLinked)

    def __handleHouseLinked(self, fields):
        if fields:
            # The avatar was given a house elsewhere while we were working.
            self.houseIds[self.slot] = fields.get('setHouseId') or self.houseIds[self.slot]

        self.__nextSlot()

    def __finish(self):
        self.provisioner.operationDone(self)
        for callback in self.callbacks:
            callback(self.estateId, self.houseIds)

        self.callbacks = []


class EstateProvisioner:
    """Serializes estate provisioning per account, so two requests arriving
    while the database work is in flight share a single operation."""

    notify = DirectNotifyGlobal.directNotify.newCategory('EstateProvisioner')

    def __init__(self, air):
        self.air = air
        self.operations = {}
        # accountId -> estate record created but not yet linked
        self.pendingEstates = {}

    def provision(self, accountId, callback=None):
        operation = self.operations.get(accountId)
        if operation is not None:
            operation.addCallback(callback)
            return operation

        operation = EstateProvisionOperation(self, accountId)
        self.operations[accountId] = operation
        operation.addCallback(callback)
        operation.start()
        return operation

    def operationDone(self, operation):
        if self.operations.get(operation.accountId) is operation:
            del self.operations[operation.accountId]
