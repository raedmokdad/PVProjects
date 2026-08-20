from portals.cosinex import CosinexHtmlPortal, CosinexJsonPortal


class VergabeRlpPortal(CosinexJsonPortal):
    name = "vergabe_rlp"
    base = "https://www.vergabe.rlp.de"
    prefix = "/VMPCenter"


class VergabeBrandenburgPortal(CosinexJsonPortal):
    name = "vergabe_brandenburg"
    base = "https://vergabemarktplatz.brandenburg.de"
    prefix = "/VMPCenter"


class EvergabeMvPortal(CosinexHtmlPortal):
    name = "evergabe_mv"
    base = "https://www.evergabe-mv.de"
    prefix = "/Satellite"


class VergabeNiedersachsenPortal(CosinexHtmlPortal):
    name = "vergabe_niedersachsen"
    base = "https://vergabe.niedersachsen.de"
    prefix = "/Satellite"
