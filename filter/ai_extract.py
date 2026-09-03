"""KI-Extraktion von Kenngrößen aus Ausschreibungstexten.

Wird nach apply_facts() aufgerufen und füllt nur Felder, die Regex leer gelassen hat.
Ohne OPENAI_API_KEY tut die Funktion nichts — kein Fehler, kein Absturz.
"""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portals.base import Notice

try:
    from openai import OpenAI
except ImportError:  # openai nicht installiert → KI deaktiviert
    OpenAI = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Modell als Konstante — bei Bedarf hier ändern.
AI_MODEL = "gpt-4o-mini"

# Maximale Zeichen des Texts, die an die KI geschickt werden.
# Titel + Detailtext; bei sehr langen Texten kürzen wir, damit die Kosten überschaubar bleiben.
MAX_CHARS = 4000

SYSTEM_PROMPT = """\
Du extrahierst strukturierte Kenngrößen aus deutschen öffentlichen Ausschreibungen für Photovoltaik- und Batteriespeicherprojekte.
Antworte ausschließlich mit dem JSON-Objekt gemäß dem vorgegebenen Schema.
Schreibe null, wenn ein Wert im Text nicht vorkommt — erfinde keine Werte.
Schreibe in das evidence-Feld den genauen Originaltext-Ausschnitt (max. 120 Zeichen), aus dem du den Wert entnommen hast.
Datumsformat: YYYY-MM-DD. Zahlen als Dezimalzahl (kein Tausendertrennzeichen).
"""

# JSON-Schema für strict: true
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "capacity_kwp": {
            "type": ["number", "null"],
            "description": "Anlagenleistung in kWp, z. B. 50.0",
        },
        "start_on": {
            "type": ["string", "null"],
            "description": "Baubeginn oder Projektstart als ISO-Datum YYYY-MM-DD",
        },
        "completion_on": {
            "type": ["string", "null"],
            "description": "Projektende / Fertigstellung als ISO-Datum YYYY-MM-DD",
        },
        "area_m2": {
            "type": ["number", "null"],
            "description": "Dachfläche oder Modulfläche in m²",
        },
        "is_new_build": {
            "type": ["boolean", "null"],
            "description": "true = Neubau, false = Bestandsgebäude, null = nicht erkennbar",
        },
        "has_transformer": {
            "type": ["boolean", "null"],
            "description": "true = Trafo/Trafostation vorhanden oder gefordert, false = explizit nicht, null = nicht erkennbar",
        },
        "evidence": {
            "type": "string",
            "description": "Originaltext-Ausschnitt als Nachweis für die extrahierten Werte (max. 120 Zeichen)",
        },
    },
    "required": ["capacity_kwp", "start_on", "completion_on", "area_m2", "is_new_build", "has_transformer", "evidence"],
    "additionalProperties": False,
}


def _api_key() -> str:
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def _is_configured() -> bool:
    return bool(_api_key())


def _build_user_text(notice: "Notice") -> str:
    parts = [notice.title or ""]
    if notice.excerpt:
        parts.append(notice.excerpt)
    if notice.detail_text:
        parts.append(notice.detail_text)
    combined = "\n\n".join(p for p in parts if p)
    return combined[:MAX_CHARS]


def ai_extract(notice: "Notice") -> None:
    """Füllt Felder in `notice` per KI. Überschreibt nur None/leere Werte.

    Wenn kein API-Key gesetzt ist, passiert nichts.
    Fehler werden geloggt, aber nie weitergereicht — ein KI-Fehler darf den Lauf nicht abbrechen.
    """
    if not _is_configured():
        return

    # Nur aufrufen, wenn noch mindestens ein Feld fehlt.
    missing = (
        notice.capacity_kwp is None
        or not notice.start_on
        or not notice.completion_on
        or notice.area_m2 is None
        or notice.is_new_build is None
        or notice.has_transformer is None
    )
    if not missing:
        return

    text = _build_user_text(notice)
    if not text.strip():
        return

    try:
        if OpenAI is None:
            return
        client = OpenAI(api_key=_api_key())
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ausschreibung_extraktion",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
            max_tokens=400,
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("ai_extract fehlgeschlagen für %s/%s: %s", notice.portal, notice.pid, exc)
        return

    # Felder nur füllen, wenn Regex sie leer gelassen hat.
    if notice.capacity_kwp is None and data.get("capacity_kwp") is not None:
        notice.capacity_kwp = float(data["capacity_kwp"])

    if not notice.start_on and data.get("start_on"):
        notice.start_on = str(data["start_on"])

    if not notice.completion_on and data.get("completion_on"):
        notice.completion_on = str(data["completion_on"])

    if notice.area_m2 is None and data.get("area_m2") is not None:
        notice.area_m2 = float(data["area_m2"])

    if notice.is_new_build is None and data.get("is_new_build") is not None:
        notice.is_new_build = bool(data["is_new_build"])

    if notice.has_transformer is None and data.get("has_transformer") is not None:
        notice.has_transformer = bool(data["has_transformer"])

    ev = (data.get("evidence") or "").strip()
    if ev:
        logger.debug("ai_extract evidence [%s/%s]: %s", notice.portal, notice.pid, ev[:120])
