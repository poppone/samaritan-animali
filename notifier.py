"""
Consegna su Telegram: il video pronto + la didascalia da copiare.

La pubblicazione su TikTok la fai tu a mano: qui arriva tutto il necessario
(video, testo con hashtag e link del prodotto) per farlo in 30 secondi.

Se le variabili TELEGRAM_* non sono configurate, il modulo non fa nulla
e non blocca mai la pipeline.
"""
import os
import html

import requests

import config

LIMITE_UPLOAD_BOT = 48 * 1024 * 1024      # i bot Telegram si fermano a ~50MB


def _api(metodo):
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{metodo}"


def invia_messaggio(testo):
    if not config.TELEGRAM_ATTIVO:
        return False
    try:
        r = requests.post(
            _api("sendMessage"),
            data={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": testo[:4096],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        if not r.ok:
            print(f"[Warning Telegram] sendMessage HTTP {r.status_code}")
        return r.ok
    except Exception as e:
        print(f"[Warning Telegram] Invio messaggio fallito: {type(e).__name__}")
        return False


def invia_video(percorso, didascalia=""):
    if not config.TELEGRAM_ATTIVO or not os.path.exists(percorso):
        return False
    if os.path.getsize(percorso) > LIMITE_UPLOAD_BOT:
        return invia_messaggio(didascalia + "\n\n(Video troppo grande per Telegram)")
    try:
        with open(percorso, "rb") as video:
            r = requests.post(
                _api("sendVideo"),
                data={
                    "chat_id": config.TELEGRAM_CHAT_ID,
                    "caption": didascalia[:1024],
                    "parse_mode": "HTML",
                    "supports_streaming": "true",
                },
                files={"video": video},
                timeout=300,
            )
        if not r.ok:
            print(f"[Warning Telegram] sendVideo HTTP {r.status_code}")
        return r.ok
    except Exception as e:
        print(f"[Warning Telegram] Invio video fallito: {type(e).__name__}")
        return False


def notifica_video(dati, percorso_video, didascalia_tiktok):
    """Due messaggi: il video con un riepilogo, poi la didascalia da copiare.

    La didascalia sta in un blocco <code>: su Telegram basta toccarla per
    copiarla tutta.
    """
    if not config.TELEGRAM_ATTIVO:
        print("[Telegram] Non configurato: video solo in locale.")
        return False

    e = html.escape
    riepilogo = (
        "<b>DA PUBBLICARE OGGI su TikTok</b>\n"
        f"<b>{e(config.NOME_NEGOZIO)} - video pronto</b>\n\n"
        f"<b>{e(dati['titolo'])}</b>\n"
        f"Prodotto: {e(dati['prodotto']['titolo'])}\n"
        f"Formato: <code>{e(dati['stile'])}</code>\n\n"
        "Scarica il video, tocca la didascalia nel messaggio successivo "
        "per copiarla e pubblica."
    )
    ok_video = invia_video(percorso_video, riepilogo)
    if not ok_video:
        invia_messaggio(riepilogo + "\n\n(Invio del video non riuscito: "
                        f"lo trovi in {e(percorso_video)})")

    ok_testo = invia_messaggio(f"<code>{e(didascalia_tiktok)}</code>")
    return ok_video and ok_testo


def notifica_errore(messaggio):
    invia_messaggio(f"<b>{html.escape(config.NOME_NEGOZIO)} - ERRORE</b>\n\n"
                    f"<pre>{html.escape(messaggio[:1500])}</pre>")
