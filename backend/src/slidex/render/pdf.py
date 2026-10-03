"""PDF renderer: the HTML document printed by headless Chromium (A4, page numbers, links)."""

from __future__ import annotations

from playwright.sync_api import Page

from slidex.db.files import FileStore
from slidex.llm.schemas import ExplanationDocumentModel
from slidex.render import register
from slidex.render.browser import load_with_math, with_page
from slidex.render.html import build_html

FOOTER = (
    '<div style="width:100%;font:9px Menlo,monospace;color:#888;padding:0 16mm;'
    'display:flex;justify-content:space-between"><span class="title"></span>'
    '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
)


@register("pdf", "pdf")
def render_pdf(doc: ExplanationDocumentModel, files: FileStore) -> bytes:
    html = build_html(doc, files)

    def run(page: Page) -> bytes:
        load_with_math(page, html)
        page.emulate_media(media="print")
        return page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=FOOTER,
            margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
        )

    return with_page(run)
