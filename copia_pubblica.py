"""Copia pubblica del video ZampaViva, per programmarlo su TikTok.

Il video esiste solo sul runner di GitHub. La stanza degli agenti
(davidedurazzi-sito, cartella stanza/) lo propone a Davide nel pannello e,
se lui approva, lo programma su TikTok: per farlo serve il file a un
indirizzo pubblico. Qui lo si carica su Vercel Blob e l'indirizzo finisce
nella cronologia, accanto al prodotto.

Senza BLOB_READ_WRITE_TOKEN non fa niente. Un errore qui non ferma mai la
pipeline: il video e' gia' arrivato su Telegram.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import requests

import config

API = "https://blob.vercel-storage.com"
VERSIONE_API = "9"
CARTELLA = "zampaviva/"
GIORNI_TENUTA = 7           # piano gratuito da 1 GB: un video al giorno sta largo


def _intestazioni(token, **altre):
    h = {"authorization": f"Bearer {token}", "x-api-version": VERSIONE_API}
    h.update(altre)
    return h


def carica(percorso, nome, token):
    """Carica il file e restituisce l'indirizzo pubblico, o None."""
    with open(percorso, "rb") as f:
        r = requests.put(
            API + "/",
            params={"pathname": CARTELLA + nome},
            data=f,
            headers=_intestazioni(token, **{"x-content-type": "video/mp4",
                                            "x-add-random-suffix": "1"}),
            timeout=300,
        )
    if not r.ok:
        print(f"[Warning Copia] Vercel Blob HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.json().get("url")


def pulisci(token, adesso=None):
    """Cancella le copie piu' vecchie di GIORNI_TENUTA. Restituisce quante."""
    adesso = adesso or datetime.now(timezone.utc)
    limite = adesso - timedelta(days=GIORNI_TENUTA)
    r = requests.get(API + "/", params={"prefix": CARTELLA, "limit": "1000"},
                     headers=_intestazioni(token), timeout=30)
    if not r.ok:
        print(f"[Warning Copia] Elenco Vercel Blob HTTP {r.status_code}")
        return 0
    vecchie = []
    for b in r.json().get("blobs", []):
        quando = datetime.fromisoformat(str(b.get("uploadedAt", "")).replace("Z", "+00:00"))
        if quando < limite:
            vecchie.append(b["url"])
    if vecchie:
        requests.post(API + "/delete", json={"urls": vecchie},
                      headers=_intestazioni(token), timeout=30)
    return len(vecchie)


def prepara(percorso_video, dati, didascalia):
    """Campi da aggiungere alla voce di cronologia, o {} se non si puo'."""
    token = (config.BLOB_READ_WRITE_TOKEN or "").strip()
    if not token or not percorso_video or not os.path.exists(percorso_video):
        return {}
    try:
        nome = f"{time.strftime('%Y-%m-%d')}-{dati['prodotto']['handle']}.mp4"
        url = carica(percorso_video, nome, token)
        if not url:
            return {}
        try:
            pulisci(token)
        except Exception as e:
            print(f"[Warning Copia] Pulizia non riuscita: {e}")
        print(f"[Copia] Video pronto per TikTok: {url}")
        return {"video_file_url": url, "didascalia_tiktok": didascalia}
    except Exception as e:
        print(f"[Warning Copia] Copia pubblica non riuscita: {e}")
        return {}
