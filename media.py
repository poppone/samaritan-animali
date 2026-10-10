"""
Procura il materiale visivo di un video ZampaViva.

  1. Foto UFFICIALI del prodotto dal catalogo Shopify del negozio
  2. Clip stock di cani e gatti da Pexels (licenza libera anche per uso
     commerciale), scelte in base alla query scritta da brain.py

L'audio delle clip viene sempre scartato in montaggio: si sente solo la voce.
"""
import os
import re
import random
from io import BytesIO

import requests
from PIL import Image

import config

FALLBACK_QUERY = {
    "cane": ["happy dog", "dog playing", "puppy close up", "dog walking park"],
    "gatto": ["cute cat", "cat playing", "kitten close up", "cat sleeping"],
    "cane e gatto": ["cute cat", "happy dog", "cat and dog", "puppy playing"],
}


# ===========================================================================
# FOTO DEL PRODOTTO (Shopify)
# ===========================================================================
def _url_ridimensionato(src, larghezza=1080):
    """Il CDN Shopify ridimensiona da solo: evita di scaricare foto da 4000px."""
    separatore = "&" if "?" in src else "?"
    return f"{src}{separatore}width={larghezza}"


def scarica_immagini_prodotto(prodotto, quante=None):
    quante = quante or config.MAX_IMMAGINI_PRODOTTO
    percorsi = []
    for i, src in enumerate(prodotto.get("immagini", [])):
        if len(percorsi) >= quante:
            break
        destinazione = os.path.join(config.DIR_TEMP,
                                    f"prod_{prodotto['handle']}_{i}.jpg")
        try:
            r = requests.get(_url_ridimensionato(src), timeout=30)
            r.raise_for_status()
            # Converto sempre in JPEG RGB: le foto possono essere webp/png
            # con trasparenza, che moviepy gestisce male.
            img = Image.open(BytesIO(r.content))
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                fondo = Image.new("RGB", img.size, (255, 255, 255))
                fondo.paste(img, mask=img.split()[-1])
                img = fondo
            else:
                img = img.convert("RGB")
            img.save(destinazione, "JPEG", quality=92)
            percorsi.append(destinazione)
        except Exception as e:
            print(f"[Media] Foto prodotto non scaricata: {e}")

    print(f"[Media] {len(percorsi)} foto di '{prodotto['titolo']}' pronte.")
    return percorsi


# ===========================================================================
# CLIP STOCK (Pexels)
# ===========================================================================
def _cerca_clip_pexels(query, gia_scaricati):
    headers = {"Authorization": config.PEXELS_API_KEY}
    query_pulita = re.sub(r"\b(vertical|short|shorts|tiktok)\b", "", query,
                          flags=re.IGNORECASE).strip()
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query_pulita, "orientation": "portrait", "per_page": 15},
            timeout=12,
        )
        r.raise_for_status()
        video_trovati = r.json().get("videos", [])
    except Exception as e:
        print(f"[Warning Pexels] Ricerca '{query_pulita}' fallita: {e}")
        return []

    random.shuffle(video_trovati)      # varieta' fra un video e l'altro
    risultati = []
    for video in video_trovati:
        if video["id"] in gia_scaricati:
            continue
        file_verticali = [
            f for f in video.get("video_files", [])
            if f.get("height", 0) >= f.get("width", 1)
        ] or video.get("video_files", [])
        if not file_verticali:
            continue
        migliore = min(file_verticali,
                       key=lambda f: abs(f.get("height", 0) - config.VIDEO_H))
        risultati.append((video["id"], migliore["link"]))
    return risultati


def scarica_clip_pexels(query, animale="cane e gatto", quante=None):
    quante = quante or config.NUM_CLIP_PEXELS
    if not config.PEXELS_API_KEY:
        print("[Media] PEXELS_API_KEY non configurata: niente clip stock.")
        return []
    riserve = FALLBACK_QUERY.get(animale, FALLBACK_QUERY["cane e gatto"])
    query_da_provare = [query] + random.sample(riserve, len(riserve))
    percorsi, gia_scaricati = [], set()

    for q in query_da_provare:
        if len(percorsi) >= quante:
            break
        for video_id, link in _cerca_clip_pexels(q, gia_scaricati):
            if len(percorsi) >= quante:
                break
            destinazione = os.path.join(config.DIR_TEMP, f"pexels_{video_id}.mp4")
            try:
                if not os.path.exists(destinazione):
                    print(f"[Media] Download clip stock '{q}'...")
                    dati = requests.get(link, timeout=60).content
                    if len(dati) < 50_000:
                        continue
                    with open(destinazione, "wb") as f:
                        f.write(dati)
                percorsi.append(destinazione)
                gia_scaricati.add(video_id)
            except Exception as e:
                print(f"[Warning Pexels] Download fallito: {e}")

    print(f"[Media] {len(percorsi)} clip stock pronte.")
    return percorsi


# ===========================================================================
# PUNTO DI INGRESSO
# ===========================================================================
def procura_materiale(prodotto, query_pexels="cute pet", animale="cane e gatto"):
    """Ritorna una lista di sorgenti [{tipo, path}] per il montaggio.

    tipo = 'video' | 'immagine'
    """
    os.makedirs(config.DIR_TEMP, exist_ok=True)
    sorgenti = [{"tipo": "immagine", "path": p}
                for p in scarica_immagini_prodotto(prodotto)]
    sorgenti += [{"tipo": "video", "path": p}
                 for p in scarica_clip_pexels(query_pexels, animale)]
    return sorgenti


if __name__ == "__main__":
    import sys
    from brain import carica_catalogo, animale_del_prodotto
    catalogo = carica_catalogo()
    prodotto = next((p for p in catalogo
                     if len(sys.argv) > 1 and p["handle"] == sys.argv[1]),
                    catalogo[0])
    for s in procura_materiale(prodotto, animale=animale_del_prodotto(prodotto)):
        print(f"  [{s['tipo']:9}] {s['path']}")
