"""
Bot Telegram con scansione REAL-TIME via Mini App (Web App)
=============================================================

Questa versione usa una Telegram "Web App" (Mini App): una pagina che si apre
DENTRO la chat e usa la fotocamera del telefono in diretta (via browser),
riconoscendo i codici in tempo reale con la libreria html5-qrcode -- senza
scattare foto manualmente. Quando ha raccolto 55 righe, la pagina manda i
dati al bot in automatico e il bot genera e invia il file Excel.

REQUISITI
---------
1. Il file webapp/index.html va pubblicato su un URL HTTPS pubblico
   (Telegram richiede HTTPS per le Web App). Opzioni semplici:
     - GitHub Pages (gratis)
     - Netlify / Vercel (gratis)
     - Un tuo server con certificato TLS
     - Per test rapidi: ngrok (es. "ngrok http 8000" servendo la cartella
       webapp/ con "python -m http.server 8000")

2. Su @BotFather:
     - crea il bot e prendi il TOKEN
     - (facoltativo ma consigliato) imposta il bottone del menu con
       /setmenubutton per aprire direttamente la Web App

3. Installa le dipendenze Python:

     pip install python-telegram-bot==21.* openpyxl

4. Imposta le variabili d'ambiente:

     export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
     export WEBAPP_URL="https://tuodominio.esempio/index.html"

5. Avvia:

     python bot_webapp.py

COME LO VIVE L'UTENTE
----------------------
- Scrive /start al bot
- Il bot mostra un bottone "Apri fotocamera" (Web App)
- Si apre la pagina dentro Telegram, la fotocamera parte da sola
- L'utente inquadra i codici: la pagina riconosce in automatico il codice
  che inizia per "d" e quello che inizia per "V" e li segna con una spunta,
  passa alla riga successiva da sola quando trova entrambi
- Dopo 55 righe la pagina si chiude e il bot riceve i dati, genera il file
  .xlsx e lo invia in chat
"""

import io
import json
import logging
import os
from datetime import datetime

from openpyxl import Workbook

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "INSERISCI_QUI_IL_TUO_TOKEN")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://INSERISCI_URL_HTTPS_QUI/index.html")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tastiera = InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "📷 Apri fotocamera e scansiona",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )]]
    )
    await update.message.reply_text(
        "Premi il bottone qui sotto per aprire la fotocamera e iniziare la "
        "scansione in tempo reale. Ti avviserò appena avrò raccolto le 55 "
        "righe e ti manderò subito l'Excel.",
        reply_markup=tastiera,
    )


async def ricevi_dati_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Chiamato quando la Mini App invia i dati con Telegram.WebApp.sendData()."""
    dati_grezzi = update.effective_message.web_app_data.data
    try:
        payload = json.loads(dati_grezzi)
        righe = payload["righe"]
    except (json.JSONDecodeError, KeyError):
        await update.message.reply_text("Dati ricevuti dalla Web App non validi.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Codici"
    ws.append(["Codice D", "Codice V", "Concatenazione"])

    for r in righe:
        ws.append([r.get("d", ""), r.get("v", ""), r.get("concat", "")])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nome_file = f"codici_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    await update.message.reply_document(
        document=buffer,
        filename=nome_file,
        caption=f"Fatto! {len(righe)} righe acquisite in tempo reale.",
    )


def main() -> None:
    if TOKEN == "INSERISCI_QUI_IL_TUO_TOKEN":
        raise SystemExit(
            "Imposta TELEGRAM_BOT_TOKEN con il token ottenuto da @BotFather."
        )
    if "INSERISCI_URL_HTTPS_QUI" in WEBAPP_URL:
        raise SystemExit(
            "Imposta WEBAPP_URL con l'URL HTTPS pubblico dove hai pubblicato "
            "webapp/index.html."
        )

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, ricevi_dati_webapp))

    logger.info("Bot avviato, in ascolto...")
    app.run_polling()


if __name__ == "__main__":
    main()
