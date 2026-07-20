"""
Backend OCR con Claude API (vision)
=====================================

Riceve dal frontend un fotogramma (JPEG in base64), lo manda a Claude con
un prompt che chiede di leggere SOLO i due codici (quello che inizia per
"D" e quello che inizia per "V") e risponde in JSON pulito.

La API key resta SEMPRE sul server, mai esposta al browser.

INSTALLAZIONE
--------------
    pip install fastapi uvicorn anthropic python-multipart

AVVIO
-----
    export ANTHROPIC_API_KEY="sk-ant-..."
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import base64
import json
import logging
import os

from anthropic import Anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise RuntimeError("Imposta la variabile d'ambiente ANTHROPIC_API_KEY")

client = Anthropic(api_key=API_KEY)

app = FastAPI(title="OCR Codici Backend")

# In produzione, se frontend e backend sono sullo stesso dominio dietro Nginx
# (come nel setup con /api/ proxato), il CORS non serve. Lo lasciamo aperto
# per facilitare i test in locale.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROMPT = """Guarda l'immagine e trova due codici stampati:
- un codice che inizia con la lettera "D" (maiuscola o minuscola)
- un codice che inizia con la lettera "V" (maiuscola o minuscola)

Rispondi SOLO con un oggetto JSON, senza testo aggiuntivo, in questo formato esatto:
{"d": "<codice trovato o null>", "v": "<codice trovato o null>"}

Se un codice non è visibile o leggibile con certezza, usa null per quel campo.
Non inventare mai un codice: se hai dubbi, metti null.
"""


class OCRRequest(BaseModel):
    image_base64: str  # JPEG in base64, senza prefisso "data:image/jpeg;base64,"


class OCRResponse(BaseModel):
    d: str | None = None
    v: str | None = None


@app.post("/api/ocr", response_model=OCRResponse)
async def leggi_codici(payload: OCRRequest) -> OCRResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Immagine base64 non valida")

    try:
        risposta = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": payload.image_base64,
                            },
                        },
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        )
    except Exception as e:
        logger.exception("Errore chiamata Claude API")
        raise HTTPException(status_code=502, detail=f"Errore API: {e}")

    testo = "".join(
        block.text for block in risposta.content if getattr(block, "type", None) == "text"
    ).strip()

    # Pulizia difensiva: a volte i modelli aggiungono ```json ... ``` attorno
    testo = testo.replace("```json", "").replace("```", "").strip()

    try:
        dati = json.loads(testo)
    except json.JSONDecodeError:
        logger.warning("Risposta non JSON valida: %s", testo)
        return OCRResponse(d=None, v=None)

    d = dati.get("d")
    v = dati.get("v")
    d = None if d in ("null", "", None) else d
    v = None if v in ("null", "", None) else v

    return OCRResponse(d=d, v=v)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
