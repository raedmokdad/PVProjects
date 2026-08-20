from __future__ import annotations

LOGIN_MARKERS = ("openid-connect", "id.dtvp.de", "/auth?", "realms/")

# Öffentliche bzw. offizielle Projektseite, wenn die gespeicherte URL fehlt oder nur Login ist.
CLICK_FALLBACK = {
    "dtvp": "https://www.dtvp.de/Center/secured/company/projectForwarding.do?pid={pid}",
    "evergabe_nrw": "https://www.evergabe.nrw.de/VMPCenter/public/company/projectForwarding.do?pid={pid}",
    "vergabe_ruhr": "https://www.vergabe.metropoleruhr.de/VMPSatellite/public/company/projectForwarding.do?pid={pid}",
    "vmp_rheinland": "https://www.vmp-rheinland.de/VMPSatellite/public/company/projectForwarding.do?pid={pid}",
    "vergabe_westfalen": "https://www.vergabe-westfalen.de/VMPSatellite/public/company/projectForwarding.do?pid={pid}",
    "evergabe_blb": "https://evergabe.blb.nrw.de/Vergabe/public/company/projectForwarding.do?pid={pid}",
    "vergabe_rlp": "https://www.vergabe.rlp.de/VMPCenter/public/company/projectForwarding.do?pid={pid}",
    "vergabe_brandenburg": "https://vergabemarktplatz.brandenburg.de/VMPCenter/public/company/projectForwarding.do?pid={pid}",
    "evergabe_mv": "https://www.evergabe-mv.de/Satellite/public/company/projectForwarding.do?pid={pid}",
    "vergabe_niedersachsen": "https://vergabe.niedersachsen.de/Satellite/public/company/projectForwarding.do?pid={pid}",
    "berlin": "https://vergabekooperation.berlin/NetServer/PublicationControllerServlet?function=Detail&TOID={pid}&Category=InvitationToTender",
    "hessen": "https://vergabe.hessen.de/NetServer/PublicationControllerServlet?function=Detail&TOID={pid}&Category=InvitationToTender",
    "landbw": "https://vergabe.landbw.de/NetServer/PublicationControllerServlet?function=Detail&TOID={pid}&Category=InvitationToTender",
    "sachsen": "https://evergabe.sachsen.de/NetServer/PublicationControllerServlet?function=Detail&TOID={pid}&Category=InvitationToTender",
    "bremen": "https://vergabe.bremen.de/NetServer/PublicationControllerServlet?function=Detail&TOID={pid}&Category=InvitationToTender",
    "evergabe_online": "https://www.evergabe-online.de/tenderdetails.html?id={pid}",
    "aumass": "https://plattform.aumass.de/Veroeffentlichung/{pid}",
    "thueringen": "https://www.evergabe-online.de/tenderdetails.html?id={pid}",
    "oeffentlichevergabe": "https://oeffentlichevergabe.de/ui/de/search/details?noticeId={pid}",
}


def is_login_url(url: str) -> bool:
    lower = (url or "").lower()
    return any(marker in lower for marker in LOGIN_MARKERS)


def notice_click_url(portal: str, pid: str, project_url: str = "") -> str:
    url = (project_url or "").strip()
    if url and not is_login_url(url):
        return url
    tmpl = CLICK_FALLBACK.get(portal or "")
    if tmpl and pid:
        value = str(pid)
        if portal == "aumass":
            value = value.lower()
        return tmpl.format(pid=value)
    return url
