from portals.aumass import AumassPortal
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
}

DEFAULT_PORTALS = list(PORTALS)

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
}
