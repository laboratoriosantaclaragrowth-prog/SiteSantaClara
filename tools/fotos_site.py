"""Gera as versões leves (WebP) das fotos reais do laboratório usadas no site.

Os originais ficam em fotos/ (fora do Git, são muito grandes).
Uso: python tools/fotos_site.py
"""
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fotos"
DST = ROOT / "assets/fotos"

# original, nome no site, maior lado em pixels
PHOTOS = [
    ("FACHADA.jpg", "fachada-laboratorio-santa-clara", 1400),
    ("IMG_9940.jpg", "coleta-de-sangue-paciente", 1400),
    ("IMG_9995.jpg", "recepcao-atendimento", 1200),
    ("IMG_9980.jpg", "recepcao-balcao", 1200),
    ("IMG_9843.jpg", "microscopio-analise", 1200),
    ("IMG_9838.jpg", "microscopio-lamina", 1200),
    ("IMG_9851.jpg", "microscopio-urina", 1200),
    ("IMG_9819.jpg", "analisador-hematologico", 1200),
    ("IMG_9857.jpg", "analisador-bioquimico", 1200),
    ("IMG_9859.jpg", "analisador-bioquimico-amostras", 1200),
    ("IMG_9879.jpg", "analisador-tecnica", 1200),
    ("IMG_9821.jpg", "laudos-computador", 1200),
    ("IMG_9902.jpg", "coleta-paciente", 1200),
    ("IMG_9945.jpg", "coleta-braco", 1200),
]

# Fotos pequenas da galeria (a primeira da galeria usa a versão grande)
THUMBS = ["microscopio-analise", "analisador-hematologico", "analisador-bioquimico", "coleta-braco",
          "microscopio-lamina", "laudos-computador", "analisador-tecnica", "microscopio-urina"]


def main():
    DST.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, slug, size in PHOTOS:
        image = Image.open(SRC / name)
        image.draft("RGB", (size * 2, size * 2))  # leitura rápida de JPEG grande
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((size, size), Image.LANCZOS)
        out = DST / f"{slug}.webp"
        image.save(out, "WEBP", quality=78, method=6)
        total += out.stat().st_size
        print(f"{slug}.webp {image.size[0]}x{image.size[1]} {out.stat().st_size // 1024} KB")
    # Miniaturas da galeria da home (640 px)
    for slug in THUMBS:
        image = Image.open(DST / f"{slug}.webp")
        image.thumbnail((640, 640), Image.LANCZOS)
        image.save(DST / f"{slug}-p.webp", "WEBP", quality=76, method=6)
        total += (DST / f"{slug}-p.webp").stat().st_size
    # Imagem de compartilhamento (WhatsApp, Facebook): 1200x630 em JPG
    share = ImageOps.fit(ImageOps.exif_transpose(Image.open(SRC / "FACHADA.jpg")).convert("RGB"), (1200, 630),
                         Image.LANCZOS, centering=(0.5, 0.4))
    share.save(ROOT / "assets/compartilhar.jpg", "JPEG", quality=82, optimize=True, progressive=True)
    print(f"Total: {total // 1024} KB")


if __name__ == "__main__":
    main()
