"""
Genera il logo ZampaViva (foto profilo TikTok, 1080x1080) in alcune varianti
di colore. TikTok ritaglia la foto profilo a cerchio: tutto il contenuto
importante sta nel cerchio centrale.

    python crea_logo.py      ->  logo/zampaviva_logo_*.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

LATO = 1080
DIR_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo")

VARIANTI = {
    "arancio": {"fondo": "#FF9F1C", "zampa": "#FFFFFF", "testo": "#FFFFFF"},
    "crema": {"fondo": "#FFF4E0", "zampa": "#FF7A00", "testo": "#3B2A1A"},
    "verde": {"fondo": "#2EC4B6", "zampa": "#FFFFFF", "testo": "#FFFFFF"},
}

_FONT = ["C:/Windows/Fonts/arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font(dimensione):
    for path in _FONT:
        try:
            return ImageFont.truetype(path, dimensione)
        except OSError:
            continue
    return ImageFont.load_default()


def _ellisse(draw, cx, cy, rx, ry, colore, s):
    draw.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s],
                 fill=colore)


def disegna_zampa(draw, cx, cy, scala, colore, s):
    """Impronta: cuscinetto centrale + 4 dita, coordinate in unita' logo."""
    _ellisse(draw, cx, cy + 40 * scala, 120 * scala, 100 * scala, colore, s)
    for dx, dy, rx, ry in ((-150, -90, 48, 62), (-58, -170, 50, 66),
                           (58, -170, 50, 66), (150, -90, 48, 62)):
        _ellisse(draw, cx + dx * scala, cy + dy * scala, rx * scala, ry * scala,
                 colore, s)


def crea_logo(nome, colori, s=3):
    """Disegna a 3x e riduce: bordi morbidi senza antialias manuale."""
    img = Image.new("RGB", (LATO * s, LATO * s), colori["fondo"])
    draw = ImageDraw.Draw(img)

    disegna_zampa(draw, LATO / 2, 430, 1.25, colori["zampa"], s)

    font = _font(150 * s)
    testo = "ZampaViva"
    w = draw.textlength(testo, font=font)
    draw.text(((LATO * s - w) / 2, 690 * s), testo, font=font,
              fill=colori["testo"])

    img = img.resize((LATO, LATO), Image.LANCZOS)
    os.makedirs(DIR_LOGO, exist_ok=True)
    percorso = os.path.join(DIR_LOGO, f"zampaviva_logo_{nome}.png")
    img.save(percorso)

    # Anteprima del ritaglio circolare usato da TikTok
    maschera = Image.new("L", (LATO, LATO), 0)
    ImageDraw.Draw(maschera).ellipse([0, 0, LATO, LATO], fill=255)
    cerchio = Image.new("RGBA", (LATO, LATO), (0, 0, 0, 0))
    cerchio.paste(img, mask=maschera)
    cerchio.save(os.path.join(DIR_LOGO, f"anteprima_cerchio_{nome}.png"))
    return percorso


if __name__ == "__main__":
    for nome, colori in VARIANTI.items():
        print(crea_logo(nome, colori))
