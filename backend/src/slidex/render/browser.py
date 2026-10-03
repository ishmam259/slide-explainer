"""Headless Chromium (Playwright) for KaTeX math and PDF printing (research.md R11)."""

from __future__ import annotations

import base64
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import TypeVar

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from slidex.core.errors import SlidexError

T = TypeVar("T")
ASSETS = Path(__file__).parent / "assets" / "katex"


@cache
def katex_css_inline() -> str:
    """KaTeX CSS with fonts embedded as data URIs, so HTML output works offline."""
    css = (ASSETS / "katex.min.css").read_text(encoding="utf-8")
    for font in (ASSETS / "fonts").glob("*.woff2"):
        data = base64.b64encode(font.read_bytes()).decode("ascii")
        css = css.replace(f"fonts/{font.name}", f"data:font/woff2;base64,{data}")
    return css


@cache
def katex_js() -> str:
    return (
        (ASSETS / "katex.min.js").read_text(encoding="utf-8")
        + "\n"
        + (ASSETS / "auto-render.min.js").read_text(encoding="utf-8")
    )


RENDER_MATH_JS = """
() => {
  renderMathInElement(document.body, {
    delimiters: [
      {left: '$$', right: '$$', display: true},
      {left: '\\\\[', right: '\\\\]', display: true},
      {left: '$', right: '$', display: false},
      {left: '\\\\(', right: '\\\\)', display: false}
    ],
    ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    throwOnError: false
  });
  document.querySelectorAll('[data-latex]').forEach(el => {
    katex.render(el.getAttribute('data-latex'), el, {displayMode: true, throwOnError: false});
  });
  return true;
}
"""


def with_page[T](fn: Callable[[Page], T]) -> T:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                return fn(page)
            finally:
                browser.close()
    except PlaywrightError as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            raise SlidexError(
                "renderer_missing",
                "Chromium is not installed. Run: cd backend; uv run playwright install chromium",
            ) from exc
        raise


def load_with_math(page: Page, html: str) -> None:
    page.set_content(html, wait_until="load")
    page.add_script_tag(content=katex_js())
    page.evaluate(RENDER_MATH_JS)
