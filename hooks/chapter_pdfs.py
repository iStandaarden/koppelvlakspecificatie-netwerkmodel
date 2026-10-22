"""
Maakt per hoofdstuk (= top-level item in de nav) een PDF, op basis van de
losse pagina-PDF's die mkdocs-exporter genereert, en ruimt de losse
pagina-PDF's daarna op zodat ze niet in gh-pages terechtkomen.

Resultaat in de site:  pdf/<hoofdstuk-slug>.pdf   (bv. pdf/indicatieregister.pdf)
De complete PDF komt van de aggregator van mkdocs-exporter (zie mkdocs.yml).

Omslag: zelfde gedrag als aggregator 'covers: book' -> voorkant van de eerste
pagina en achterkant van de laatste pagina blijven staan, alle tussenliggende
omslagpagina's worden verwijderd. Gaat uit van 1 pagina per omslag.
"""
import os
import re
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment
from mkdocs.plugins import event_priority
from mkdocs.structure.pages import Page
from mkdocs.structure.nav import Section
from pypdf import PdfReader, PdfWriter

# Zet op False als je geen cover templates gebruikt.
HAS_COVERS = True
# Hoofdstukken (titel in de nav) die je NIET als aparte PDF wilt.
SKIP_CHAPTERS = set()  # bv. {"Welkom"}

# Map met de cover-templates (relatief aan mkdocs.yml) en de standaard-URL van de complete PDF.
COVERS_DIR = "resources/templates/covers"
COMPLETE_PDF = "pdf/koppelvlakspecificatie-netwerkmodel.pdf"  # moet gelijk zijn aan aggregator.output

_nav = None
_H1 = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.M)


def _pdf_enabled():
    return os.environ.get("MKDOCS_EXPORTER_PDF_ENABLED", "").lower() in ("1", "true")


def on_config(config):
    # Zet de vlaggen voor de download-knoppen (docs/overrides/main.html) hier, zodat ze niet
    # apart in mkdocs.yml hoeven te staan.
    config.extra["pdf_enabled"] = _pdf_enabled()
    config.extra.setdefault("pdf_complete", COMPLETE_PDF)
    return config


def _page_title(page, markdown):
    # page.title is in on_page_markdown nog leeg voor pagina's zonder titel in nav of front matter;
    # dan nemen we de eerste H1 uit de markdown.
    title = page.meta.get("title") or getattr(page, "title", None)
    if not title:
        match = _H1.search(markdown)
        title = match.group(1) if match else Path(page.file.src_uri).stem
    return title


@event_priority(50)  # ná mkdocs-exporter (prioriteit 100), dat de covers vóór de markdown plakt
def on_page_markdown(markdown, page, config, files):
    """Vult {{ config... }} en {{ page... }} in de cover-templates in.

    mkdocs-exporter plakt de templates als ruwe tekst vóór/achter de markdown van elke pagina en
    rendert ze zelf niet. Alleen de template-tekst wordt hier gerenderd; de rest van de pagina
    blijft ongemoeid (dus {{ }} in Mermaid-diagrammen of codeblokken is veilig).
    """
    if not _pdf_enabled() or "mkdocs-exporter-" not in markdown:
        return markdown

    covers = Path(config["config_file_path"]).parent / COVERS_DIR
    context = {
        "config": config,
        "page": SimpleNamespace(
            title=_page_title(page, markdown), meta=page.meta, url=page.url, file=page.file
        ),
    }
    env = Environment()
    for template in sorted(covers.glob("*.j2")):
        raw = template.read_text(encoding="utf-8").strip("\n")
        if raw and raw in markdown:
            markdown = markdown.replace(raw, env.from_string(raw).render(**context))
    return markdown


def on_nav(nav, config, files):
    global _nav
    _nav = nav
    # Maak de bestandsnaam beschikbaar voor de download-knoppen in docs/overrides/main.html
    for item in nav.items:
        if isinstance(item, Section) and item.title not in SKIP_CHAPTERS:
            item.pdf_slug = _slug(item.title)
    return nav


def _pages(item):
    if isinstance(item, Page):
        yield item
    elif isinstance(item, Section):
        for child in item.children:
            yield from _pages(child)


def _slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _pdf_path(site, page):
    # mkdocs-exporter schrijft de PDF naast de HTML: foo/bar/index.html -> foo/bar/index.pdf
    return site / Path(page.file.dest_uri).with_suffix(".pdf")


@event_priority(-200)  # ná mkdocs-exporter (die gebruikt -90, -95 en -100)
def on_post_build(config):
    if not _pdf_enabled():
        return
    if _nav is None:
        return

    site = Path(config["site_dir"])
    out = site / "pdf"
    out.mkdir(parents=True, exist_ok=True)

    for section in (i for i in _nav.items if isinstance(i, Section)):
        if section.title in SKIP_CHAPTERS:
            continue
        pages = [p for p in _pages(section) if _pdf_path(site, p).exists()]
        if not pages:
            continue

        writer = PdfWriter()
        for n, page in enumerate(pages):
            pdf_pages = list(PdfReader(_pdf_path(site, page)).pages)
            if HAS_COVERS and len(pdf_pages) > 2:
                if n > 0:
                    pdf_pages = pdf_pages[1:]    # voorkant weg
                if n < len(pages) - 1:
                    pdf_pages = pdf_pages[:-1]   # achterkant weg
            writer.add_outline_item(page.title or page.file.src_uri, len(writer.pages))
            for p in pdf_pages:
                writer.add_page(p)

        target = out / f"{_slug(section.title)}.pdf"
        with open(target, "wb") as fh:
            writer.write(fh)
        print(f"[chapter_pdfs] {target.relative_to(site)}: {len(pages)} pagina's")

    # Losse pagina-PDF's opruimen (alleen die van pagina's in de nav)
    for page in _nav.pages:
        f = _pdf_path(site, page)
        if f.exists() and out not in f.parents:
            f.unlink()
