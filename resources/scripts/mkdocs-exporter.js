/**
 * Wordt ALLEEN in de PDF-render geïnjecteerd (exporter -> formats -> pdf -> scripts).
 *
 * Waarom: mkdocs-exporter laadt de pagina in Chromium en laat Paged.js direct daarna de
 * pagina's opdelen. Paged.js werkt op een kopie van de DOM. Een Mermaid-diagram dat pas
 * daarna (asynchroon) wordt getekend, ontbreekt dus in de PDF. Paged.js wacht wél op
 * window.MkDocsExporter.render() voordat het begint; hier zorgen we dat alle diagrammen
 * klaar zijn.
 */
window.MkDocsExporter = {
  render: async () => {
    const SELECTOR = '.mermaid, .mermaid-zoom';
    const GRACE_MS = 4000;    // tijd voor je eigen mermaid-zoom.js om zelf te tekenen
    const POLL_MS = 150;
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    const sources = () => [...document.querySelectorAll(SELECTOR)];

    // Een diagram geldt als getekend als er een <svg> in zit, Mermaid het als verwerkt heeft
    // gemarkeerd, of een direct naastgelegen element de <svg> bevat (andere zoom-wrappers).
    const isRendered = (el) =>
      !!el.querySelector('svg') ||
      el.getAttribute('data-processed') === 'true' ||
      !!(el.nextElementSibling && el.nextElementSibling.querySelector('svg')) ||
      !!(el.previousElementSibling && el.previousElementSibling.querySelector('svg'));

    const pending = () => sources().filter((el) => !isRendered(el));

    const total = sources().length;
    if (total === 0) return;

    // 1. Geef bestaande scripts (mermaid-zoom.js) de tijd om zelf te tekenen.
    const start = Date.now();
    while (pending().length > 0 && Date.now() - start < GRACE_MS) {
      await sleep(POLL_MS);
    }

    // 2. Wat nog niet getekend is, tekenen we zelf.
    let todo = pending();
    if (todo.length > 0) {
      if (!window.mermaid) {
        console.error(`[mkdocs-exporter] ${todo.length}/${total} Mermaid-diagram(men) niet getekend: window.mermaid ontbreekt (script niet geladen?)`);
      } else {
        try {
          window.mermaid.initialize({ startOnLoad: false });
          await window.mermaid.run({ nodes: todo, suppressErrors: true });
        } catch (error) {
          console.error('[mkdocs-exporter] Mermaid render mislukt:', error);
        }
      }
    }

    // 3. Fonts en layout laten settelen, zodat Paged.js de echte afmetingen ziet.
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
    await sleep(300);

    todo = pending();
    if (todo.length > 0) {
      console.error(`[mkdocs-exporter] ${todo.length}/${total} Mermaid-diagram(men) ontbreken nog in de PDF`);
    } else {
      console.info(`[mkdocs-exporter] ${total} Mermaid-diagram(men) getekend`);
    }
  }
};