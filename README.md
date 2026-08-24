# PV- und Batteriespeicher-Projekte (Deutschland)

Täglich um 00:05 holt das Tool die Bekanntmachungen des **Vortags**, filtert auf Photovoltaik und Batteriespeicher und speichert die Treffer lokal.

Der [Bekanntmachungsservice](https://oeffentlichevergabe.de/) allein reicht nicht: Unterschwellenverfahren stehen oft nur auf Landes- und Kommunalportalen.

**21 öffentliche Portale**, Standard ist alle. Ohne Login, ohne Unterlagen-Download.

## Öffentlich vs. Login (DTVP)

[id.dtvp.de](https://id.dtvp.de/) ist nur die **Anmeldeseite** (Bieterraum). Das Tool meldet sich dort nicht an und liest dort nichts.

Die Treffer kommen von der **öffentlichen Suche** auf [www.dtvp.de](https://www.dtvp.de): Titel, Auftraggeber, Datum, Frist, Stichworte. Dafür braucht man kein Konto.

| Quelle | Zugang | Im Tool |
|---|---|---|
| Bekanntmachungsliste www.dtvp.de | öffentlich | ja |
| Verfahrensangaben auf einem Landesportal (z. B. [vergabe.niedersachsen.de](https://vergabe.niedersachsen.de/)) | oft öffentlich | ja, wenn die Seite ohne Login da ist (Beginn/Ende, kWp, …) |
| Bieterraum / Leistungsverzeichnis hinter id.dtvp.de | Login | nein. Der Link in der Liste ist zum selbst Öffnen |

Deshalb fehlen bei manchen DTVP-Verfahren Fläche, kWp und Projektende: die stehen nur in den Unterlagen hinter der Anmeldung. Dasselbe gilt für andere Portale, sobald die Detailseite auf eine Login-Seite umleitet.

## Abdeckung der Länder

Öffentlich ohne Login sind alle 16 Länder abgedeckt, soweit es eine freie Suche gibt.

| Land | Quelle im Tool |
|---|---|
| Baden-Württemberg | `landbw` — [vergabe.landbw.de](https://vergabe.landbw.de/) |
| Bayern (Kommunen) | `aumass` — [plattform.aumass.de](https://plattform.aumass.de/Tender/Search/0) |
| Berlin | `berlin` — [vergabekooperation.berlin](https://vergabekooperation.berlin/) |
| Brandenburg | `vergabe_brandenburg` — [vergabemarktplatz.brandenburg.de](https://vergabemarktplatz.brandenburg.de/) |
| Bremen | `bremen` — [vergabe.bremen.de](https://vergabe.bremen.de/) |
| Hamburg | nicht öffentlich (Login) |
| Hessen | `hessen` — [vergabe.hessen.de](https://vergabe.hessen.de/) (oft 503) |
| Mecklenburg-Vorpommern | `evergabe_mv` — [evergabe-mv.de](https://www.evergabe-mv.de/) |
| Niedersachsen | `vergabe_niedersachsen` — [vergabe.niedersachsen.de](https://vergabe.niedersachsen.de/) |
| Nordrhein-Westfalen | `evergabe_nrw` plus Ruhr, Rheinland, Westfalen, BLB |
| Rheinland-Pfalz | `vergabe_rlp` — [vergabe.rlp.de](https://www.vergabe.rlp.de/) |
| Saarland | `saarland` — [Landesliste](https://www.saarland.de/mibs/DE/portale/ausschreibungen/aktuelles/neue-veroeffentlichungen) |
| Sachsen | `sachsen` — [evergabe.sachsen.de](https://evergabe.sachsen.de/) |
| Sachsen-Anhalt | `sachsen_anhalt` — [evergabe.sachsen-anhalt.de](https://evergabe.sachsen-anhalt.de/) |
| Schleswig-Holstein | kein eigenes Listenportal (`vergabe.schleswig-holstein.de` = 403); Kommunen über **DTVP** |
| Thüringen | `thueringen` — [verwaltung.thueringen.de/evergabe](https://verwaltung.thueringen.de/evergabe) (oft dieselben Verfahren wie evergabe-online) |

Dazu bundesweit: `oeffentlichevergabe`, `dtvp`, `evergabe_online`.

Dasselbe Verfahren kann auf mehreren Portalen stehen (z. B. DTVP + Landesportal, Thüringen + evergabe-online).

## Was noch fehlt (Login oder Abo)

Diese Portale sind **nicht** im Tool. Die Suche liegt hinter Login, Paywall oder Abo — ohne Konto gibt es keine öffentliche Trefferliste. Ein Scraper wird nicht gebaut.

| Portal | Was dort fehlt | Warum nicht drin |
|---|---|---|
| [Hamburg eVergabe](https://fbhh-evergabe.web.hamburg.de/) | Hamburg-Land und städtische Verfahren | Login (`Login.aspx`), keine öffentliche Suche |
| [BayVeBe](https://www.vergabe.bayern.de/) | Bayern-Land (Ministerien, Staatliche Bauämter) | Website-Suche hinter Login. Kommunen laufen über `aumass` |
| [HAD Onlinesuche](https://www.had.de/) | Aggregator, viele Kommunen | nur mit Zugang |
| [Vergabe24](https://www.vergabe24.de/) | Aggregator / Abo-Marktplatz | Paywall |
| [subreport ELViS](https://www.subreport.de/) | Aggregator, u. a. Kommunen | Login/Abo, keine öffentliche Suche |

Mit einem Firmenkonto für **Hamburg** oder **BayVeBe** kämen die letzten Landeslücken dazu. HAD, Vergabe24 und ELViS sind Doppelungen zu Portalen, die wir schon öffentlich abfragen — lohnt sich nur, wenn dort nachweislich Verfahren stehen, die nirgends sonst erscheinen.

## Portale und Kurzformen

`--portal` akzeptiert den Namen oder den Alias.

| `--portal` | Alias | Plattform |
|---|---|---|
| `oeffentlichevergabe` | `ov` | Bekanntmachungsservice Bund |
| `dtvp` | | DTVP, viele Kommunen und Stadtwerke |
| `evergabe_online` | `eo`, `bund` | e-Vergabe des Bundes |
| `evergabe_nrw` | `nrw` | NRW-Landesmarktplatz |
| `vergabe_ruhr` | `ruhr` | Ruhr-Kommunen |
| `vmp_rheinland` | `rheinland` | Rheinland-Kommunen |
| `vergabe_westfalen` | `westfalen` | Westfalen-Kommunen |
| `evergabe_blb` | `blb` | BLB NRW |
| `vergabe_rlp` | `rlp` | Rheinland-Pfalz |
| `vergabe_brandenburg` | `bb` | Brandenburg |
| `evergabe_mv` | `mv` | Mecklenburg-Vorpommern |
| `vergabe_niedersachsen` | `ni`, `nds` | Niedersachsen |
| `berlin` | | Berlin |
| `hessen` | | Hessen |
| `landbw` | `bw` | Baden-Württemberg |
| `sachsen` | `sn` | Sachsen |
| `bremen` | `hb` | Bremen |
| `aumass` | `by`, `bayern` | bayerische Kommunen |
| `sachsen_anhalt` | `st`, `lsa` | Sachsen-Anhalt |
| `thueringen` | `th` | Thüringen |
| `saarland` | `sl` | Saarland |

## Einmal einrichten

Im Ordner `Ausschreibungen`:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Windows-Aufgabe (00:05):

```bat
powershell -ExecutionPolicy Bypass -File jobs\setup_windows_task.ps1
```

## Nutzen

```bat
.venv\Scripts\python jobs\daily.py
```

- Standard: **gestern** (Europe/Berlin), **alle** Portale
- Zum Testen heute: `python jobs/daily.py --today`
- Bestimmtes Datum: `python jobs/daily.py --date 2026-08-17`
- Einzeln oder mehrere: `--portal st --portal th --portal sl`
- Alle explizit: `--portal all`

Anzeige:

```bat
.venv\Scripts\python app.py
```

Browser: http://127.0.0.1:8000

In der Liste: **Jetzt suchen** startet dieselbe Abfrage wie um 00:05 (Bekanntmachungen von **gestern**). Der Lauf dauert oft mehrere Minuten; die Seite lädt danach neu. Ein zweiter Klick während eines Laufs startet nichts extra.

## Docker und Railway

Lokal mit Docker:

```bat
docker compose up --build
```

Liste: http://127.0.0.1:8000  
Einmaliger Tageslauf (gleiche Datenbank): `docker compose --profile job run --rm daily`

Auf [Railway](https://railway.app): Repo verbinden, Build nutzt das `Dockerfile`. Wichtig:

1. **Volume** anlegen und nach `/data` mounten (sonst ist die SQLite-Datei nach jedem Deploy weg).
2. Variable `DATA_DIR=/data` setzen (im Image schon Standard).
3. Optional **`RUN_SECRET`** auf ein echtes Passwort setzen (nicht `true`). Dann erscheint neben dem Button ein Feld, und nur mit diesem Passwort startet die Suche. `true`/`false` schaltet nichts extra.

Der tägliche Lauf um **00:05 Europe/Berlin** läuft im Web-Dienst selbst (interner Scheduler, `ENABLE_SCHEDULER=1` im Image gesetzt). Kein zweiter Cron-Dienst nötig — praktisch, weil ein Railway-Volume ohnehin nur an einen Dienst hängt. Der Web-Dienst muss dafür durchlaufen (Standard).

Die Railway-URL der Liste ist ohne Login erreichbar. Nicht öffentlich teilen, wenn die Treffer intern bleiben sollen.

Ohne Volume bleiben Treffer nach einem Deploy nicht erhalten. Der Button startet denselben Lauf jederzeit von Hand.

Dateien:

- `data/notices.db` — alle geprüften Projekte (in Docker/Railway: `$DATA_DIR/notices.db`)
- `data/exports/YYYY-MM-DD.xlsx` — Excel des Stichtags
- `data/exports/aktuell.xlsx` — letzte Auswertung
- `config/filter.yaml` — Stichworte und CPV-Codes

Unterlagen liegen auf der jeweiligen Vergabeplattform, nicht auf oeffentlichevergabe.de.

Filter: Photovoltaik, Batteriespeicher, PV+Speicher. Reine Solarthermie fällt raus. Standalone `PV` kann noch Fehltreffer erzeugen (z. B. Abdichtungsarbeiten).
