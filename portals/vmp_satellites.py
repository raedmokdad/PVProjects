from portals.cosinex import CosinexHtmlPortal


class VergabeRuhrPortal(CosinexHtmlPortal):
    name = "vergabe_ruhr"
    base = "https://www.vergabe.metropoleruhr.de"
    prefix = "/VMPSatellite"


class VmpRheinlandPortal(CosinexHtmlPortal):
    name = "vmp_rheinland"
    base = "https://www.vmp-rheinland.de"
    prefix = "/VMPSatellite"


class VergabeWestfalenPortal(CosinexHtmlPortal):
    name = "vergabe_westfalen"
    base = "https://www.vergabe-westfalen.de"
    prefix = "/VMPSatellite"


class EvergabeBlbPortal(CosinexHtmlPortal):
    name = "evergabe_blb"
    base = "https://evergabe.blb.nrw.de"
    prefix = "/Vergabe"
