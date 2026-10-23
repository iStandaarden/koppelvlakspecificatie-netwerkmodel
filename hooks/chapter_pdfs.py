"""
Aanvullingen op mkdocs-exporter (PDF):

1. Vult {{ ... }} in de cover-templates in en zet per pagina een hoofdstukmarkering voor de kopregel.
2. Maakt per hoofdstuk (= top-level item in de nav) een PDF:  pdf/<hoofdstuk-slug>.pdf
3. Voegt aan de complete PDF (aggregator) een klikbare inhoudsopgave en bladwijzers toe.
4. Ruimt de losse pagina-PDF's op zodat ze niet in gh-pages terechtkomen.

Uitgangspunt voor de covers: alleen een voorblad (HAS_FRONT) bij het begin van een document; in de
aggregator moet daarom  covers: limits  staan en er mag geen achterblad zijn geconfigureerd.
"""
import html
import io
import logging
import os
import re
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment
from mkdocs.plugins import event_priority
from mkdocs.structure.nav import Section
from mkdocs.structure.pages import Page
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject

log = logging.getLogger("mkdocs.hooks.chapter_pdfs")

# --- Instellingen -------------------------------------------------------------------------------
COVERS_DIR = "resources/templates/covers"                      # relatief aan mkdocs.yml
COMPLETE_PDF = "pdf/koppelvlakspecificatie-netwerkmodel.pdf"   # moet gelijk zijn aan aggregator.output
HAS_FRONT = True       # voorblad geconfigureerd (covers.front)
HAS_BACK = False       # achterblad geconfigureerd (covers.back)
SKIP_CHAPTERS = set()  # hoofdstukken (titel in de nav) zonder aparte PDF, bv. {"Welkom"}
TOC_TITLE = "Inhoudsopgave"
TOC_LEVEL = 3          # diepte van de inhoudsopgave (1 = alleen hoofdstukken)
GREEN = (0x02 / 255, 0x6E / 255, 0x06 / 255)
# -------------------------------------------------------------------------------------------------

_nav = None
_H1 = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.M)


def _pdf_enabled():
    return os.environ.get("MKDOCS_EXPORTER_PDF_ENABLED", "").lower() in ("1", "true")


def on_config(config):
    # Vlaggen voor de download-knoppen (docs/overrides/main.html) en standaardwaarden voor de covers.
    config.extra["pdf_enabled"] = _pdf_enabled()
    config.extra.setdefault("pdf_complete", COMPLETE_PDF)
    config.extra.setdefault("pdf_title", config.site_name)
    config.extra.setdefault("pdf_copyright", "")
    return config


def on_nav(nav, config, files):
    global _nav
    _nav = nav
    # Bestandsnaam voor de hoofdstuk-knop in docs/overrides/main.html
    for item in nav.items:
        if isinstance(item, Section) and item.title not in SKIP_CHAPTERS:
            item.pdf_slug = _slug(item.title)
    return nav


# --- 1. Covers invullen en hoofdstukmarkering ----------------------------------------------------
def _page_title(page, markdown):
    # page.title is in on_page_markdown nog leeg voor pagina's zonder titel in nav of front matter;
    # dan nemen we de eerste H1 uit de markdown.
    title = page.meta.get("title") or getattr(page, "title", None)
    if not title:
        match = _H1.search(markdown)
        title = match.group(1) if match else Path(page.file.src_uri).stem
    return title


def _chapter(page):
    return page.ancestors[-1].title if page.ancestors else None


@event_priority(50)  # ná mkdocs-exporter (prioriteit 100), dat de covers vóór de markdown plakt
def on_page_markdown(markdown, page, config, files):
    """Rendert de cover-templates en zet de hoofdstukmarkering direct na het voorblad.

    mkdocs-exporter plakt de templates als ruwe tekst vóór de markdown en rendert ze zelf niet.
    Alleen die template-tekst wordt hier gerenderd; de rest van de pagina blijft ongemoeid (dus
    {{ }} in Mermaid-diagrammen of codeblokken is veilig).
    """
    if not _pdf_enabled():
        return markdown

    # MkDocs haalt een paginatitel uit het EERSTE element van de pagina. Doordat mkdocs-exporter een
    # voorblad vóór de kop plakt, valt MkDocs anders terug op de bestandsnaam ("Index"). Op dit punt is
    # page.title nog op basis van de originele markdown, dus zetten we hem vast in de metadata.
    title = _page_title(page, markdown)
    if "title" not in page.meta:
        page.meta["title"] = title

    depth = len([part for part in page.url.split("/") if part])
    context = {
        "config": config,
        "base": "../" * depth,   # relatief pad naar de docs-root, voor afbeeldingen in de cover
        "chapter": _chapter(page),
        "page": SimpleNamespace(
            title=title, meta=page.meta, url=page.url, file=page.file
        ),
    }

    front_rendered = None
    if "mkdocs-exporter-" in markdown:
        env = Environment()
        covers = Path(config["config_file_path"]).parent / COVERS_DIR
        for template in sorted(covers.glob("*.j2")):
            raw = template.read_text(encoding="utf-8").strip("\n")
            if raw and raw in markdown:
                rendered = env.from_string(raw).render(**context)
                markdown = markdown.replace(raw, rendered)
                if template.name.startswith("front"):
                    front_rendered = rendered

    chapter = context["chapter"]
    if chapter:
        marker = f'<div class="pdf-chapter">{html.escape(chapter)}</div>\n\n'
        # mkdocs-exporter: '<div class="mkdocs-exporter-front-cover" ...>' + inhoud + '</div>\n'
        end = front_rendered + "</div>\n" if front_rendered is not None else None
        pos = markdown.find(end) if end else -1
        if pos != -1:
            pos += len(end)
            markdown = markdown[:pos] + "\n" + marker + markdown[pos:]
        else:
            markdown = marker + markdown
    return markdown


# --- Hulpfuncties voor PDF's ---------------------------------------------------------------------
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


def _slice(i, count, total):
    """Welke pagina's van de losse PDF van document i (van count) blijven over (covers: limits)."""
    start, end = 0, total
    if HAS_FRONT and i > 0:
        start = 1                 # voorblad alleen bij het eerste document
    if HAS_BACK and i < count - 1:
        end = total - 1           # achterblad alleen bij het laatste document
    if end - start < 1:
        return 0, total
    return start, end


# --- 2. Hoofdstuk-PDF's, 3. inhoudsopgave in de complete PDF, 4. opruimen -------------------------
@event_priority(-200)  # ná mkdocs-exporter (die gebruikt -90, -95 en -100)
def on_post_build(config):
    if not _pdf_enabled() or _nav is None:
        return

    site = Path(config["site_dir"])
    out = site / "pdf"
    out.mkdir(parents=True, exist_ok=True)

    counts = {}
    for page in _nav.pages:
        f = _pdf_path(site, page)
        if f.exists():
            counts[page.file.src_uri] = len(PdfReader(f).pages)   # sleutel = bronpad (Page is niet hashbaar)

    # Hoofdstuk-PDF's
    for section in (i for i in _nav.items if isinstance(i, Section)):
        if section.title in SKIP_CHAPTERS:
            continue
        pages = [p for p in _pages(section) if p.file.src_uri in counts]
        if not pages:
            continue

        writer = PdfWriter()
        for n, page in enumerate(pages):
            pdf_pages = list(PdfReader(_pdf_path(site, page)).pages)
            start, end = _slice(n, len(pages), len(pdf_pages))
            writer.add_outline_item(page.title or page.file.src_uri, len(writer.pages))
            for p in pdf_pages[start:end]:
                writer.add_page(p)

        target = out / f"{_slug(section.title)}.pdf"
        with open(target, "wb") as fh:
            writer.write(fh)
        print(f"[chapter_pdfs] {target.relative_to(site)}: {len(pages)} pagina's")

    # Inhoudsopgave en bladwijzers in de complete PDF
    try:
        _finish_complete(site, counts, config)
    except Exception:  # de site mag niet stuk gaan door de inhoudsopgave; de PDF blijft bruikbaar
        log.warning("Inhoudsopgave voor de complete PDF is mislukt; PDF zonder inhoudsopgave.", exc_info=True)

    # Losse pagina-PDF's opruimen (alleen die van pagina's in de nav)
    for page in _nav.pages:
        f = _pdf_path(site, page)
        if f.exists() and out not in f.parents:
            f.unlink()


def _finish_complete(site, counts, config):
    target = site / COMPLETE_PDF
    pages = [p for p in _nav.pages if p.file.src_uri in counts]
    if not target.exists() or not pages:
        log.warning("Complete PDF niet gevonden op %s; inhoudsopgave overgeslagen.", COMPLETE_PDF)
        return

    # Beginpositie (0-based) van elke pagina in de PDF van de aggregator, vóór de inhoudsopgave.
    start_of, content_start, pos = {}, {}, 0
    for i, page in enumerate(pages):
        key = page.file.src_uri
        s, e = _slice(i, len(pages), counts[key])
        start_of[key] = pos
        content_start[key] = pos + (1 if (HAS_FRONT and i == 0) else 0)  # voorblad zelf overslaan
        pos += e - s

    reader = PdfReader(target)
    if len(reader.pages) != pos:
        log.warning(
            "Complete PDF heeft %d pagina's, verwacht %d. Controleer 'covers: limits' en HAS_FRONT/HAS_BACK "
            "in de hook; inhoudsopgave overgeslagen.", len(reader.pages), pos,
        )
        return

    tree = [n for n in (_node(i, 1, content_start, start_of) for i in _nav.items) if n]
    entries = []
    _flatten(tree, entries)

    toc_pdf, links = _build_toc(entries)
    toc_reader = PdfReader(io.BytesIO(toc_pdf))
    toc_len = len(toc_reader.pages)
    ins = 1 if HAS_FRONT else 0

    def final(idx):
        return idx + toc_len if idx >= ins else idx

    writer = PdfWriter()
    for p in reader.pages[:ins]:
        writer.add_page(p)
    for p in toc_reader.pages:
        writer.add_page(p)
    for p in reader.pages[ins:]:
        writer.add_page(p)

    # Let op: pypdf's Link(target_page_index=...) schrijft een paginanummer als doel; viewers verwachten
    # een verwijzing naar het paginaobject. Daarom bouwen we de annotatie zelf op (met /A in plaats van
    # /Dest, anders past pypdf er zelf een eigen omzetting op toe).
    for toc_page, rect, entry in links:
        dest = writer.pages[final(entry["index"])].indirect_reference
        writer.add_annotation(
            page_number=ins + toc_page,
            annotation=DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): ArrayObject([FloatObject(v) for v in rect]),
                NameObject("/Border"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)]),
                NameObject("/A"): DictionaryObject({           # GoTo-actie: werkt in alle viewers
                    NameObject("/S"): NameObject("/GoTo"),
                    NameObject("/D"): ArrayObject([dest, NameObject("/Fit")]),
                }),
            }),
        )

    writer.add_outline_item(TOC_TITLE, ins)

    def outline(nodes, parent=None):
        for node in nodes:
            item = writer.add_outline_item(node["title"], final(node["index"]), parent=parent)
            outline(node["children"], item)

    outline(tree)
    writer.add_metadata({"/Title": str(config.extra.get("pdf_title") or config.site_name), "/Producer": "MkDocs Exporter"})

    tmp = target.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        writer.write(fh)
    tmp.replace(target)
    print(f"[chapter_pdfs] {target.relative_to(site)}: inhoudsopgave ({toc_len} p.), {len(entries)} regels, bladwijzers")


def _node(item, level, content_start, start_of):
    if isinstance(item, Page):
        key = item.file.src_uri
        if key not in start_of:
            return None
        # Eerste pagina: de inhoud begint na het voorblad; andere pagina's beginnen direct.
        return {"title": item.title or item.file.src_uri, "level": level,
                "index": content_start[key], "number": content_start[key] + 1,   # afgedrukt nummer = index + 1
                "children": []}
    children = [n for n in (_node(c, level + 1, content_start, start_of) for c in item.children) if n]
    if not children:
        return None
    # Indexpagina met dezelfde titel als het hoofdstuk (navigation.indexes): niet dubbel tonen.
    first = children[0]
    if not first["children"] and first["title"].strip().lower() == (item.title or "").strip().lower():
        children = children[1:]
        children = [dict(c, level=c["level"]) for c in children]
        return {"title": item.title, "level": level, "index": first["index"],
                "number": first["number"], "children": children}
    return {"title": item.title, "level": level, "index": children[0]["index"],
            "number": children[0]["number"], "children": children}


def _flatten(nodes, entries):
    for node in nodes:
        if node["level"] <= TOC_LEVEL:
            entries.append(node)
        _flatten(node["children"], entries)


def _roman(n):
    out = ""
    for value, sym in ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out += sym
            n -= value
    return out


def _build_toc(entries):
    """Tekent de inhoudsopgave met reportlab. Geeft (pdf-bytes, [(pagina, rect, entry)]) terug."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    width, height = A4
    margin = 20 * mm
    top, bottom = height - 28 * mm, 22 * mm
    # (lettertype, grootte, kleur, inspringing, ruimte ervoor)
    styles = {
        1: ("Helvetica-Bold", 11, GREEN, 0, 9),
        2: ("Helvetica", 10, (0.13, 0.13, 0.13), 14, 2),
        3: ("Helvetica", 9, (0.35, 0.35, 0.35), 28, 1),
    }

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    links, page_no = [], 0

    def new_page():
        nonlocal page_no
        if page_no:
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawCentredString(width / 2, 12 * mm, _roman(page_no))
            c.showPage()
        page_no += 1
        if page_no == 1:
            c.setFont("Helvetica-Bold", 20)
            c.setFillColorRGB(*GREEN)
            c.drawString(margin, height - 22 * mm, TOC_TITLE)
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(margin, height - 25 * mm, width - margin, height - 25 * mm)
        return top

    y = new_page()
    for entry in entries:
        font, size, color, indent, before = styles.get(entry["level"], styles[3])
        line = size * 1.5
        if y - before - line < bottom:
            y = new_page()
        y -= before + line * 0.8

        number = str(entry["number"])
        number_w = stringWidth(number, font, size)
        x = margin + indent
        avail = width - margin - x - number_w - 14
        title = entry["title"]
        while stringWidth(title, font, size) > avail and len(title) > 4:
            title = title[:-2].rstrip() + "…"
        title_w = stringWidth(title, font, size)

        c.setFont(font, size)
        c.setFillColorRGB(*color)
        c.drawString(x, y, title)
        c.drawRightString(width - margin, y, number)
        c.setStrokeColorRGB(0.65, 0.65, 0.65)
        c.setDash(0.4, 2.2)
        c.setLineWidth(0.5)
        c.line(x + title_w + 4, y + 1.5, width - margin - number_w - 4, y + 1.5)
        c.setDash()
        links.append((page_no - 1, (x, y - 3, width - margin, y + size), entry))
        y -= line * 0.2

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, 12 * mm, _roman(page_no))
    c.showPage()
    c.save()
    return buffer.getvalue(), links