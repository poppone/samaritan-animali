# ZampaViva TikTok

Genera video TikTok per il negozio ZampaViva e li manda su Telegram con la
didascalia pronta. **La pubblicazione su TikTok la fai tu, a mano.**

```
FASE 1  brain.py     prodotto in rotazione dal catalogo pubblico Shopify,
                     formato, script, didascalia e hashtag (Groq)
FASE 2  media.py     foto del prodotto (Shopify) + clip di cani e gatti (Pexels)
        voice.py     voce neurale Edge-TTS
        maker.py     montaggio 9:16, stacchi, zoom, sottotitoli (Whisper)
FASE 3  notifier.py  video + didascalia su Telegram
```

## In cloud (GitHub Actions)

`.github/workflows/zampaviva.yml` fa un video ogni mattina, senza il PC acceso.
Il video arriva su Telegram come prima e la cronologia si salva da sola.
Secrets del repository (Settings > Secrets and variables > Actions):
`GROQ_API_KEY`, `PEXELS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
(gli stessi valori del file `.env`) e, facoltativo, `BLOB_READ_WRITE_TOKEN`:
con quello il video si carica anche su Vercel Blob (`copia_pubblica.py`) e la
stanza degli agenti puo' proporlo per TikTok.
Si lancia anche a mano da Actions > ZampaViva TikTok > Run workflow.

## Configurazione

Le chiavi NON stanno in questa cartella. Crea `C:\Users\<utente>\.zampaviva\.env`
partendo da `.env.example` (servono `GROQ_API_KEY`, `PEXELS_API_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Per usare un altro percorso imposta
la variabile d'ambiente `ZAMPAVIVA_ENV`.

## Uso

```bash
pip install -r requirements.txt     # serve anche FFmpeg nel PATH
python main.py                      # prodotto in rotazione
python main.py borraccia            # prodotto specifico (handle o parola del titolo)
python brain.py                     # solo testo, senza video
```

Oppure doppio click su `run_zampaviva.bat`.

Il video finisce in `output_videos/` insieme a un `.txt` con la didascalia.
La memoria dei prodotti e dei formati usati sta in `cronologia_zampaviva.json`.

## Test

```bash
pip install pytest
python -m pytest tests -q
```
