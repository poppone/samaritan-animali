"""Test sulla logica pura di brain.py e maker.py: niente rete."""
import brain
import maker

SCRIPT_BUONO = (
    "Il tuo cane tira al guinzaglio appena vede un piccione? "
    "Succede a tantissimi, e il collo ne fa le spese. "
    "Questa pettorina distribuisce la trazione sul petto. "
    "Niente strattoni sulla gola, e tu hai piu' controllo. "
    "In piu' ha dettagli riflettenti per le passeggiate serali. "
    "La trovi al link in bio. E la prossima volta che vede un piccione?"
)

PRODOTTO_GREZZO = {
    "handle": "pettorina-anti-tiro",
    "title": "Pettorina anti-tiro",
    "body_html": "<p><strong>Passeggiate rilassate</strong> &amp; sicure.</p>"
                 "<ul><li>Riflettente</li></ul>",
    "variants": [{"price": "29.90"}, {"price": "24.90"}],
    "images": [{"src": "https://cdn.example/a.jpg"}, {"src": "https://cdn.example/b.jpg"}],
    "tags": ["Cane", "top"],
    "product_type": "Pettorine",
}


def _prodotto(handle, tags=("cane",)):
    return {"handle": handle, "titolo": handle.title(), "tags": list(tags),
            "tipo": "", "url": f"https://x/products/{handle}"}


class TestValidaScript:
    def test_accetta_uno_script_buono(self):
        ok, motivo = brain.valida_script("Titolo", SCRIPT_BUONO)
        assert ok, motivo

    def test_rifiuta_i_saluti(self):
        for apertura in ("Ciao a tutti", "Benvenuti", "Oggi vi parlo", "Ragazzi, "):
            ok, motivo = brain.valida_script("T", apertura + " " + SCRIPT_BUONO)
            assert not ok and "apertura" in motivo

    def test_rifiuta_senza_link_in_bio(self):
        ok, motivo = brain.valida_script("T", SCRIPT_BUONO.replace("link in bio", "negozio"))
        assert not ok and "bio" in motivo

    def test_rifiuta_lunghezze_sbagliate(self):
        assert not brain.valida_script("T", "Corto. link in bio")[0]
        assert not brain.valida_script("T", "parola " * 120 + "bio")[0]


class TestCatalogo:
    def test_normalizza_prodotto(self):
        p = brain.normalizza_prodotto(PRODOTTO_GREZZO)
        assert p["prezzo"] == "24.90"
        assert "Passeggiate rilassate & sicure." in p["descrizione"]
        assert "<" not in p["descrizione"]
        assert p["immagini"] == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"]
        assert p["tags"] == ["cane", "top"]
        assert p["url"].endswith("/products/pettorina-anti-tiro")

    def test_animale(self):
        assert brain.animale_del_prodotto(_prodotto("a", ["cane"])) == "cane"
        assert brain.animale_del_prodotto(_prodotto("a", ["gatto"])) == "gatto"
        assert brain.animale_del_prodotto(_prodotto("a", ["cane", "gatto"])) == "cane e gatto"
        assert brain.animale_del_prodotto(_prodotto("a", [])) == "cane e gatto"


class TestRotazione:
    def test_preferisce_i_mai_usati(self):
        catalogo = [_prodotto("a"), _prodotto("b"), _prodotto("c")]
        cronologia = [{"handle": "a"}, {"handle": "b"}]
        assert brain.scegli_prodotto(catalogo, cronologia)["handle"] == "c"

    def test_poi_il_meno_recente(self):
        catalogo = [_prodotto("a"), _prodotto("b")]
        cronologia = [{"handle": "b"}, {"handle": "a"}, {"handle": "b"}]
        assert brain.scegli_prodotto(catalogo, cronologia)["handle"] == "a"

    def test_prodotto_richiesto(self):
        catalogo = [_prodotto("a"), _prodotto("borraccia")]
        assert brain.scegli_prodotto(catalogo, [], "borraccia")["handle"] == "borraccia"

    def test_formato_non_ripete_gli_ultimi(self):
        cronologia = [{"stile": "TRE_MOTIVI"}, {"stile": "PRIMA_DOPO"}]
        for _ in range(30):
            assert brain.scegli_formato(cronologia) not in {"TRE_MOTIVI", "PRIMA_DOPO"}


class TestHashtag:
    def test_sempre_tra_3_e_5(self):
        assert 3 <= len(brain.pulisci_hashtag([], "cane")) <= 5
        molti = [f"#tag{i}" for i in range(10)]
        assert len(brain.pulisci_hashtag(molti, "cane e gatto")) == 5

    def test_normalizza_e_include_le_basi(self):
        h = brain.pulisci_hashtag(["Gatti Di TikTok", "#gatto", "#Petlover"], "gatto")
        assert h[:2] == ["#gatto", "#animalidomestici"]
        assert "#petlover" in h
        assert len(h) == len(set(h))
        assert all(x.startswith("#") and " " not in x for x in h)

    def test_didascalia_con_link(self):
        dati = {"didascalia": "Lo vuoi?", "hashtag": ["#cane", "#animalidomestici"],
                "prodotto": {"url": "https://zampaviva-5.myshopify.com/products/x"}}
        testo = brain.componi_didascalia(dati)
        assert testo.endswith("https://zampaviva-5.myshopify.com/products/x")
        assert "#cane #animalidomestici" in testo


class TestMontaggio:
    def test_apre_con_una_clip_e_alterna(self):
        sorgenti = ([{"tipo": "immagine", "path": f"i{i}"} for i in range(3)]
                    + [{"tipo": "video", "path": f"v{i}"} for i in range(3)])
        ordinate = maker.ordina_sorgenti(sorgenti)
        assert [s["tipo"] for s in ordinate] == ["video", "immagine"] * 3
        assert ordinate[1]["path"] == "i0"
