from portals.aumass import AumassPortal
from portals.cosuno import CosunoPortal
from portals.dtvp import DtvpPortal
from portals.evergabe_nrw import EvergabeNrwPortal
from portals.evergabe_online import EvergabeOnlinePortal
from portals.netserver import BerlinPortal, BremenPortal, HessenPortal, LandbwPortal, SachsenPortal
from portals.oeffentlichevergabe import OeffentlichevergabePortal
from portals.saarland import SaarlandPortal
from portals.sachsen_anhalt import SachsenAnhaltPortal
from portals.thueringen import ThueringenPortal
from portals.vmp_laender import (
    EvergabeMvPortal,
    VergabeBrandenburgPortal,
    VergabeNiedersachsenPortal,
    VergabeRlpPortal,
)
from portals.vmp_satellites import (
    EvergabeBlbPortal,
    VergabeRuhrPortal,
    VergabeWestfalenPortal,
    VmpRheinlandPortal,
)

PORTALS = {
    "oeffentlichevergabe": OeffentlichevergabePortal,
    "dtvp": DtvpPortal,
    "evergabe_nrw": EvergabeNrwPortal,
    "vergabe_ruhr": VergabeRuhrPortal,
    "vmp_rheinland": VmpRheinlandPortal,
    "vergabe_westfalen": VergabeWestfalenPortal,
    "evergabe_blb": EvergabeBlbPortal,
    "vergabe_rlp": VergabeRlpPortal,
    "vergabe_brandenburg": VergabeBrandenburgPortal,
    "evergabe_mv": EvergabeMvPortal,
    "vergabe_niedersachsen": VergabeNiedersachsenPortal,
    "berlin": BerlinPortal,
    "hessen": HessenPortal,
    "landbw": LandbwPortal,
    "sachsen": SachsenPortal,
    "bremen": BremenPortal,
    "evergabe_online": EvergabeOnlinePortal,
    "aumass": AumassPortal,
    "sachsen_anhalt": SachsenAnhaltPortal,
    "thueringen": ThueringenPortal,
    "saarland": SaarlandPortal,
    "cosuno": CosunoPortal,
}

DEFAULT_PORTALS = list(PORTALS)

PORTAL_LABELS = {
    "oeffentlichevergabe": "Bekanntmachungsservice Bund",
    "dtvp": "DTVP",
    "evergabe_nrw": "eVergabe.NRW",
    "vergabe_ruhr": "Vergabemarktplatz Metropole Ruhr",
    "vmp_rheinland": "VMP Rheinland",
    "vergabe_westfalen": "Vergabe Westfalen",
    "evergabe_blb": "eVergabe BLB NRW",
    "vergabe_rlp": "Vergabemarktplatz Rheinland-Pfalz",
    "vergabe_brandenburg": "Vergabemarktplatz Brandenburg",
    "evergabe_mv": "eVergabe Mecklenburg-Vorpommern",
    "vergabe_niedersachsen": "Vergabe Niedersachsen",
    "berlin": "Vergabekooperation Berlin",
    "hessen": "Vergabe Hessen",
    "landbw": "Vergabemarktplatz Baden-Württemberg",
    "sachsen": "eVergabe Sachsen",
    "bremen": "Vergabe Bremen",
    "evergabe_online": "e-Vergabe Bund",
    "aumass": "AUMASs Bayern",
    "sachsen_anhalt": "eVergabe Sachsen-Anhalt",
    "thueringen": "eVergabe Thüringen",
    "saarland": "Ausschreibungen Saarland",
    "cosuno": "Cosuno Marktplatz",
}

# Startseite, wenn die Portal-Klasse keine öffentliche Suche als base hat.
PORTAL_HOME = {
    "cosuno": "https://www.cosuno.com/de/marketplace",
    "oeffentlichevergabe": "https://www.oeffentlichevergabe.de",
}


def _sort_label(label: str) -> str:
    return (
        (label or "")
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def portal_label(key: str) -> str:
    return PORTAL_LABELS.get(key, key)


def portal_home(key: str) -> str:
    if key in PORTAL_HOME:
        return PORTAL_HOME[key]
    cls = PORTALS.get(key)
    return (getattr(cls, "base", "") or "").rstrip("/") if cls else ""


def portal_catalog(keys=None) -> list[dict]:
    """Portale mit Anzeigename und Start-URL, alphabetisch nach Name."""
    keys = keys if keys is not None else DEFAULT_PORTALS
    entries = [
        {"key": key, "label": portal_label(key), "url": portal_home(key)}
        for key in keys
    ]
    entries.sort(key=lambda e: _sort_label(e["label"]))
    return entries


def portal_labels(keys=None) -> list[str]:
    return [entry["label"] for entry in portal_catalog(keys)]

ALIASES = {
    "nrw": "evergabe_nrw",
    "ov": "oeffentlichevergabe",
    "ruhr": "vergabe_ruhr",
    "rheinland": "vmp_rheinland",
    "westfalen": "vergabe_westfalen",
    "blb": "evergabe_blb",
    "rlp": "vergabe_rlp",
    "brandenburg": "vergabe_brandenburg",
    "bb": "vergabe_brandenburg",
    "mv": "evergabe_mv",
    "ni": "vergabe_niedersachsen",
    "nds": "vergabe_niedersachsen",
    "niedersachsen": "vergabe_niedersachsen",
    "bw": "landbw",
    "baden": "landbw",
    "sn": "sachsen",
    "hb": "bremen",
    "eo": "evergabe_online",
    "bund": "evergabe_online",
    "by": "aumass",
    "bayern": "aumass",
    "st": "sachsen_anhalt",
    "lsa": "sachsen_anhalt",
    "th": "thueringen",
    "sl": "saarland",
    "cs": "cosuno",
}
