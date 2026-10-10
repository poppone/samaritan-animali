"""
Cervello di ZampaViva TikTok: sceglie prodotto e formato, scrive titolo,
script e didascalia, e valida il risultato.

  - Fonte delle idee: il catalogo PUBBLICO del negozio (products.json).
  - I prodotti ruotano: viene scelto quello mostrato meno di recente.
  - Lo script usa SOLO le informazioni del catalogo, niente promesse inventate.
  - Se il modello apre con un saluto lo script viene rifiutato e rigenerato.
"""
import os
import json
import random
import time
import re
import html

import requests
from groq import Groq

import config

client = Groq(api_key=config.GROQ_API_KEY)

FORMATI_VIDEO = {
    "PROBLEMA_SOLUZIONE": "Un fastidio quotidiano reale con il cane o il gatto, "
                          "poi il prodotto che lo risolve",
    "LO_FA_ANCHE_IL_TUO": "'Il tuo gatto lo fa?' / 'Il tuo cane lo fa?': un "
                          "comportamento tipico in cui ogni padrone si "
                          "riconosce, collegato al prodotto",
    "TRE_MOTIVI": "3 motivi veloci per cui il tuo animale amera' questo "
                  "prodotto, presi dalla descrizione",
    "PRIMA_DOPO": "Com'era la situazione prima e come cambia dopo, senza "
                  "esagerare i risultati",
    "DOMANDA_AL_PUBBLICO": "Un dilemma simpatico da padroni di animali che "
                           "spinge a commentare, con il prodotto protagonista",
}

APERTURE_VIETATE = (
    "ciao", "salve", "benvenut", "buongiorno", "buonasera", "ehi ragazzi",
    "oggi vi parlo", "oggi parliamo", "in questo video", "oggi vi mostro",
    "come state", "raga,", "ragazzi,",
)

MIN_PAROLE_SCRIPT = 45
MAX_PAROLE_SCRIPT = 95
MIN_HASHTAG, MAX_HASHTAG = 3, 5

# Chiusura fissa di ogni video
FRASE_FINALE = "Trovi il negozio nel profilo!"


# ============================================================== CATALOGO
def _testo_da_html(contenuto):
    t = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", contenuto or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


def normalizza_prodotto(p):
    varianti = p.get("variants") or []
    prezzi = [float(v["price"]) for v in varianti if v.get("price")]
    handle = p.get("handle", "")
    return {
        "handle": handle,
        "titolo": (p.get("title") or "").strip(),
        "descrizione": _testo_da_html(p.get("body_html"))[:900],
        "prezzo": f"{min(prezzi):.2f}" if prezzi else "",
        "immagini": [i["src"] for i in p.get("images", []) if i.get("src")],
        "tags": [t.lower() for t in (p.get("tags") or [])],
        "tipo": p.get("product_type") or "",
        "url": f"{config.URL_NEGOZIO}/products/{handle}",
    }


def carica_catalogo():
    url = f"{config.URL_NEGOZIO}/products.json"
    print(f"[ZampaViva Brain] Lettura catalogo da {url}...")
    r = requests.get(url, params={"limit": 250}, timeout=15)
    r.raise_for_status()
    prodotti = [normalizza_prodotto(p) for p in r.json().get("products", [])]
    prodotti = [p for p in prodotti if p["handle"] and p["titolo"]]
    print(f"[ZampaViva Brain] {len(prodotti)} prodotti nel catalogo.")
    return prodotti


def animale_del_prodotto(prodotto):
    testo = " ".join(prodotto["tags"] + [prodotto["tipo"], prodotto["titolo"]]).lower()
    cane = "cane" in testo or "cani" in testo
    gatto = "gatto" in testo or "gatti" in testo
    if gatto and not cane:
        return "gatto"
    if cane and not gatto:
        return "cane"
    return "cane e gatto"


# ================================================================ MEMORIA
def carica_cronologia():
    if not os.path.exists(config.FILE_CRONOLOGIA):
        return []
    try:
        with open(config.FILE_CRONOLOGIA, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def salva_in_cronologia(dati):
    cronologia = carica_cronologia()
    cronologia.append({
        "timestamp": int(time.time()),
        "data": time.strftime("%Y-%m-%d"),
        "handle": dati["prodotto"]["handle"],
        "titolo": dati["titolo"],
        "estratto_script": dati["script"][:90],
        "stile": dati["stile"],
    })
    with open(config.FILE_CRONOLOGIA, "w", encoding="utf-8") as f:
        json.dump(cronologia[-300:], f, ensure_ascii=False, indent=2)


# ================================================================= SCELTE
def scegli_prodotto(catalogo, cronologia, richiesto=None):
    """Il prodotto mostrato meno di recente (i mai usati per primi).
    `richiesto` puo' essere un handle o una parola del titolo."""
    if not catalogo:
        raise ValueError("catalogo vuoto")
    if richiesto:
        r = richiesto.lower().strip()
        for p in catalogo:
            if p["handle"] == r or r in p["titolo"].lower():
                return p

    ultimo_uso = {}
    for i, voce in enumerate(cronologia):
        if isinstance(voce, dict) and voce.get("handle"):
            ultimo_uso[voce["handle"]] = i
    minimo = min(ultimo_uso.get(p["handle"], -1) for p in catalogo)
    return random.choice(
        [p for p in catalogo if ultimo_uso.get(p["handle"], -1) == minimo])


def scegli_formato(cronologia, prodotto=None):
    """Evita gli ultimi 2 formati e quelli gia' usati per lo stesso prodotto."""
    voci = [v for v in cronologia if isinstance(v, dict)]
    recenti = {v.get("stile") for v in voci[-2:]}
    gia_usati = {v.get("stile") for v in voci
                 if prodotto and v.get("handle") == prodotto["handle"]}
    candidati = [f for f in FORMATI_VIDEO if f not in recenti | gia_usati]
    if not candidati:
        candidati = [f for f in FORMATI_VIDEO if f not in recenti] or list(FORMATI_VIDEO)
    return random.choice(candidati)


# ===================================================== VALIDAZIONE E TESTI
def _pulisci_titolo(titolo):
    t = titolo.strip().strip('"').strip("'")
    t = re.sub(r"#\w+", "", t).strip()
    return re.sub(r"\s+", " ", t)[:100]


def pulisci_hashtag(grezzi, animale="cane e gatto"):
    """3-5 hashtag minuscoli, senza duplicati, con sempre quelli di base."""
    if isinstance(grezzi, str):
        grezzi = re.split(r"[\s,]+", grezzi)
    base = [h for h, a in (("#cane", "cane"), ("#gatto", "gatto")) if a in animale]
    base.append("#animalidomestici")

    altri = []
    for h in grezzi or []:
        h = "#" + re.sub(r"[^\w]", "", str(h).lower())
        if len(h) > 2 and h not in base and h not in altri:
            altri.append(h)

    finali = base + altri[:MAX_HASHTAG - len(base)]
    for extra in ("#zampaviva", "#petlover"):
        if len(finali) < MIN_HASHTAG and extra not in finali:
            finali.append(extra)
    return finali


def valida_script(titolo, script):
    if not titolo or not script:
        return False, "titolo o script vuoti"
    inizio = script.lower().lstrip(" \"'-–—")
    for vietata in APERTURE_VIETATE:
        if inizio.startswith(vietata):
            return False, f"apertura debole vietata: '{vietata}'"
    n_parole = len(script.split())
    if n_parole < MIN_PAROLE_SCRIPT:
        return False, f"script troppo corto ({n_parole} parole)"
    if n_parole > MAX_PAROLE_SCRIPT:
        return False, f"script troppo lungo ({n_parole} parole)"
    return True, ""


def aggiungi_frase_finale(script):
    """Chiude sempre con la stessa frase: il negozio e' nel profilo.

    La aggiunge il codice e non il modello, cosi' e' identica in ogni video.
    Se il modello ha comunque scritto un suo invito ('link in bio',
    'nel profilo'), quella frase viene tolta per non ripeterla.
    """
    frasi = re.split(r"(?<=[.!?])\s+", script.strip())
    frasi = [f for f in frasi
             if not re.search(r"link in bio|nel (mio |nostro )?profilo", f, re.I)]
    return " ".join(frasi + [FRASE_FINALE])


def componi_didascalia(dati):
    """Didascalia TikTok pronta da copiare: testo + hashtag + link prodotto."""
    return (f"{dati['didascalia'].strip()}\n\n"
            f"{' '.join(dati['hashtag'])}\n\n"
            f"{dati['prodotto']['url']}")


# ============================================================= GENERAZIONE
def _costruisci_system_prompt(formato, prodotto, animale, ultimi_titoli):
    scheda = (
        f"  Nome: {prodotto['titolo']}\n"
        f"  Categoria: {prodotto['tipo'] or 'n/d'}\n"
        f"  Per: {animale}\n"
        f"  Prezzo: {prodotto['prezzo']} EUR\n"
        f"  Descrizione ufficiale:\n{prodotto['descrizione']}\n"
    )
    return (
        f"Sei il social media manager di '{config.NOME_NEGOZIO}', negozio online "
        "italiano di accessori per cani e gatti. Scrivi in italiano lo script di un "
        "video TikTok ad ALTISSIMA RETENTION (20-30 secondi, quindi 55-85 parole). "
        "Tono caldo, simpatico e affettuoso, da amante degli animali a amante degli "
        "animali: mai da televendita.\n\n"
        f"FORMATO RICHIESTO: {formato} - {FORMATI_VIDEO[formato]}\n\n"
        f"PRODOTTO DA PRESENTARE:\n{scheda}\n"
        "VINCOLO DI VERIDICITA' ASSOLUTO: usa SOLO le caratteristiche scritte nella "
        "descrizione ufficiale. NON inventare benefici per la salute, promesse "
        "veterinarie, sconti, offerte a tempo, recensioni, numeri di clienti o di "
        "vendite. Se non sei certo di un dettaglio, NON inserirlo.\n\n"
        "REGOLE TASSATIVE:\n"
        "1. PRIMA FRASE = HOOK che blocca lo scroll in 3 secondi. VIETATO iniziare "
        "con saluti ('Ciao', 'Raga', 'Benvenuti', 'Oggi vi parlo'). Inizia con una "
        "domanda diretta o una scena in cui il padrone si riconosce (es: 'Il tuo "
        "gatto ti sveglia alle 5?').\n"
        "2. CHIUSURA: l'ultima frase richiama in modo naturale la domanda iniziale.\n"
        "3. RITMO: frasi corte, una informazione per frase, niente subordinate.\n"
        "4. NIENTE INVITO FINALE: non scrivere 'link in bio', 'nel profilo' o "
        f"simili. La frase '{FRASE_FINALE}' viene aggiunta automaticamente "
        "dopo il tuo testo.\n"
        "5. TITOLO: testo a schermo, massimo 60 caratteri, UNA emoji, niente hashtag.\n"
        "6. QUERY VIDEO: in INGLESE, 2-4 parole, per clip stock di animali coerenti "
        "(es: 'cat playing ball', 'dog walking leash').\n"
        "7. DIDASCALIA: caption TikTok di 1-2 righe brevi + UNA domanda che spinga "
        "a commentare. Niente hashtag e niente link.\n"
        "8. HASHTAG: lista di 3-5 hashtag italiani pertinenti "
        "(es: #cane #gatto #animalidomestici #gattiditiktok).\n"
        "9. NON riusare questi titoli:\n"
        f"   {json.dumps(ultimi_titoli, ensure_ascii=False)}\n\n"
        "Rispondi ESCLUSIVAMENTE con un JSON valido con le chiavi: "
        "'titolo', 'script', 'query_video', 'didascalia', 'hashtag'."
    )


def _fallback(prodotto, animale, formato):
    chi = {"gatto": "il tuo gatto", "cane": "il tuo cane"}.get(
        animale, "il tuo amico a quattro zampe")
    nome = prodotto["titolo"]
    return {
        "titolo": f"{nome} 🐾",
        "script": (
            f"Lo sai cosa renderebbe felice {chi} oggi? "
            f"Si chiama {nome}, e l'abbiamo scelto pensando proprio a lui. "
            "E' fatto per la vita di tutti i giorni. "
            "Semplice da usare, bello da vedere. "
            f"Lo trovi su {config.NOME_NEGOZIO}, scelto con amore per lui. "
            f"E adesso dimmi: lo sai cosa renderebbe felice {chi}?"
        ),
        "query_video": {"gatto": "cute cat playing", "cane": "happy dog playing"}
                       .get(animale, "cute cat dog"),
        "didascalia": f"{nome}: lo vorresti per {chi}? Dimmelo nei commenti!",
        "hashtag": [],
        "stile": formato,
    }


def genera_script_zampaviva(richiesto=None):
    """Ritorna un dict: titolo, script, query_video, didascalia, hashtag,
    stile, prodotto, animale."""
    catalogo = carica_catalogo()
    cronologia = carica_cronologia()
    prodotto = scegli_prodotto(catalogo, cronologia, richiesto)
    animale = animale_del_prodotto(prodotto)
    formato = scegli_formato(cronologia, prodotto)
    print(f"[ZampaViva Brain] {prodotto['titolo']} ({animale}) - {formato}")

    ultimi_titoli = [v.get("titolo", "") for v in cronologia[-12:]
                     if isinstance(v, dict)]
    system_prompt = _costruisci_system_prompt(formato, prodotto, animale,
                                              ultimi_titoli)
    risultato = None

    for modello in config.GROQ_MODELLI:
        for tentativo in range(1, 3):
            try:
                print(f"[ZampaViva Brain] {modello} - tentativo {tentativo}...")
                response = client.chat.completions.create(
                    model=modello,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Scrivi il video di oggi."},
                    ],
                    temperature=0.9,
                    # i modelli gpt-oss ragionano prima di rispondere: serve margine
                    max_tokens=3000,
                    response_format={"type": "json_object"},
                )
                contenuto = response.choices[0].message.content
                if not contenuto:
                    continue
                data = json.loads(contenuto)
                titolo = _pulisci_titolo(str(data.get("titolo", "")))
                script = str(data.get("script", "")).strip()
                ok, motivo = valida_script(titolo, script)
                if not ok:
                    print(f"[ZampaViva Brain] SCARTATO: {motivo}. Rigenero.")
                    continue
                risultato = {
                    "titolo": titolo,
                    "script": script,
                    "query_video": str(data.get("query_video") or "cute pet").strip(),
                    "didascalia": str(data.get("didascalia") or titolo).strip(),
                    "hashtag": data.get("hashtag", []),
                    "stile": formato,
                }
                break
            except Exception as e:
                print(f"[Groq Warning] {modello}: {e}")
        if risultato:
            break

    if not risultato:
        print("[ZampaViva Brain] Tutti i modelli hanno fallito: uso il fallback.")
        risultato = _fallback(prodotto, animale, formato)

    risultato["script"] = aggiungi_frase_finale(risultato["script"])
    risultato["hashtag"] = pulisci_hashtag(risultato["hashtag"], animale)
    risultato["prodotto"] = prodotto
    risultato["animale"] = animale
    salva_in_cronologia(risultato)
    return risultato


if __name__ == "__main__":
    import sys
    dati = genera_script_zampaviva(sys.argv[1] if len(sys.argv) > 1 else None)
    print("\n" + dati["script"] + "\n")
    print(componi_didascalia(dati))
