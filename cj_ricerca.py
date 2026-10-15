"""Ricerca prodotti CJ per ZampaViva: prezzo, magazzino e spedizione verso l'Italia.

Legge le parole chiave da cj/richieste.txt (una per riga) oppure dalla variabile
RICERCHE (separate da ";"). Per ogni parola cerca su CJ i prodotti con
magazzino in Europa e, se non ce ne sono, quelli dalla Cina; per i primi
risultati calcola la spedizione verso l'Italia. Scrive cj/risultati.md e
cj/risultati.json. Serve il segreto CJ_API_KEY.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "https://developers.cjdropshipping.com/api2.0/v1"
PAESI_UE = ["DE", "FR", "ES", "IT", "PL", "CZ", "NL", "BE", "HU"]
PER_RICERCA = int(os.environ.get("PER_RICERCA", "3"))
# Commissione e cambio sono stime: servono solo per ordinare i risultati.
CAMBIO_USD_EUR = float(os.environ.get("CAMBIO_USD_EUR", "0.92"))

_ultima = 0.0


def _attendi():
    """CJ accetta una chiamata al secondo."""
    global _ultima
    pausa = 1.1 - (time.time() - _ultima)
    if pausa > 0:
        time.sleep(pausa)
    _ultima = time.time()


def chiama(metodo, percorso, token=None, **kw):
    _attendi()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["CJ-Access-Token"] = token
    r = requests.request(metodo, f"{BASE}/{percorso}", headers=headers, timeout=60, **kw)
    r.raise_for_status()
    dati = r.json()
    if not dati.get("result", dati.get("success")):
        raise RuntimeError(f"CJ {percorso}: {dati.get('code')} {dati.get('message')}")
    return dati.get("data")


def token(chiave):
    return chiama("POST", "authentication/getAccessToken", json={"apiKey": chiave})["accessToken"]


def cerca(tok, parola, paese=None):
    params = {"keyWord": parola, "page": 1, "size": 20}
    if paese:
        params["countryCode"] = paese
    dati = chiama("GET", "product/listV2", tok, params=params) or {}
    prodotti = []
    for blocco in dati.get("content") or []:
        prodotti.extend(blocco.get("productList") or [])
    return prodotti


def dettaglio(tok, pid):
    return chiama("GET", "product/query", tok, params={"pid": pid}) or {}


def spedizione(tok, vid, da):
    corpo = {"startCountryCode": da, "endCountryCode": "IT",
             "products": [{"vid": vid, "quantity": 1}]}
    try:
        opzioni = chiama("POST", "logistic/freightCalculate", tok, json=corpo) or []
    except Exception as e:  # noqa: BLE001 - un prodotto senza tariffa non ferma la ricerca
        return {"errore": str(e)[:200]}
    if not opzioni:
        return {"errore": "nessuna tariffa"}
    migliore = min(opzioni, key=lambda o: float(o.get("logisticPrice") or 1e9))
    return {"corriere": migliore.get("logisticName"),
            "prezzo_usd": float(migliore.get("logisticPrice") or 0),
            "giorni": migliore.get("logisticAging")}


def _numero(v):
    try:
        return float(str(v).split("--")[0].split("-")[0])
    except (TypeError, ValueError):
        return None


def analizza(tok, parola):
    trovati = []
    for paese in PAESI_UE:
        for p in cerca(tok, parola, paese):
            trovati.append((paese, p))
        if len(trovati) >= PER_RICERCA:
            break
    if not trovati:
        trovati = [("CN", p) for p in cerca(tok, parola)]
    righe = []
    visti = set()
    for paese, p in trovati:
        pid = p.get("id")
        if not pid or pid in visti:
            continue
        visti.add(pid)
        d = dettaglio(tok, pid)
        varianti = d.get("variants") or []
        v = varianti[0] if varianti else {}
        costo = _numero(v.get("variantSellPrice") or p.get("sellPrice") or p.get("nowPrice"))
        sped = spedizione(tok, v.get("vid"), paese) if v.get("vid") else {"errore": "nessuna variante"}
        righe.append({
            "ricerca": parola,
            "nome": p.get("nameEn"),
            "pid": pid,
            "sku": p.get("sku"),
            "magazzino": paese,
            "costo_usd": costo,
            "peso_g": v.get("variantWeight"),
            "varianti": len(varianti),
            "spedizione": sped,
            "immagine": p.get("bigImage"),
            "inventario": [{"paese": i.get("countryCode"), "pezzi": i.get("totalInventory")}
                           for i in (d.get("inventories") or [])],
        })
        if len(righe) >= PER_RICERCA:
            break
    return righe


def tabella(risultati):
    out = [f"# Ricerca CJ ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
           f"Costi e spedizioni in dollari, letti dall'API CJ. Euro = stima al cambio {CAMBIO_USD_EUR}.", "",
           "| Ricerca | Prodotto | Magazzino | Costo $ | Spedizione IT $ | Giorni | Totale € (stima) | SKU |",
           "|---|---|---|---|---|---|---|---|"]
    for r in risultati:
        s = r["spedizione"]
        sp = s.get("prezzo_usd")
        tot = round(((r["costo_usd"] or 0) + (sp or 0)) * CAMBIO_USD_EUR, 2) if sp is not None and r["costo_usd"] is not None else "n.d."
        nome = (r["nome"] or "").replace("|", "/")[:70]
        out.append(f"| {r['ricerca']} | {nome} | {r['magazzino']} | {r['costo_usd']} | "
                   f"{sp if sp is not None else s.get('errore', 'n.d.')} | {s.get('giorni', '')} | {tot} | {r['sku']} |")
    return "\n".join(out) + "\n"


def main():
    chiave = os.environ.get("CJ_API_KEY")
    if not chiave:
        sys.exit("Manca il segreto CJ_API_KEY")
    if os.environ.get("RICERCHE"):
        parole = [p.strip() for p in os.environ["RICERCHE"].split(";") if p.strip()]
    else:
        with open("cj/richieste.txt", encoding="utf-8") as f:
            parole = [r.strip() for r in f if r.strip() and not r.startswith("#")]
    tok = token(chiave)
    risultati = []
    for parola in parole:
        try:
            risultati.extend(analizza(tok, parola))
        except Exception as e:  # noqa: BLE001
            print(f"[cj] {parola}: {e}")
    with open("cj/risultati.json", "w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=1)
    with open("cj/risultati.md", "w", encoding="utf-8") as f:
        f.write(tabella(risultati))
    print(f"[cj] {len(risultati)} prodotti da {len(parole)} ricerche")


if __name__ == "__main__":
    main()
