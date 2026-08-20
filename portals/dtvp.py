from portals.cosinex import CosinexJsonPortal


class DtvpPortal(CosinexJsonPortal):
    """Deutsches Vergabeportal — bundesweit, inkl. Kommunen/Stadtwerke außerhalb evergabe.nrw."""

    name = "dtvp"
    base = "https://www.dtvp.de"
    prefix = "/Center"
    search_texts = (
        "Photovoltaik",
        "PV-Anlage",
        "Batteriespeicher",
        "Stromspeicher",
        "Solarmodul",
        "kWp",
    )
