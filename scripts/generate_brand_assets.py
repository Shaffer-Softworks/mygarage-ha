#!/usr/bin/env python3
"""Generate HA brand PNGs from the official MyGarage Logo.tsx lockup."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = REPO_ROOT / "custom_components" / "mygarage" / "brand"

# Default accent palette (src/index.css :root + html.light text)
ACCENT = "#4f8cff"
ACCENT_SOFT = "rgba(79, 140, 255, 0.15)"
TEXT_LIGHT = "#0f172a"
TEXT_DARK = "#e8eaed"

CAR_PATHS = """
  <path d="M3 13l2-5a3 3 0 0 1 3-2h8a3 3 0 0 1 3 2l2 5" />
  <path d="M3 13h18v4a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-1H7v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
  <circle cx="7.5" cy="15.5" r="1" />
  <circle cx="16.5" cy="15.5" r="1" />
"""


def _car_group(scale: float, cx: float, cy: float, stroke: str) -> str:
    return f"""
    <g transform="translate({cx} {cy}) scale({scale}) translate(-12 -12)"
       fill="none" stroke="{stroke}" stroke-width="1.7"
       stroke-linecap="round" stroke-linejoin="round">
      {CAR_PATHS}
    </g>
    """


def icon_svg(size: int, *, dark: bool) -> str:
    """Square mark: rounded accent-soft tile + car outline."""
    tile = size * 0.72
    x = (size - tile) / 2
    radius = tile * 0.3  # 9/30 from Logo.tsx
    car_scale = (tile * (19 / 30)) / 24
    cx = size / 2
    cy = size / 2
    bg = ACCENT_SOFT if not dark else "rgba(79, 140, 255, 0.22)"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect x="{x}" y="{x}" width="{tile}" height="{tile}" rx="{radius}" fill="{bg}"/>
  {_car_group(car_scale, cx, cy, ACCENT)}
</svg>"""


def logo_svg(height: int, *, dark: bool) -> str:
    """Horizontal lockup matching Logo.tsx proportions."""
    text_color = TEXT_DARK if dark else TEXT_LIGHT
    tile = height * 0.88
    gap = tile * (10 / 30)
    radius = tile * 0.3
    car_scale = (tile * (19 / 30)) / 24
    font_size = tile * (15.5 / 30)
    text_y = height / 2 + font_size * 0.36
    text_x = tile + gap
    # Approximate width for "MyGarage" bold at this size
    width = int(text_x + font_size * 5.6)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="0" y="{(height - tile) / 2}" width="{tile}" height="{tile}" rx="{radius}" fill="{ACCENT_SOFT if not dark else 'rgba(79, 140, 255, 0.22)'}"/>
  {_car_group(car_scale, tile / 2, height / 2, ACCENT)}
  <text x="{text_x}" y="{text_y}" font-family="Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="{font_size}" font-weight="700" letter-spacing="-0.01em">
    <tspan fill="{ACCENT}">My</tspan><tspan fill="{text_color}">Garage</tspan>
  </text>
</svg>"""


def render_svg_playwright(svg: str, dest: Path) -> None:
    from playwright.sync_api import sync_playwright

    # Parse dimensions from the SVG root width/height attributes.
    import re

    match = re.search(r'width="(\d+)" height="(\d+)"', svg)
    if not match:
        raise RuntimeError("Could not parse SVG dimensions")
    width, height = int(match.group(1)), int(match.group(2))
    html = f"""<!DOCTYPE html><html><body style="margin:0;background:transparent">
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{re.search(r'viewBox=\"([^\"]+)\"', svg).group(1)}">
{svg.split('>', 1)[1].rsplit('</svg>', 1)[0]}
</svg></body></html>"""
    # Simpler: embed full svg
    html = f"""<!DOCTYPE html><html><body style="margin:0;background:transparent">{svg}</body></html>"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page.set_content(html)
        page.locator("svg").screenshot(path=str(dest), omit_background=True)
        browser.close()


def render_svg(svg: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tmp:
        tmp.write(svg)
        tmp_path = Path(tmp.name)
    try:
        for cmd in (
            ["rsvg-convert", "-o", str(dest), str(tmp_path)],
            ["magick", "-background", "none", str(tmp_path), str(dest)],
            [sys.executable, "-m", "cairosvg", str(tmp_path), "-o", str(dest)],
        ):
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        render_svg_playwright(svg, dest)
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> int:
    specs = [
        ("icon.png", icon_svg(256, dark=False)),
        ("icon@2x.png", icon_svg(512, dark=False)),
        ("dark_icon.png", icon_svg(256, dark=True)),
        ("dark_icon@2x.png", icon_svg(512, dark=True)),
        ("logo.png", logo_svg(256, dark=False)),
        ("logo@2x.png", logo_svg(512, dark=False)),
        ("dark_logo.png", logo_svg(256, dark=True)),
        ("dark_logo@2x.png", logo_svg(512, dark=True)),
    ]
    for name, svg in specs:
        dest = BRAND_DIR / name
        render_svg(svg, dest)
        print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
