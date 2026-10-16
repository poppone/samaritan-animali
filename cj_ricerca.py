"""Ricerca prodotti CJ per ZampaViva: prezzo, magazzino e spedizione verso l'Italia.

Legge le parole chiave da cj/richieste.txt (una per riga) oppure dalla variabile
RICERCHE (separate da ";"). Per ogni parola cerca su CJ i prodotti con
magazzino in Europa e, se non ce ne sono, quelli dalla Cina; scarta i
risultati che non c'entrano con la ricerca, legge le scorte per magazzino e
calcola la spedizione verso l'Italia (prima da un magazzino UE, poi dalla Cina). Scrive cj/risultati.md e
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
MIN_PERTINENZA = float(os.environ.get("MIN_PERTINENZA", "0.6"))
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


def scorte(tok, vid):
    """Pezzi disponibili per paese del magazzino (vuoto se CJ non risponde)."""
    try:
        dati = chiama("GET", "product/stock/queryByVid", tok, params={"vid": vid}) or []
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for i in dati if isinstance(dati, list) else []:
        paese = i.get("countryCode") or i.get("areaEn")
        pezzi = i.get("totalInventoryNum", i.get("storageNum", i.get("totalInventory")))
        if paese:
            out[paese] = pezzi
    return out


def spedizione(tok, vid, partenze):
    """Tariffa più economica verso l'Italia, provando le partenze in ordine."""
    errori = []
    for da in partenze:
        corpo = {"startCountryCode": da, "endCountryCode": "IT",
                 "products": [{"vid": vid, "quantity": 1}]}
        try:
            opzioni = chiama("POST", "logistic/freightCalculate", tok, json=corpo) or []
        except Exception as e:  # noqa: BLE001 - un prodotto senza tariffa non ferma la ricerca
            errori.append(f"{da}: {str(e)[:120]}")
            continue
        if opzioni:
            migliore = min(opzioni, key=lambda o: float(o.get("logisticPrice") or 1e9))
            return {"da": da, "corriere": migliore.get("logisticName"),
                    "prezzo_usd": float(migliore.get("logisticPrice") or 0),
                    "giorni": migliore.get("logisticAging")}
        errori.append(f"{da}: nessuna tariffa")
    return {"errore": "; ".join(errori) or "nessuna tariffa"}


def _numero(v):
    try:
        return float(str(v).split("--")[0].split("-")[0])
    except (TypeError, ValueError):
        return None


def _pertinenza(parola, nome):
    """Quota delle parole della ricerca presenti nel nome del prodotto."""
    chiavi = [w for w in parola.lower().split() if len(w) > 2]
    nome = (nome or "").lower()
    return sum(1 for w in chiavi if w in nome) / max(len(chiavi), 1)


def analizza(tok, parola):
    trovati = {}
    for paese in PAESI_UE + [None]:
        for p in cerca(tok, parola, paese):
            pid = p.get("id")
            if pid and pid not in trovati and _pertinenza(parola, p.get("nameEn")) >= MIN_PERTINENZA:
                trovati[pid] = p
        if len(trovati) >= PER_RICERCA * 3:
            break
    candidati = sorted(trovati.values(), key=lambda p: -_pertinenza(parola, p.get("nameEn")))
    righe = []
    for p in candidati[:PER_RICERCA * 2]:
        d = dettaglio(tok, p["id"])
        varianti = d.get("variants") or []
        v = varianti[0] if varianti else {}
        if not v.get("vid"):
            continue
        stock = scorte(tok, v["vid"])
        ue = [c for c in PAESI_UE if (stock.get(c) or 0) > 0]
        sped = spedizione(tok, v["vid"], ue + ["CN"])
        costo = _numero(v.get("variantSellPrice") or p.get("sellPrice") or p.get("nowPrice"))
        righe.append({
            "ricerca": parola,
            "nome": p.get("nameEn"),
            "pid": p["id"],
            "sku": p.get("sku"),
            "magazzino": sped.get("da") or (ue[0] if ue else "CN"),
            "costo_usd": costo,
            "peso_g": v.get("variantWeight"),
            "varianti": len(varianti),
            "spedizione": sped,
            "immagine": p.get("bigImage"),
            "scorte": stock,
        })
    # Prima chi spedisce da un magazzino europeo, poi i più economici.
    righe.sort(key=lambda r: (r["magazzino"] not in PAESI_UE, "prezzo_usd" not in r["spedizione"],
                              (r["costo_usd"] or 0) + (r["spedizione"].get("prezzo_usd") or 0)))
    return righe[:PER_RICERCA]


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


def varianti(tok, pids):
    """Tutte le varianti dei prodotti indicati, con prezzo, scorte e spedizione dalla Cina."""
    out = [f"# Varianti CJ ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
           "Costi e spedizioni in dollari, letti dall'API CJ.", ""]
    for pid in pids:
        try:
            d = dettaglio(tok, pid)
        except Exception as e:  # noqa: BLE001
            out += [f"## {pid}", "", f"Errore: {e}", ""]
            continue
        out += [f"## {d.get('productNameEn', '')} ({d.get('productSku', '')})", "",
                "| Variante | Chiave | Costo $ | Peso g | Scorte | Spedizione IT $ | Giorni | SKU variante |",
                "|---|---|---|---|---|---|---|---|"]
        for v in d.get("variants") or []:
            vid = v.get("vid")
            stock = scorte(tok, vid) if vid else {}
            ue = [c for c in PAESI_UE if (stock.get(c) or 0) > 0]
            sped = spedizione(tok, vid, ue + ["CN"]) if vid else {}
            nome = (v.get("variantNameEn") or "").replace("|", "/")
            out.append(f"| {nome} | {v.get('variantKey', '')} | {v.get('variantSellPrice', '')} | "
                       f"{v.get('variantWeight', '')} | {stock or 'n.d.'} | "
                       f"{sped.get('prezzo_usd', sped.get('errore', 'n.d.'))} | {sped.get('giorni', '')} | "
                       f"{v.get('variantSku', '')} |")
        testo = " ".join(str(d.get(k) or "") for k in ("description", "productProEn", "materialNameEn"))
        spine = [w for w in ("EU plug", "EU Plug", "US plug", "UK plug", "USB", "CE") if w in testo]
        out += ["", f"Nella scheda CJ compaiono: {', '.join(spine) or 'nessuna indicazione su spina o CE'}.", ""]
        foto = d.get("productImageSet") or []
        if isinstance(foto, str):
            foto = [u for u in foto.strip("[]").replace('"', "").split(",") if u.strip()]
        foto += [v.get("variantImage") for v in d.get("variants") or [] if v.get("variantImage")]
        foto = list(dict.fromkeys(u.strip() for u in foto if u))
        out += [f"Foto ({len(foto)}):", ""] + [f"- {u}" for u in foto] + [""]
    with open("cj/varianti.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"[cj] varianti di {len(pids)} prodotti in cj/varianti.md")


def main():
    chiave = os.environ.get("CJ_API_KEY")
    if not chiave:
        sys.exit("Manca il segreto CJ_API_KEY")
    if os.environ.get("VARIANTI"):
        varianti(token(chiave), [p.strip() for p in os.environ["VARIANTI"].split(";") if p.strip()])
        return
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
