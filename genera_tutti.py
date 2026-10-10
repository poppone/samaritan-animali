"""
Genera un video per ogni prodotto del catalogo, uno dopo l'altro, e li
manda tutti su Telegram.

Uso:
    python genera_tutti.py                       # tutti i prodotti
    python genera_tutti.py handle-da-saltare ... # salta alcuni handle

Ogni video richiede ~10-12 minuti su un PC normale: con 16 prodotti conta
circa 3 ore. Se un prodotto fallisce si passa al successivo.
"""
import sys
import traceback

import notifier
from brain import carica_catalogo
from main import esegui_pipeline


def main(da_saltare=()):
    catalogo = [p for p in carica_catalogo() if p["handle"] not in da_saltare]
    totale = len(catalogo)
    notifier.invia_messaggio(
        f"<b>ZampaViva</b>: preparo {totale} video, uno per prodotto. "
        "Ti arrivano qui man mano (circa uno ogni 10-12 minuti).")

    riusciti, falliti = [], []
    for i, prodotto in enumerate(catalogo, 1):
        print(f"\n######## {i}/{totale}: {prodotto['titolo']} ########")
        try:
            if esegui_pipeline(prodotto["handle"]):
                riusciti.append(prodotto["titolo"])
            else:
                falliti.append(prodotto["titolo"])
        except Exception:
            print(traceback.format_exc())
            falliti.append(prodotto["titolo"])

    riepilogo = f"<b>ZampaViva</b>: finito. {len(riusciti)}/{totale} video pronti."
    if falliti:
        riepilogo += "\nNon riusciti: " + ", ".join(falliti)
    notifier.invia_messaggio(riepilogo)
    print(riepilogo)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
