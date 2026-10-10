"""
Configurazione centralizzata di ZampaViva TikTok.

I segreti NON stanno nella cartella del progetto (che puo' finire su Google
Drive): vengono letti da  %USERPROFILE%\\.zampaviva\\.env  oppure dal percorso
indicato nella variabile d'ambiente ZAMPAVIVA_ENV. Nessuna chiave hardcoded.
"""
import os
import sys

DIR_PROGETTO = os.path.dirname(os.path.abspath(__file__))
FILE_ENV = os.getenv(
    "ZAMPAVIVA_ENV",
    os.path.join(os.path.expanduser("~"), ".zampaviva", ".env"),
)

try:
    from dotenv import load_dotenv
    load_dotenv(FILE_ENV)
except ImportError:
    pass


def _get(nome, default=None, obbligatoria=False):
    valore = os.getenv(nome, default)
    if isinstance(valore, str):
        valore = valore.strip()
    if valore and valore.startswith("inserisci_qui"):
        valore = None
    if obbligatoria and not valore:
        print(f"[Config] ERRORE: la variabile '{nome}' non e' configurata.")
        print(f"         Impostala in {FILE_ENV}")
        sys.exit(1)
    return valore


# ---------------------------------------------------------------- API esterne
GROQ_API_KEY = _get("GROQ_API_KEY", obbligatoria=True)
# Opzionale: senza, il video usa solo le foto del prodotto
PEXELS_API_KEY = _get("PEXELS_API_KEY")

# ------------------------------------------------------------------- Negozio
NOME_NEGOZIO = _get("NOME_NEGOZIO", "ZampaViva")
URL_NEGOZIO = _get("URL_NEGOZIO", "https://zampaviva-5.myshopify.com").rstrip("/")
LINGUA = _get("LINGUA", "it")

# ------------------------------------------------------------------ Voce (TTS)
#   it-IT-IsabellaNeural  (femminile, brillante -> calda e simpatica)
#   it-IT-ElsaNeural      (femminile, morbida)
#   it-IT-DiegoNeural     (maschile, energico)
VOCE_TTS = _get("VOCE_TTS", "it-IT-IsabellaNeural")
VOCE_VELOCITA = _get("VOCE_VELOCITA", "+8%")
VOCE_PITCH = _get("VOCE_PITCH", "+4Hz")

# ---------------------------------------------------------------- Rendering
VIDEO_W = int(_get("VIDEO_W", "1080"))
VIDEO_H = int(_get("VIDEO_H", "1920"))
FPS = int(_get("FPS", "30"))
STACCO_MIN = float(_get("STACCO_MIN", "2.0"))
STACCO_MAX = float(_get("STACCO_MAX", "3.2"))
WHISPER_MODEL = _get("WHISPER_MODEL", "base")

# ------------------------------------------------------------------ Materiale
# Foto del prodotto dal catalogo Shopify + clip stock di cani e gatti da Pexels
MAX_IMMAGINI_PRODOTTO = int(_get("MAX_IMMAGINI_PRODOTTO", "5"))
NUM_CLIP_PEXELS = int(_get("NUM_CLIP_PEXELS", "3"))
# Le foto prodotto (quasi sempre quadrate) stanno in un riquadro su sfondo
# sfocato. 1.0 = larghezza piena.
ZOOM_PRODOTTO = float(_get("ZOOM_PRODOTTO", "0.92"))

# ------------------------------------------------ Notifiche Telegram
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")
TELEGRAM_ATTIVO = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# ---------------------------------------------------------------------- File
FILE_CRONOLOGIA = os.path.join(DIR_PROGETTO, "cronologia_zampaviva.json")
DIR_TEMP = os.path.join(DIR_PROGETTO, "temp_assets")
DIR_OUTPUT = os.path.join(DIR_PROGETTO, "output_videos")

os.makedirs(DIR_TEMP, exist_ok=True)
os.makedirs(DIR_OUTPUT, exist_ok=True)
