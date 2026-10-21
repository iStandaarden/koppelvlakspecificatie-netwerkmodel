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

from mkdocs.plugins import event_priority
from mkdocs.structure.pages import Page
from mkdocs.structure.nav import Section
from pypdf import PdfReader, PdfWriter

# Zet op False als je geen cover templates gebruikt.
HAS_COVERS = True
# Hoofdstukken (titel in de nav) die je NIET als aparte PDF wilt.
SKIP_CHAPTERS = set()  # bv. {"Welkom"}

_nav = None


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
    if os.environ.get("MKDOCS_EXPORTER_PDF_ENABLED", "").lower() not in ("1", "true"):
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