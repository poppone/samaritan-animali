"""
Orchestratore della pipeline ZampaViva TikTok.

  FASE 1  Scrittura -> prodotto in rotazione dal catalogo + script
  FASE 2  Montaggio -> foto prodotto, clip di cani e gatti, voce, sottotitoli
  FASE 3  Consegna  -> video + didascalia pronta su Telegram

La pubblicazione su TikTok resta manuale.

Uso:
    python main.py                                   # prodotto in rotazione
    python main.py pettorina-anti-tiro-riflettente   # prodotto specifico (handle)
"""
import sys
import os
import traceback

import config
from brain import genera_script_zampaviva, componi_didascalia
from maker import assembla_video_finale
import notifier


def esegui_pipeline(richiesto=None):
    print("=" * 62)
    print(f"ZAMPAVIVA TIKTOK | {config.NOME_NEGOZIO} | "
          f"telegram={'si' if config.TELEGRAM_ATTIVO else 'no'}")
    print("=" * 62)

    # -------------------------------------------------- FASE 1: Scrittura
    print("\n[FASE 1/3] Generazione contenuto...")
    dati = genera_script_zampaviva(richiesto)
    didascalia = componi_didascalia(dati)

    print("-" * 62)
    print(f"TITOLO   : {dati['titolo']}")
    print(f"FORMATO  : {dati['stile']}")
    print(f"PRODOTTO : {dati['prodotto']['titolo']} ({dati['animale']})")
    print(f"QUERY    : {dati['query_video']}")
    print("-" * 62)
    print(dati["script"])
    print("-" * 62)
    print(didascalia)
    print("-" * 62)

    # -------------------------------------------------- FASE 2: Montaggio
    print("\n[FASE 2/3] Foto, clip, voce, montaggio e sottotitoli...")
    video_path = assembla_video_finale(dati)

    if not video_path or not os.path.exists(video_path):
        print("\n[Errore Pipeline] Rendering non completato.")
        notifier.notifica_errore("Rendering del video fallito.")
        return None

    # salvo la didascalia accanto al video, utile anche senza Telegram
    with open(os.path.splitext(video_path)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write(didascalia + "\n")

    # --------------------------------------------------- FASE 3: Consegna
    print("\n[FASE 3/3] Invio su Telegram...")
    consegnato = notifier.notifica_video(dati, video_path, didascalia)

    print("=" * 62)
    print(f"VIDEO PRONTO -> {video_path}")
    print(f"TELEGRAM     -> {'inviato' if consegnato else 'NON inviato'}")
    print("=" * 62)
    return video_path


if __name__ == "__main__":
    richiesto = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        esegui_pipeline(richiesto)
    except Exception:
        traccia = traceback.format_exc()
        print(traccia)
        notifier.notifica_errore(traccia)
        sys.exit(1)
