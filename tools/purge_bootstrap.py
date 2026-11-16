"""Gera um Bootstrap enxuto para a página "Santa Clara até você".

Mantém só as regras cujas classes aparecem na página ou nos scripts dela.
O Bootstrap completo fica em tools/vendor/bootstrap-5.1.1.css (não vai para o site).
Uso: python tools/purge_bootstrap.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools/vendor/bootstrap-5.1.1.css"
TARGET = ROOT / "assets/ate-voce/css/bootstrap.min.css"
PAGES = [ROOT / "santa-clara-ate-voce/index.html"]
SCRIPTS = [ROOT / "assets/ate-voce/page.js", ROOT / "assets/lead-tracking.js",
           ROOT / "assets/analytics-preferences.js", ROOT / "assets/ebook-popup.js"]
# Classes que os scripts colocam e tiram (menu, sanfona do FAQ).
DYNAMIC = {"show", "collapsed", "collapsing", "active", "fade", "hidden"}


def used_classes():
    names = set(DYNAMIC)
    for page in PAGES:
        for value in re.findall(r'class="([^"]*)"', page.read_text(encoding="utf-8")):
            names.update(value.split())
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        names.update(re.findall(r"""['"`\s.]([a-z][\w-]*)""", text))
    return names


def split_blocks(css):
    """Divide o CSS em blocos de nível superior: (prelúdio, corpo)."""
    blocks, i, n = [], 0, len(css)
    while i < n:
        start = css.find("{", i)
        if start == -1:
            break
        prelude = css[i:start].strip()
        depth, j = 1, start + 1
        while depth and j < n:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        blocks.append((prelude, css[start + 1:j - 1]))
        i = j
    return blocks


def keep_selector(selector, used):
    classes = re.findall(r"\.([\w-]+)", re.sub(r"\[[^\]]*\]|:not\([^)]*\)", "", selector))
    return all(c in used for c in classes)


def purge(css, used):
    out = []
    for prelude, body in split_blocks(css):
        if prelude.startswith("@media") or prelude.startswith("@supports"):
            inner = purge(body, used)
            if inner:
                out.append(f"{prelude}{{{inner}}}")
        elif prelude.startswith("@"):
            out.append(f"{prelude}{{{body}}}")
        else:
            selectors = [s.strip() for s in prelude.split(",") if keep_selector(s.strip(), used)]
            if selectors:
                out.append(f"{','.join(selectors)}{{{body.strip()}}}")
    return "".join(out)


def minify(css):
    css = re.sub(r"/\*#\s*sourceMappingURL=[^*]*\*/", "", css)
    css = re.sub(r"/\*(?!!)[\s\S]*?\*/", "", css)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
    return css.replace(";}", "}")


def main():
    css = minify(SOURCE.read_text(encoding="utf-8"))
    css = css.removeprefix('@charset "UTF-8";')
    license = re.match(r"\s*(/\*![\s\S]*?\*/)", css)
    if license:
        css = css[license.end():]
    header = '@charset "UTF-8";' + ("/*! Bootstrap v5.1.1 | MIT License | https://getbootstrap.com */" if license else "")
    result = header + purge(css, used_classes())
    TARGET.write_text(result, encoding="utf-8")
    print(f"{SOURCE.stat().st_size // 1024} KB -> {len(result.encode()) // 1024} KB")


if __name__ == "__main__":
    main()
