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

    def test_rifiuta_lunghezze_sbagliate(self):
        assert not brain.valida_script("T", "Corto.")[0]
        assert not brain.valida_script("T", "parola " * 120)[0]


class TestFraseFinale:
    def test_chiude_sempre_con_il_profilo(self):
        finale = brain.aggiungi_frase_finale("Il tuo cane tira? Ecco la soluzione.")
        assert finale.endswith(brain.FRASE_FINALE)

    def test_toglie_gli_inviti_scritti_dal_modello(self):
        finale = brain.aggiungi_frase_finale(SCRIPT_BUONO)
        assert "link in bio" not in finale
        assert finale.count("profilo") == 1
        assert "piccione?" in finale


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
                "prodotto": {"handle": "x", "url": "https://zampavivaoff.myshopify.com/products/x"}}
        testo = brain.componi_didascalia(dati)
        assert "https://zampavivaoff.myshopify.com/products/x?utm_source=tiktok" in testo
        assert "#cane #animalidomestici" in testo


class TestMontaggio:
    def test_apre_con_una_clip_e_alterna(self):
        sorgenti = ([{"tipo": "immagine", "path": f"i{i}"} for i in range(3)]
                    + [{"tipo": "video", "path": f"v{i}"} for i in range(3)])
        ordinate = maker.ordina_sorgenti(sorgenti)
        assert [s["tipo"] for s in ordinate] == ["video", "immagine"] * 3
        assert ordinate[1]["path"] == "i0"


class TestDidascalia:
    DATI = {
        "didascalia": "Passeggiate senza strattoni ",
        "hashtag": ["#cane", "#zampaviva"],
        "prodotto": {"handle": "pettorina", "url": "https://negozio/products/pettorina"},
    }

    def test_link_con_utm_tiktok(self, monkeypatch):
        monkeypatch.setattr(brain.config, "CODICE_SCONTO", "")
        testo = brain.componi_didascalia(self.DATI)
        assert testo.endswith("https://negozio/products/pettorina"
                              "?utm_source=tiktok&utm_medium=video&utm_campaign=pettorina")
        assert "codice" not in testo.lower()

    def test_codice_sconto_valido(self, monkeypatch):
        monkeypatch.setattr(brain.config, "CODICE_SCONTO", "BENVENUTO10")
        monkeypatch.setattr(brain.config, "CODICE_SCONTO_SCADENZA", "2026-12-12")
        testo = brain.componi_didascalia(self.DATI, oggi="2026-10-13")
        assert "Usa il codice BENVENUTO10 al checkout" in testo

    def test_codice_sconto_scaduto_sparisce(self, monkeypatch):
        monkeypatch.setattr(brain.config, "CODICE_SCONTO", "BENVENUTO10")
        monkeypatch.setattr(brain.config, "CODICE_SCONTO_SCADENZA", "2026-12-12")
        testo = brain.componi_didascalia(self.DATI, oggi="2026-12-13")
        assert "BENVENUTO10" not in testo


class TestAggiornaUltimaVoce:
    def test_aggiunge_campi_all_ultima(self, tmp_path, monkeypatch):
        import json
        f = tmp_path / "cron.json"
        f.write_text(json.dumps([{"handle": "a"}, {"handle": "b"}]), encoding="utf-8")
        monkeypatch.setattr(brain.config, "FILE_CRONOLOGIA", str(f))
        brain.aggiorna_ultima_voce({"video_file_url": "https://blob/x.mp4"})
        dati = json.loads(f.read_text(encoding="utf-8"))
        assert dati[-1] == {"handle": "b", "video_file_url": "https://blob/x.mp4"}
        assert "video_file_url" not in dati[0]

    def test_niente_campi_niente_scrittura(self, tmp_path, monkeypatch):
        f = tmp_path / "cron.json"
        monkeypatch.setattr(brain.config, "FILE_CRONOLOGIA", str(f))
        brain.aggiorna_ultima_voce({})
        assert not f.exists()


class TestPianoSettimana:
    # domenica 25/10/2026 alle 17:00 UTC (18:00 italiane, ora solare)
    DOMENICA = 1792947600

    def _voce(self, ore_fa, titolo):
        return {"timestamp": self.DOMENICA - ore_fa * 3600, "titolo": titolo}

    def test_due_al_giorno_dal_lunedi_in_ordine(self):
        cron = [self._voce(10, "C"), self._voce(150, "A"), self._voce(100, "B")]
        righe = brain.piano_settimana(cron, self.DOMENICA)
        assert righe == ["1. lunedì 26/10 12:30 - A",
                         "2. lunedì 26/10 19:00 - B",
                         "3. martedì 27/10 12:30 - C"]

    def test_esclude_i_video_vecchi_e_quelli_futuri(self):
        cron = [self._voce(169, "vecchio"), self._voce(-1, "dopo"), "voce stringa",
                self._voce(1, "ok")]
        assert brain.piano_settimana(cron, self.DOMENICA) == ["1. lunedì 26/10 12:30 - ok"]

    def test_settimana_vuota(self):
        assert brain.piano_settimana([], self.DOMENICA) == []
