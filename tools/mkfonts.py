#!/usr/bin/env python3
"""Subset the three handbook typefaces to woff2 and emit assets/fonts.css
with @font-face blocks carrying base64 data: URIs (the Artifact CSP blocks
external font hosts, so everything must travel inside the page).

Typefaces
---------
URW Gothic  (Avant Garde Gothic clone) -> display / headings / eyebrows
P052        (Palatino clone)           -> body prose
Adwaita Mono(Iosevka fork)             -> code, terminal, data plates, ASCII art
"""
import base64
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
TMP = ROOT / ".fontcache"
OUT.mkdir(exist_ok=True)
TMP.mkdir(exist_ok=True)

GS = "/usr/share/fonts/gsfonts"
ADW = "/usr/share/fonts/Adwaita"

# --- character coverage -----------------------------------------------------
# Latin text + typographic punctuation, shared by every face.
TEXT = (
    "U+0020-007E,"          # ASCII
    "U+00A0,U+00A9,U+00AB,U+00BB,U+00B0,U+00B1,U+00B7,U+00BD,U+00BC,U+00BE,"
    "U+00C0-00FF,"          # accented Latin (names: Torvalds, Tanenbaum, Stallman are ASCII, but be safe)
    "U+2010-2015,"          # hyphens & dashes
    "U+2018,U+2019,U+201C,U+201D,U+2020,U+2026,"
    "U+2022,U+2023,U+2039,U+203A,"
    "U+20B9,U+2122,"
    "U+2190-2199,"          # arrows
    "U+21C4,U+21D2,U+21D4,"
    "U+2212,U+2248,U+2260,U+2264,U+2265,U+221E,"
    "U+2713,U+2714,U+2717,U+2718,U+26A0,"
    "U+00D7,U+00F7,"
    "U+25A0,U+25AA,U+25B8,U+25B6,U+25BE,U+25C6,U+25C8,U+25CF,U+25CB,"
    "U+2588,U+2591,U+2592,U+2593,"
    "U+00B6,U+00A7,U+2032,U+2033"
)
# Mono additionally carries the box-drawing set so the PDF's ASCII diagrams
# (and the redrawn ones) line up cell-for-cell.
MONO_EXTRA = ",U+2500-257F,U+2580-259F,U+25E2-25E5,U+0391-03C9"

FACES = [
    # (family, weight, style, source file, unicode range)
    ("HB Display", "400", "normal", f"{GS}/URWGothic-Book.otf", TEXT),
    ("HB Display", "600", "normal", f"{GS}/URWGothic-Demi.otf", TEXT),
    ("HB Display", "400", "italic", f"{GS}/URWGothic-BookOblique.otf", TEXT),
    ("HB Body", "400", "normal", f"{GS}/P052-Roman.otf", TEXT),
    ("HB Body", "700", "normal", f"{GS}/P052-Bold.otf", TEXT),
    ("HB Body", "400", "italic", f"{GS}/P052-Italic.otf", TEXT),
    ("HB Body", "700", "italic", f"{GS}/P052-BoldItalic.otf", TEXT),
    ("HB Mono", "400", "normal", f"{ADW}/AdwaitaMono-Regular.ttf", TEXT + MONO_EXTRA),
    ("HB Mono", "700", "normal", f"{ADW}/AdwaitaMono-Bold.ttf", TEXT + MONO_EXTRA),
    ("HB Mono", "400", "italic", f"{ADW}/AdwaitaMono-Italic.ttf", TEXT + MONO_EXTRA),
]


def subset(src: str, unicodes: str, dest: pathlib.Path) -> None:
    subprocess.run(
        [
            sys.executable, "-m", "fontTools.subset", src,
            f"--unicodes={unicodes}",
            "--layout-features=kern,liga,calt,tnum,onum,frac",
            "--flavor=woff2",
            "--desubroutinize",
            "--no-hinting",
            f"--output-file={dest}",
        ],
        check=True,
        capture_output=True,
    )


def main() -> None:
    blocks = ["/* Typefaces subset from local files and inlined; no network fetch. */"]
    total = 0
    for family, weight, style, src, uni in FACES:
        if not pathlib.Path(src).exists():
            sys.exit(f"missing font source: {src}")
        dest = TMP / (pathlib.Path(src).stem + ".woff2")
        if not dest.exists():
            subset(src, uni, dest)
        raw = dest.read_bytes()
        total += len(raw)
        b64 = base64.b64encode(raw).decode()
        blocks.append(
            "@font-face{"
            f"font-family:'{family}';font-style:{style};font-weight:{weight};"
            "font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')" "}"
        )
        print(f"  {pathlib.Path(src).name:34s} {len(raw)/1024:7.1f} KB  -> {family} {weight} {style}")
    (OUT / "fonts.css").write_text("\n".join(blocks) + "\n")
    print(f"\ntotal woff2 {total/1024:.1f} KB  ->  fonts.css {(OUT/'fonts.css').stat().st_size/1024:.1f} KB (base64)")


if __name__ == "__main__":
    main()
