from portals.cosinex import CosinexJsonPortal


class EvergabeNrwPortal(CosinexJsonPortal):
    name = "evergabe_nrw"
    base = "https://www.evergabe.nrw.de"
    prefix = "/VMPCenter"
