"""
Backend OCR self-hosted con EasyOCR (GRATUITO, nessuna API a pagamento)
=========================================================================

Riceve dal frontend un fotogramma (JPEG in base64), lo analizza con EasyOCR
(libreria open-source basata su deep learning, gira interamente sul server,
nessun costo per chiamata) e cerca i due codici (uno che inizia per "D",
uno che inizia per "V").

REQUISITI HARDWARE
-------------------
EasyOCR usa PyTorch. Su CPU (nessuna GPU) serve almeno 2 vCPU / 4GB RAM
per tempi di risposta ragionevoli (1-3 secondi per immagine). Su istanze
troppo piccole (es. t2/t3.micro) puo' essere lento o non avviarsi per
mancanza di memoria.

INSTALLAZIONE
--------------
    pip install fastapi uvicorn easyocr pillow numpy python-multipart

Il primo avvio scarica i pesi del modello (~100MB), poi restano in cache.

AVVIO
-----
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import base64
import io
import logging
import re

import easyocr
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OCR Codici Backend (EasyOCR, gratuito)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Caricato una sola volta all'avvio del processo (lento al primo avvio,
# poi resta in memoria per tutte le richieste successive).
logger.info("Caricamento modello EasyOCR in corso...")
reader = easyocr.Reader(["en"], gpu=False)
logger.info("Modello EasyOCR pronto.")

REGEX_D = re.compile(r"\b([dD][A-Za-z0-9]{3,})\b")
REGEX_V = re.compile(r"\b([vV][A-Za-z0-9]{3,})\b")


class OCRRequest(BaseModel):
    image_base64: str  # JPEG in base64, senza prefisso "data:image/jpeg;base64,"


class OCRResponse(BaseModel):
    d: str | None = None
    v: str | None = None


def pulisci_token(testo: str) -> str:
    """Rimuove spazi e caratteri non alfanumerici tipici di errori OCR."""
    return re.sub(r"[^A-Za-z0-9]", "", testo)


@app.post("/api/ocr", response_model=OCRResponse)
async def leggi_codici(payload: OCRRequest) -> OCRResponse:
    try:
        image_bytes = base64.b64decode(payload.image_base64)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Immagine base64 non valida")

    img_np = np.array(img)

    try:
        risultati = reader.readtext(img_np, detail=0)  # lista di stringhe lette
    except Exception as e:
        logger.exception("Errore EasyOCR")
        raise HTTPException(status_code=502, detail=f"Errore OCR: {e}")

    testo_completo = " ".join(risultati)
    testo_pulito_per_match = testo_completo  # i separatori (spazi) aiutano il match \b

    codice_d = None
    codice_v = None

    match_d = REGEX_D.search(testo_pulito_per_match)
    if match_d:
        codice_d = pulisci_token(match_d.group(1))

    match_v = REGEX_V.search(testo_pulito_per_match)
    if match_v:
        codice_v = pulisci_token(match_v.group(1))

    logger.info("OCR letto: %r -> D=%s V=%s", testo_completo, codice_d, codice_v)

    return OCRResponse(d=codice_d, v=codice_v)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

