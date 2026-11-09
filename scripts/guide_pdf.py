#!/usr/bin/env python3
"""Print the methods guide to a PDF for the paper's appendix: `logs/methods-guide.pdf`.

The guide as on screen, laid out by its print stylesheet (`website/src/print.css`): A4, white, a
chapter per page, no controls, every detail box open, one example species throughout. Run `uv run
python scripts/build_site.py` first (or `npm run build --prefix website`), then

uv run --with playwright python scripts/guide_pdf.py [--species avibase-451D6FC8]

Playwright drives the installed Chrome (`channel="chrome"`); it is not a dependency of the repo.
"""

import argparse
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "data" / "output" / "site"
OUT = ROOT / "logs" / "methods-guide.pdf"
SPECIES = "avibase-451D6FC8"  # Red Kite, the guide's default example
SCALE = 0.8  # the page drawn at 80%: body text about 9 pt
CONTENT_WIDTH = 657  # CSS px between the A4 page's 18 mm margins (print.css)
SCROLL_STEPS = 90  # figures are drawn when scrolled into view
SCROLL_PX = 800
SETTLE_MS = 2000
WIDTH_TOLERANCE = 2  # px: a figure drawn narrower than its box by more is a failed print
# Each figure's drawn width against its container's, where they differ
NARROW_PLOTS = f"""() => [...document.querySelectorAll('.js-plotly-plot')].flatMap(d => {{
  const drawn = d.querySelector('.main-svg')?.getBoundingClientRect().width ?? 0;
  const box = d.getBoundingClientRect().width;
  return box - drawn > {WIDTH_TOLERANCE}
    ? [[d.closest('section[id]')?.id, Math.round(drawn), Math.round(box)]] : [];
}})"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(folder: Path) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(QuietHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--species", default=SPECIES, help="taxon_id of the example species")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    if not (SITE / "index.html").exists():
        raise SystemExit(f"No site in {SITE}: run scripts/build_site.py first")

    server = serve(SITE)
    url = f"http://127.0.0.1:{server.server_port}/?species={args.species}"
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        # The window is as wide as the printed text, so the figures are drawn at their print size
        page = browser.new_page(viewport={"width": round(CONTENT_WIDTH / SCALE), "height": 1200})
        page.on("pageerror", lambda e: errors.append(str(e)))
        # The print layout from the start, so every figure is drawn at its printed width
        page.emulate_media(media="print")
        page.goto(url)
        page.wait_for_selector("#symbols", timeout=60000)
        for _ in range(SCROLL_STEPS):
            page.mouse.wheel(0, SCROLL_PX)
            page.wait_for_timeout(100)
        page.evaluate("() => document.querySelectorAll('details').forEach(d => (d.open = true))")
        # Opened boxes and late layout changes: let the responsive figures take their width again
        page.evaluate("() => window.dispatchEvent(new Event('resize'))")
        page.wait_for_timeout(SETTLE_MS)
        narrow = page.evaluate(NARROW_PLOTS)
        if narrow:
            raise SystemExit(f"Figures narrower than their box (section, drawn, box): {narrow}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        page.pdf(path=str(args.out), scale=SCALE, print_background=True, prefer_css_page_size=True)
        browser.close()
    server.shutdown()
    if errors:
        raise SystemExit(f"The page reported errors: {errors[:3]}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
