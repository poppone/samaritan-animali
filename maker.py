"""
Montaggio video di ZampaViva TikTok.

  1. Foto ufficiali del prodotto + clip stock di cani e gatti (media.py)
  2. Stacco ogni 2-3 secondi, alternando clip in movimento e foto prodotto
  3. Zoom lento (Ken Burns) su ogni stacco: movimento costante
  4. Foto quadrate inserite nel 9:16 con sfondo sfocato
  5. Progress bar, banner del titolo, sottotitoli parola-per-parola
"""
import os
import re
import time
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

import config
from voice import genera_voce_samaritan, pulisci_testo

GIALLO = "#FFE600"
EVIDENZIA = "#FF9F1C"        # arancio caldo per nome prodotto e numeri

# Layout verticale pensato per TikTok: in alto c'e' la barra "Seguiti/Per te",
# in basso a destra le icone e in basso la caption. Il contenuto sta nel mezzo.
Y_MEDIA = 0.16
Y_SOTTOTITOLI = 0.69
Y_BANNER = 0.10

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "arialbd.ttf",
    "arial.ttf",
]

_CACHE_VIDEO = {}


def _carica_font(dimensione):
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, dimensione)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# ===========================================================================
# ADATTAMENTO AL FORMATO VERTICALE
# ===========================================================================
def _sfondo_sfocato(frame, durata):
    """Sfondo 9:16 ricavato dal frame stesso: sfocato e scurito.
    Sfocato in miniatura e poi ingrandito: molto piu' veloce, stesso risultato."""
    W, H = config.VIDEO_W, config.VIDEO_H
    piccolo_w, piccolo_h = 108, 192

    img = Image.fromarray(frame)
    fattore = max(piccolo_w / img.width, piccolo_h / img.height)
    img = img.resize((max(int(img.width * fattore), piccolo_w),
                      max(int(img.height * fattore), piccolo_h)), Image.BILINEAR)
    sinistra = (img.width - piccolo_w) // 2
    alto = (img.height - piccolo_h) // 2
    img = img.crop((sinistra, alto, sinistra + piccolo_w, alto + piccolo_h))
    img = img.filter(ImageFilter.GaussianBlur(4))
    img = ImageEnhance.Brightness(img).enhance(0.55)
    img = img.resize((W, H), Image.BILINEAR)
    return ImageClip(np.array(img)).with_duration(durata)


def _adatta_a_verticale(clip, durata):
    """Porta qualunque sorgente a 1080x1920.

    - Sorgenti gia' verticali  -> scale-to-cover + crop centrale
    - Foto quadrate/orizzontali -> riquadro su sfondo sfocato
    """
    W, H = config.VIDEO_W, config.VIDEO_H

    if clip.h / max(clip.w, 1) >= 1.4:
        fattore = max(W / clip.w, H / clip.h)
        scalato = clip.resized((round(clip.w * fattore), round(clip.h * fattore)))
        return scalato.cropped(width=W, height=H,
                               x_center=scalato.w / 2, y_center=scalato.h / 2)

    larghezza_fg = int(W * config.ZOOM_PRODOTTO)
    altezza_fg = round(larghezza_fg * clip.h / clip.w)
    altezza_max = int(H * (Y_SOTTOTITOLI - Y_MEDIA))
    if altezza_fg > altezza_max:
        altezza_fg = altezza_max
        larghezza_fg = round(altezza_fg * clip.w / clip.h)

    primo_piano = clip.resized((larghezza_fg, altezza_fg))
    try:
        istante = min(clip.duration / 2, max(clip.duration - 0.05, 0))
        sfondo = _sfondo_sfocato(clip.get_frame(istante), durata)
    except Exception as e:
        print(f"[Warning Maker] Sfondo sfocato non generato ({e}), uso il nero.")
        sfondo = ColorClip(size=(W, H), color=(0, 0, 0)).with_duration(durata)

    return CompositeVideoClip(
        [sfondo, primo_piano.with_position(("center", int(H * Y_MEDIA)))],
        size=(W, H),
    ).with_duration(durata)


def _applica_zoom(clip, durata, intensita=0.08):
    try:
        zoomata = clip.resized(lambda t: 1 + intensita * (t / max(durata, 0.01)))
        return CompositeVideoClip(
            [zoomata.with_position("center")],
            size=(config.VIDEO_W, config.VIDEO_H),
        ).with_duration(durata)
    except Exception as e:
        print(f"[Warning Maker] Zoom non applicato ({e}).")
        return clip


# ===========================================================================
# MONTAGGIO
# ===========================================================================
def _apri_video(percorso):
    if percorso not in _CACHE_VIDEO:
        _CACHE_VIDEO[percorso] = VideoFileClip(percorso).without_audio()
    return _CACHE_VIDEO[percorso]


def _prepara_segmento(sorgente, durata):
    if sorgente["tipo"] == "immagine":
        base = ImageClip(sorgente["path"]).with_duration(durata)
        return _applica_zoom(_adatta_a_verticale(base, durata), durata, intensita=0.10)

    video = _apri_video(sorgente["path"])
    if video.duration <= durata:
        pezzo = video.subclipped(0, video.duration)
        durata = video.duration
    else:
        inizio = random.uniform(0, video.duration - durata)
        pezzo = video.subclipped(inizio, inizio + durata)
    return _applica_zoom(_adatta_a_verticale(pezzo, durata), durata)


def ordina_sorgenti(sorgenti):
    """Alterna clip e foto, aprendo con una clip: il video deve partire in
    movimento, e il prodotto deve tornare in scena ogni pochi secondi."""
    video = [s for s in sorgenti if s["tipo"] == "video"]
    immagini = [s for s in sorgenti if s["tipo"] != "video"]
    random.shuffle(video)
    # la prima foto del catalogo e' quasi sempre la piu' rappresentativa
    immagini = immagini[:1] + random.sample(immagini[1:], len(immagini[1:]))

    ordinate = []
    for i in range(max(len(video), len(immagini))):
        if i < len(video):
            ordinate.append(video[i])
        if i < len(immagini):
            ordinate.append(immagini[i])
    return ordinate


def costruisci_sfondo_montato(sorgenti, durata_totale):
    utilizzabili = ordina_sorgenti([s for s in sorgenti if os.path.exists(s["path"])])
    if not utilizzabili:
        return None

    segmenti, coperto, indice = [], 0.0, 0
    while coperto < durata_totale and utilizzabili:
        sorgente = utilizzabili[indice % len(utilizzabili)]
        indice += 1

        durata = random.uniform(config.STACCO_MIN, config.STACCO_MAX)
        durata = min(durata, durata_totale - coperto)
        if durata < 0.4:
            break

        try:
            segmento = _prepara_segmento(sorgente, durata)
        except Exception as e:
            print(f"[Warning Maker] Sorgente scartata ({sorgente['path']}): {e}")
            utilizzabili = [s for s in utilizzabili if s is not sorgente]
            continue

        segmenti.append(segmento)
        coperto += segmento.duration

    if not segmenti:
        return None

    print(f"[ZampaViva Maker] {len(segmenti)} stacchi in {coperto:.1f}s "
          f"da {len(utilizzabili)} sorgenti")
    return concatenate_videoclips(segmenti, method="compose")


# ===========================================================================
# GRAFICA
# ===========================================================================
def crea_immagine_parola(testo, font_size=110, colore=GIALLO):
    font = _carica_font(font_size)
    misura = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = misura.textbbox((0, 0), testo, font=font)
    testo_w, testo_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    bordo, pad_x, pad_y = 9, 44, 28
    img = Image.new(
        "RGBA",
        (testo_w + bordo * 2 + pad_x * 2, testo_h + bordo * 2 + pad_y * 2),
        (0, 0, 0, 0),
    )
    ImageDraw.Draw(img).text(
        (pad_x + bordo - bbox[0], pad_y + bordo - bbox[1]),
        testo, font=font, fill=colore, stroke_width=bordo, stroke_fill="black",
    )
    return np.array(img)


def crea_banner_titolo(testo, larghezza_max, font_size=62):
    font = _carica_font(font_size)
    misura = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    righe, riga = [], ""
    for parola in testo.split():
        tentativo = f"{riga} {parola}".strip()
        if misura.textlength(tentativo, font=font) <= larghezza_max - 80:
            riga = tentativo
        else:
            if riga:
                righe.append(riga)
            riga = parola
    if riga:
        righe.append(riga)
    righe = righe[:3]

    altezza_riga = font_size + 18
    img = Image.new("RGBA",
                    (larghezza_max, altezza_riga * len(righe) + 40),
                    (0, 0, 0, 165))
    draw = ImageDraw.Draw(img)
    for i, riga in enumerate(righe):
        w = draw.textlength(riga, font=font)
        draw.text(((larghezza_max - w) / 2, 20 + i * altezza_riga),
                  riga, font=font, fill="white", stroke_width=3, stroke_fill="black")
    return np.array(img)


def crea_progress_bar(durata, passi=60):
    clips, altezza = [], 12
    clips.append(
        ColorClip(size=(config.VIDEO_W, altezza), color=(20, 20, 20))
        .with_duration(durata).with_position((0, 0)).with_opacity(0.55)
    )
    passo = durata / passi
    for i in range(1, passi + 1):
        clips.append(
            ColorClip(size=(max(int(config.VIDEO_W * i / passi), 1), altezza),
                      color=(255, 159, 28))
            .with_start(passo * (i - 1)).with_duration(passo).with_position((0, 0))
        )
    return clips


# ===========================================================================
# SOTTOTITOLI
# ===========================================================================
def genera_sottotitoli_clips(audio_path, parole_evidenziate=""):
    import whisper

    print(f"[ZampaViva Subtitles] Trascrizione con modello '{config.WHISPER_MODEL}'...")
    modello = whisper.load_model(config.WHISPER_MODEL)
    risultato = modello.transcribe(audio_path, language=config.LINGUA,
                                   word_timestamps=True)

    parole_chiave = {w.upper() for w in re.findall(r"\b\w{4,}\b", parole_evidenziate)}
    clips = []
    y = int(config.VIDEO_H * Y_SOTTOTITOLI)

    for segmento in risultato.get("segments", []):
        for info in segmento.get("words", []):
            parola = info["word"].strip().upper()
            if not parola:
                continue
            inizio = info["start"]
            durata = max(info["end"] - inizio, 0.25)
            nudo = parola.strip(".,!?;:")
            evidenzia = nudo.isdigit() or nudo in parole_chiave

            clip = (
                ImageClip(crea_immagine_parola(parola,
                                               colore=EVIDENZIA if evidenzia else GIALLO))
                .with_start(inizio).with_duration(durata)
                .with_position(("center", y))
            )
            try:
                clip = clip.resized(lambda t: min(1.0, 0.80 + 2.2 * t))
            except Exception:
                pass
            clips.append(clip)

    print(f"[ZampaViva Subtitles] {len(clips)} parole sincronizzate.")
    return clips


# ===========================================================================
# PIPELINE
# ===========================================================================
def assembla_video_finale(dati):
    """Produce il video a partire dal pacchetto di brain.py. Ritorna il path."""
    from media import procura_materiale

    os.makedirs(config.DIR_OUTPUT, exist_ok=True)
    print("\n--- ZAMPAVIVA MAKER: PRODUZIONE VIDEO ---")
    prodotto = dati["prodotto"]

    audio_path = genera_voce_samaritan(dati["script"])
    if not audio_path:
        print("[Errore Maker] Audio non generato: interrompo.")
        return None

    sorgenti = procura_materiale(prodotto, dati["query_video"], dati["animale"])
    if not sorgenti:
        print("[Errore Maker] Nessun materiale visivo disponibile: interrompo.")
        return None

    audio_clip = AudioFileClip(audio_path)
    durata = audio_clip.duration + 0.4

    sfondo = costruisci_sfondo_montato(sorgenti, durata)
    if sfondo is None:
        print("[Errore Maker] Montaggio fallito: interrompo.")
        audio_clip.close()
        return None

    sfondo = sfondo.with_duration(durata).with_audio(audio_clip)
    livelli = [sfondo]

    try:
        banner = (
            ImageClip(crea_banner_titolo(pulisci_testo(dati["titolo"]).upper(),
                                         int(config.VIDEO_W * 0.92)))
            .with_start(0).with_duration(min(2.5, durata))
            .with_position(("center", int(config.VIDEO_H * Y_BANNER)))
        )
        livelli.append(banner)
    except Exception as e:
        print(f"[Warning Maker] Banner titolo saltato: {e}")

    try:
        livelli.extend(crea_progress_bar(durata))
    except Exception as e:
        print(f"[Warning Maker] Progress bar saltata: {e}")

    try:
        livelli.extend(genera_sottotitoli_clips(audio_path, prodotto["titolo"]))
    except Exception as e:
        print(f"[Warning Maker] Sottotitoli saltati: {e}")

    finale = CompositeVideoClip(livelli,
                                size=(config.VIDEO_W, config.VIDEO_H)
                                ).with_duration(durata)

    nome = f"zampaviva_{prodotto['handle'][:40]}_{time.strftime('%Y%m%d_%H%M')}.mp4"
    output_file = os.path.join(config.DIR_OUTPUT, nome)
    print(f"[ZampaViva Maker] Rendering {config.VIDEO_W}x{config.VIDEO_H} "
          f"@{config.FPS}fps ({durata:.1f}s)...")
    finale.write_videofile(output_file, fps=config.FPS, codec="libx264",
                           audio_codec="aac", preset="medium", threads=4)

    for c in [audio_clip, sfondo, finale] + list(_CACHE_VIDEO.values()):
        try:
            c.close()
        except Exception:
            pass
    _CACHE_VIDEO.clear()

    print("\nVIDEO GENERATO CON SUCCESSO!")
    return output_file


if __name__ == "__main__":
    from brain import genera_script_zampaviva
    print(assembla_video_finale(genera_script_zampaviva()))
