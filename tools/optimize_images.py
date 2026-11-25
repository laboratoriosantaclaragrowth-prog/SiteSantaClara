"""Gera versões leves (WebP) das imagens pesadas do site e troca as referências.

Uso: python tools/optimize_images.py
Os arquivos originais continuam no repositório; as páginas passam a usar os .webp.
Rode de novo sempre que trocar uma dessas imagens.
"""
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# origem, destino, largura máxima, qualidade
IMAGES = [
    ("logo.png", "assets/logo-santa-clara.webp", 128, 90),
    ("assets/image_hero2.png", "assets/image_hero2.webp", 1600, 80),
    ("assets/image_hero2mob.png", "assets/image_hero2mob.webp", 800, 80),
    ("assets/equipe-provisoria.png", "assets/equipe-provisoria.webp", 900, 78),
    ("assets/lab-banner.png", "assets/lab-banner.webp", 1400, 78),
    ("assets/recepcao-ilustrativa.jpg", "assets/recepcao-ilustrativa.webp", 1400, 78),
    ("assets/fachada.jpg", "assets/fachada.webp", 1600, 82),
    ("assets/images/ebook-santa-clara.png", "assets/images/ebook-santa-clara.webp", 900, 80),
    ("assets/ate-voce/images/santa-clara-banner.png", "assets/ate-voce/images/santa-clara-banner.webp", 1200, 80),
    ("assets/ate-voce/images/destaque-servicos2.png", "assets/ate-voce/images/destaque-servicos2.webp", 900, 78),
    ("assets/ate-voce/images/destaque-vantagens.png", "assets/ate-voce/images/destaque-vantagens.webp", 900, 78),
    ("assets/ate-voce/images/region-background-mg2.png", "assets/ate-voce/images/region-background-mg2.webp", 1400, 72),
    ("assets/ate-voce/images/region-background-mg.jpg", "assets/ate-voce/images/region-background-mg.webp", 1600, 72),
]

# Trocas de texto nas páginas, estilos e scripts (o favicon continua PNG, mas pequeno).
REPLACEMENTS = [
    ('href="/logo.png"', 'href="/assets/favicon.png"'),
    ('src="/logo.png"', 'src="/assets/logo-santa-clara.webp"'),
    ('/assets/lab-banner.png?v=c4dbc6a844bd', '/assets/lab-banner.webp'),
] + [(f"/{src}", f"/{dst}") for src, dst, *_ in IMAGES if src != "logo.png"] + [
    ("../images/region-background-mg2.png", "../images/region-background-mg2.webp"),
    ("../images/region-background-mg.jpg", "../images/region-background-mg.webp"),
]
TEXT_SUFFIXES = (".html", ".css", ".js")
SKIP = ("backups/", "page-cache/", "tests/", "verification/", "imagem_rod", "original.html", "reference")


def convert(src, dst, width, quality):
    image = Image.open(ROOT / src)
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    image.save(ROOT / dst, "WEBP", quality=quality, method=6)
    return (ROOT / src).stat().st_size, (ROOT / dst).stat().st_size


def main():
    before = after = 0
    for src, dst, width, quality in IMAGES:
        if not (ROOT / src).is_file():
            print(f"falta {src}")
            continue
        old, new = convert(src, dst, width, quality)
        before, after = before + old, after + new
        print(f"{src}: {old // 1024} KB -> {new // 1024} KB")
    favicon = Image.open(ROOT / "logo.png").convert("RGBA").resize((64, 64), Image.LANCZOS)
    favicon.save(ROOT / "assets/favicon.png", optimize=True)
    print(f"Total: {before // 1024} KB -> {after // 1024} KB")

    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    for name in tracked + ["admin_painel.py"]:
        if not (name.endswith(TEXT_SUFFIXES) or name == "admin_painel.py") or any(s in name for s in SKIP):
            continue
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in REPLACEMENTS:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="")
            print(f"atualizado: {name}")


if __name__ == "__main__":
    main()
