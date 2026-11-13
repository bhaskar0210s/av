#!/usr/bin/env python3
"""Makes the small fonts used by the worksheets and writes them into my_name/index.html.

* "AV Kid Digits" redraws only 1 and 4 the way children are taught to write them:
  1 is a standing line with a small slanting start and no foot, and 4 is open at the top
  (a short standing line, a sleeping line, then a long standing line).
  There are two sets, one to sit with Comic Sans MS (Windows and Mac) and one to sit with
  Comic Neue (phones and tablets that have no Comic Sans), each in regular and bold.
* "AV Cells" has empty glyphs that are exactly one square wide. The square-ruled sheet lays
  its text out with it, so every letter or number gets its own square.

Run:  python3 tools/make_fonts.py      (needs: pip install fonttools brotli)
"""
import base64
import io
import math
import re
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.timeTools import timestampFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen

PAGE = Path(__file__).resolve().parent.parent / "my_name" / "index.html"

# Measured from the fonts they sit beside (units of 2048 to the em):
#   height: top of the digits; stroke: width of a standing line; one, four: how much room "1" and
#   "4" take; four_ink: how wide the font's own 4 is drawn.
DIGIT_STYLES = {
    "kidSans400": dict(height=1555, stroke=196, one=922, four=1250, four_ink=1141),  # Comic Sans MS
    "kidSans700": dict(height=1555, stroke=270, one=1250, four=1250, four_ink=1222),  # Comic Sans MS Bold
    "kidNeue400": dict(height=1386, stroke=129, one=811, four=991, four_ink=815),    # Comic Neue
    "kidNeue700": dict(height=1352, stroke=198, one=805, four=961, four_ink=832),    # Comic Neue Bold
}
UPM = 2048


def capsule(pen, start, end, radius):
    """A straight stroke with round ends, drawn clockwise (TrueType outer contour)."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    angle = math.atan2(uy, ux)
    points = []  # (x, y, on_curve)

    def arc(cx, cy, from_angle):
        # Half circle in four 45° quadratic pieces, turning clockwise.
        for step in range(4):
            a0 = from_angle - step * math.pi / 4
            a1 = a0 - math.pi / 4
            mid = (a0 + a1) / 2
            reach = radius / math.cos(math.pi / 8)
            points.append((cx + reach * math.cos(mid), cy + reach * math.sin(mid), False))
            points.append((cx + radius * math.cos(a1), cy + radius * math.sin(a1), True))

    # Left side of the stroke, round end at `end`, right side back, round end at `start`.
    points.append((x0 + radius * math.cos(angle + math.pi / 2), y0 + radius * math.sin(angle + math.pi / 2), True))
    points.append((x1 + radius * math.cos(angle + math.pi / 2), y1 + radius * math.sin(angle + math.pi / 2), True))
    arc(x1, y1, angle + math.pi / 2)
    points.append((x0 + radius * math.cos(angle - math.pi / 2), y0 + radius * math.sin(angle - math.pi / 2), True))
    arc(x0, y0, angle - math.pi / 2)
    points.pop()  # the last arc ends where the contour started

    rounded = [(round(x), round(y), on) for x, y, on in points]
    pen.moveTo(rounded[0][:2])
    pending = []
    for x, y, on in rounded[1:]:
        if on:
            if pending:
                pen.qCurveTo(*pending, (x, y))
                pending = []
            else:
                pen.lineTo((x, y))
        else:
            pending.append((x, y))
    if pending:
        pen.qCurveTo(*pending, rounded[0][:2])
    pen.closePath()


def strokes_glyph(strokes, stroke_width):
    pen = TTGlyphPen(None)
    for polyline in strokes:
        for start, end in zip(polyline, polyline[1:]):
            capsule(pen, start, end, stroke_width / 2)
    glyph = pen.glyph()
    glyph.flags[0] |= 0x40  # OVERLAP_SIMPLE: the strokes overlap on purpose
    return glyph


def digit_shapes(height, stroke, one, four, four_ink):
    r = stroke / 2
    top, bottom = height - r, r
    # 1: a small slanting line into a standing line, no foot.
    flag_dx, flag_dy = 0.23 * height, 0.19 * height
    ink = flag_dx + stroke
    stem = (one - ink) / 2 + r + flag_dx
    one_strokes = [[(stem - flag_dx, top - flag_dy), (stem, top), (stem, bottom)]]
    # 4: short standing line, sleeping line, then a long standing line through it.
    # The open top is a little under three times as wide as the bit of sleeping line past the long line.
    span = four_ink - stroke
    gap, past, bar = span * 45 / 61, span * 16 / 61, 0.40 * height
    left = (four - four_ink) / 2 + r
    long_line = left + gap
    four_strokes = [
        [(left, top), (left, bar), (long_line + past, bar)],
        [(long_line, top), (long_line, bottom)],
    ]
    return {"one": (one, one_strokes), "four": (four, four_strokes)}


def notdef_box(width, height):
    pen = TTGlyphPen(None)
    inset = width // 10
    outer = [(inset, 0), (inset, height), (width - inset, height), (width - inset, 0)]
    inner = [(2 * inset, inset), (width - 2 * inset, inset), (width - 2 * inset, height - inset), (2 * inset, height - inset)]
    for contour in (outer, inner):
        pen.moveTo(contour[0])
        for point in contour[1:]:
            pen.lineTo(point)
        pen.closePath()
    return pen.glyph()


def to_woff2(fb):
    # Fixed dates, so running this again gives the same bytes.
    fb.font.recalcTimestamp = False
    fb.font["head"].created = fb.font["head"].modified = timestampFromString("Fri Nov 13 00:00:00 2026")
    fb.font.flavor = "woff2"
    buffer = io.BytesIO()
    fb.font.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def finish(fb, family, ascent, descent, weight=400):
    # The bold fonts must say they are bold, or browsers thicken them a second time.
    bold = weight >= 600
    style = "Bold" if bold else "Regular"
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent, lineGap=0)
    fb.setupNameTable({"familyName": family, "styleName": style, "uniqueFontIdentifier": f"{family} {style}",
                       "fullName": f"{family} {style}", "psName": f"{family.replace(' ', '')}-{style}",
                       "version": "Version 1.000"})
    fb.setupOS2(version=4, usWeightClass=weight, sTypoAscender=ascent, sTypoDescender=-descent, sTypoLineGap=0,
                usWinAscent=ascent, usWinDescent=descent, fsSelection=(0x20 if bold else 0x40) | 0x80, achVendID="NONE")
    fb.font["head"].macStyle = 1 if bold else 0
    fb.setupPost()


def kid_digits(name, style):
    shapes = digit_shapes(**style)
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder([".notdef", "one", "four"])
    fb.setupCharacterMap({0x31: "one", 0x34: "four"})
    glyphs = {".notdef": notdef_box(style["one"], style["height"])}
    metrics = {".notdef": (style["one"], 0)}
    for glyph_name, (advance, strokes) in shapes.items():
        glyphs[glyph_name] = strokes_glyph(strokes, style["stroke"])
        metrics[glyph_name] = (advance, 0)
    fb.setupGlyf(glyphs)
    for glyph_name, glyph in glyphs.items():
        glyph.recalcBounds(fb.font["glyf"])
        metrics[glyph_name] = (metrics[glyph_name][0], getattr(glyph, "xMin", 0))
    fb.setupHorizontalMetrics(metrics)
    finish(fb, "AV Kid Digits", 2257, 597, weight=int(name[-3:]))
    return to_woff2(fb)


# Letters, numbers and signs that get one square each on the square-ruled sheet.
CELL_CHARACTERS = (
    list(range(0x20, 0x7F))           # English letters, numbers, + - = < > ( ) and the rest
    + list(range(0xA0, 0x100))        # × ÷ ½ and accented letters
    + list(range(0x2010, 0x2028))     # dashes and curly quotes
    + [0x2212, 0x2215, 0x2219, 0x221A, 0x2260, 0x2264, 0x2265, 0x2190, 0x2191, 0x2192, 0x2193, 0x25CB, 0x25A1]
)


def cells_font():
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "cell"])
    fb.setupCharacterMap({code: "cell" for code in CELL_CHARACTERS})
    fb.setupGlyf({".notdef": notdef_box(1000, 700), "cell": TTGlyphPen(None).glyph()})
    fb.setupHorizontalMetrics({".notdef": (1000, 100), "cell": (1000, 0)})
    finish(fb, "AV Cells", 800, 200)
    return to_woff2(fb)


def main():
    data = {name: kid_digits(name, style) for name, style in DIGIT_STYLES.items()}
    data["cells"] = cells_font()
    lines = ["const FONT_DATA = {"]
    lines += [f"  {name}: '{value}'," for name, value in data.items()]
    lines.append("};")
    block = "\n".join(lines)
    page = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(r"(/\* fonts:start[^\n]*\*/\n)(?:.*?\n)?(/\* fonts:end \*/)", re.S)
    if not pattern.search(page):
        sys.exit(f"No /* fonts:start */ ... /* fonts:end */ block in {PAGE}")
    page = pattern.sub(lambda m: m.group(1) + block + "\n" + m.group(2), page, count=1)
    PAGE.write_text(page, encoding="utf-8")
    sizes = ", ".join(f"{name} {len(value) * 3 // 4} bytes" for name, value in data.items())
    print(f"Wrote fonts into {PAGE.relative_to(PAGE.parent.parent)} ({sizes})")


if __name__ == "__main__":
    main()
