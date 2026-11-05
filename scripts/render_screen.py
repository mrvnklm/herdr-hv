"""Turn a terminal dump from scripts/demo_screen.py into an SVG (and a PNG with rsvg-convert).

    python3 scripts/render_screen.py /tmp/screen.json /tmp/screen.svg
    rsvg-convert -z 2 /tmp/screen.svg -o docs/screenshot.png

Box-drawing lines are drawn as strokes, not glyphs, so they meet without gaps between rows.
"""
import json
import sys
from xml.sax.saxutils import escape

FONT, SIZE, CELL_W, CELL_H, PAD = "Menlo, DejaVu Sans Mono, monospace", 14, 8.43, 19, 18
FG, BG = "#cdd6f4", "#1e1e2e"
ANSI = {"black": "#45475a", "red": "#f38ba8", "green": "#a6e3a1", "brown": "#f9e2af",
        "blue": "#89b4fa", "magenta": "#f5c2e7", "cyan": "#94e2d5", "white": "#bac2de"}
# up, down, left, right
BOX = {"─": "0011", "│": "1100", "┌": "0101", "┐": "0110", "└": "1001", "┘": "1010",
       "├": "1101", "┤": "1110", "┬": "0111", "┴": "1011", "┼": "1111",
       "╭": "0101", "╮": "0110", "╰": "1001", "╯": "1010"}
BLANK = {"⠀"}


def color(name, default):
    if name == "default":
        return default
    name = name.replace("bfight", "bright")
    if len(name) == 6 and all(c in "0123456789abcdef" for c in name.lower()):
        return "#" + name
    return ANSI.get(name.replace("bright", ""), default)


def render(cells):
    rows, cols = len(cells), len(cells[0])
    width, height = cols * CELL_W + 2 * PAD, rows * CELL_H + 2 * PAD
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'viewBox="0 0 {width:.0f} {height:.0f}">',
           f'<rect width="100%" height="100%" rx="10" fill="{BG}"/>']
    for y, row in enumerate(cells):
        top = PAD + y * CELL_H
        x = 0
        while x < cols:  # background runs
            fg, bg = color(row[x]["fg"], FG), color(row[x]["bg"], BG)
            if row[x]["r"]:
                fg, bg = bg, fg
            end = x
            while end < cols and (color(row[end]["bg"], BG) if not row[end]["r"] else color(row[end]["fg"], FG)) == bg:
                end += 1
            if bg != BG:
                out.append(f'<rect x="{PAD + x * CELL_W:.2f}" y="{top}" width="{(end - x) * CELL_W:.2f}" '
                           f'height="{CELL_H}" fill="{bg}"/>')
            x = end
        x = 0
        while x < cols:  # text runs of one colour and weight; box characters as strokes
            cell = row[x]
            fg = color(cell["bg"], BG) if cell["r"] else color(cell["fg"], FG)
            if cell["c"] in BOX:
                up, down, left, right = (s == "1" for s in BOX[cell["c"]])
                cx, cy = PAD + (x + 0.5) * CELL_W, top + CELL_H / 2
                segments = [(cx, top, cx, cy) if up else None, (cx, cy, cx, top + CELL_H) if down else None,
                            (PAD + x * CELL_W, cy, cx, cy) if left else None,
                            (cx, cy, PAD + (x + 1) * CELL_W, cy) if right else None]
                for s in filter(None, segments):
                    out.append(f'<line x1="{s[0]:.2f}" y1="{s[1]:.2f}" x2="{s[2]:.2f}" y2="{s[3]:.2f}" '
                               f'stroke="{fg}" stroke-width="1.2" stroke-linecap="square"/>')
                x += 1
                continue
            end, text = x, ""
            while end < cols and row[end]["c"] not in BOX and row[end]["b"] == cell["b"] and \
                    (color(row[end]["bg"], BG) if row[end]["r"] else color(row[end]["fg"], FG)) == fg:
                text += " " if row[end]["c"] in BLANK or not row[end]["c"] else row[end]["c"]
                end += 1
            if text.strip():
                weight = ' font-weight="bold"' if cell["b"] else ""
                out.append(f'<text x="{PAD + x * CELL_W:.2f}" y="{top + CELL_H * 0.73:.2f}" fill="{fg}"{weight} '
                           f'textLength="{len(text) * CELL_W:.2f}" lengthAdjust="spacingAndGlyphs" '
                           f'xml:space="preserve">{escape(text)}</text>')
            x = end
    out.insert(1, f'<style>text{{font-family:{FONT};font-size:{SIZE}px}}</style>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    with open(sys.argv[1]) as fh:
        svg = render(json.load(fh))
    with open(sys.argv[2], "w") as fh:
        fh.write(svg + "\n")
