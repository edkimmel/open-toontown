"""Strict decoding of a single catalog item blob sent up by a client.

`CatalogItem.getItem` is deliberately forgiving: `decodeCatalogItem` turns
any failure into a `CatalogInvalidItem` (CatalogItem.py:443-458) and nothing
checks that the blob was fully consumed (CatalogItem.py:467-475), so a
truncated, padded or forged blob still "decodes".  The AI needs the opposite
answer, so it can refuse the purchase instead of acting on garbage.
"""
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator

from . import CatalogItem
from . import CatalogItemTypes


def decodeVerifiedItem(blob, store=0):
    """Decodes exactly one catalog item from blob, or returns None.

    The blob must carry the current version byte, a registered type code,
    and no bytes beyond the single item it encodes.
    """
    if not blob:
        return None
    dg = PyDatagram(blob)
    try:
        di = PyDatagramIterator(dg)
        versionNumber = di.getUint8()
        if versionNumber != CatalogItem.CatalogItemVersion:
            return None
        flags = di.getUint8()
        typeIndex = flags & CatalogItemTypes.CatalogItemTypeMask
        if typeIndex not in list(CatalogItemTypes.CatalogItemTypes.values()):
            return None
        di = PyDatagramIterator(dg)
        di.getUint8()
    except Exception:
        return None

    item = CatalogItem.decodeCatalogItem(di, versionNumber, store)
    from . import CatalogInvalidItem
    if isinstance(item, CatalogInvalidItem.CatalogInvalidItem):
        return None
    try:
        if di.getRemainingSize() != 0:
            return None
    except Exception:
        return None
    return item
