"""Prepare search metadata for the current static pages without rebuilding them."""

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, indent, tostring

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SECTIONS = ("blog", "contato", "exames", "santa-clara-ate-voce")
CANONICAL = re.compile(r'''<link\b(?=[^>]*\brel\s*=\s*["']canonical["'])[^>]*>''', re.I)
SOCIAL_URL = re.compile(r'''<meta\b(?=[^>]*\bproperty\s*=\s*["']og:url["'])[^>]*>''', re.I)
STRUCTURED = re.compile(r'''(<script\b[^>]*\btype\s*=\s*["']application/ld\+json["'][^>]*>)(.*?)(</script>)''', re.I | re.S)
PAGE_TYPES = {"/contato/": "ContactPage", "/santa-clara-ate-voce/": "WebPage"}
LLMS_LINKS = (
    ("Página inicial", "/", "Informações sobre o laboratório e seus serviços em Araçuaí."),
    ("Guia de exames", "/exames/", "Exames com páginas informativas e orientações de atendimento."),
    ("Onde fazer exames em Araçuaí", "/exames/aracuai/", "Como consultar disponibilidade e planejar a visita."),
    ("Coleta domiciliar", "/santa-clara-ate-voce/", "Como consultar cobertura e disponibilidade para seu endereço."),
    ("Contato e localização", "/contato/", "Canais oficiais de atendimento e informações da unidade."),
    ("Blog de exames", "/blog/", "Orientações sobre preparo, coleta, convênios e resultados."),
)


def render_llms(origin=""):
    links = "\n".join(f"- [{label}]({origin}{route}): {description}" for label, route, description in LLMS_LINKS)
    return (
        "# Laboratório Santa Clara\n\n"
        "> Laboratório de análises clínicas em Araçuaí, Minas Gerais. "
        "O site reúne informações sobre exames, preparo, atendimento e coleta domiciliar.\n\n"
        "## Páginas principais\n\n"
        f"{links}\n\n"
        "Confirme exames, preparo, horários e cobertura da coleta domiciliar pelos canais de atendimento do laboratório.\n"
    )


def schema_json(value):
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def prepare_schema(head, origin, route):
    url = origin + route

    def update(match):
        data = json.loads(match[2])
        if not isinstance(data, dict) or data.get("@type") not in {"Blog", "BlogPosting", "WebPage", "MedicalWebPage", "ContactPage"}:
            return match[0]
        data["url"] = url
        if data.get("@type") == "BlogPosting":
            data["mainEntityOfPage"] = url
        publisher = data.get("publisher")
        if isinstance(publisher, dict) and publisher.get("@type") == "MedicalClinic":
            publisher.update({"@id": origin + "/#laboratorio", "url": origin + "/"})
        return match[1] + schema_json(data) + match[3]

    if STRUCTURED.search(head):
        return STRUCTURED.sub(update, head)
    if route in PAGE_TYPES:
        title = re.search(r"<title>(.*?)</title>", head, re.I | re.S)
        data = {"@context": "https://schema.org", "@type": PAGE_TYPES[route], "url": url,
                "inLanguage": "pt-BR", "about": {"@id": origin + "/#laboratorio"}}
        if title:
            data["name"] = unescape(title[1]).strip()
        return head + f'\n<script type="application/ld+json">{schema_json(data)}</script>'
    return head


def prepare_updates(root, site_url):
    origin = site_url.strip().removesuffix("/")
    if not re.fullmatch(r"https://(?:[a-z0-9-]+\.)+[a-z0-9-]+", origin, re.I):
        raise ValueError("Informe o domínio público HTTPS em content/business.json (siteUrl), sem caminho.")

    pages = [root / "index.html"]
    for section in PUBLIC_SECTIONS:
        pages.extend(sorted((root / section).rglob("index.html")))

    sitemap = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    updates = {}
    for page in pages:
        directory = page.parent.relative_to(root)
        route = "/" if directory == Path(".") else f"/{quote(directory.as_posix())}/"
        url = origin + route
        head, closing, body = page.read_text(encoding="utf-8").partition("</head>")
        if not closing:
            raise ValueError(f"Cabeçalho HTML não encontrado em {page.relative_to(root)}.")
        head = SOCIAL_URL.sub("", CANONICAL.sub("", head)).rstrip()
        head = prepare_schema(head, origin, route)
        updates[page] = f'{head}\n<link rel="canonical" href="{url}">\n<meta property="og:url" content="{url}">\n{closing}{body}'
        SubElement(SubElement(sitemap, "url"), "loc").text = url

    indent(sitemap)
    updates[root / "sitemap.xml"] = tostring(sitemap, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n"
    robots_path = root / "robots.txt"
    robots = robots_path.read_text(encoding="utf-8") if robots_path.exists() else "User-agent: *\nAllow: /\n"
    directives = [line for line in robots.splitlines() if not re.match(r"\s*sitemap\s*:", line, re.I)]
    updates[robots_path] = "\n".join(directives).rstrip() + f"\n\nSitemap: {origin}/sitemap.xml\n"
    updates[root / "llms.txt"] = render_llms(origin)
    return updates


if __name__ == "__main__":
    config = json.loads((ROOT / "content/business.json").read_text(encoding="utf-8"))
    try:
        updates = prepare_updates(ROOT, config["siteUrl"])
    except ValueError as error:
        raise SystemExit(str(error)) from None
    for path, text in updates.items():
        path.write_text(text, encoding="utf-8")
    print(f"Sitemap, URLs canônicas, metadados e llms.txt gerados para {len(updates) - 3} páginas.")
