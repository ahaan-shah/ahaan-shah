#!/usr/bin/env python3
"""Draws the project map and slices it into clickable SVG tiles for README.md.

    python3 -m venv .venv && .venv/bin/pip install fonttools
    .venv/bin/python build/build.py

Also needs rsvg-convert, magick, and two OFL fonts in build/fonts/:
BricolageGrotesque.ttf (variable, github.com/google/fonts) and JetBrainsMono-Medium.ttf.
The brain icon is from Noto Emoji (github.com/googlefonts/noto-emoji).

Everything to edit is in the first section: TAGS, NODES, EDGES, ROWS.
Coordinates are on an 846-unit-wide canvas, GitHub's README column width.
"""
import base64, math, pathlib, subprocess, tempfile
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
W, H = 846, 1462
GH = "https://github.com/ahaan-shah"

# ---------------------------------------------------------------- content
THEMES = {
    "dark": dict(page="#0d1117", name="#ffe0c4", text="#e9e6f2", muted="#98a0c6", line="#3a4373",
                 border="#2d3560", dot="#ffcead", ring="#7d82d9",
                 egui="#8e93ee", pywal="#e9bb4f", go="#8fc4a3", bio="#f0706f", data="#cfa2d6"),
    "light": dict(page="#ffffff", name="#0b2049", text="#131b38", muted="#5a6489", line="#bdc5e2",
                  border="#cfd5ea", dot="#0b2049", ring="#5558c8",
                  egui="#5558c8", pywal="#a87408", go="#3d7f5b", bio="#cc3f43", data="#94558f"),
}
HUB = (423, 190)
TAGS = {  # key: x, y, label, label side
    "egui": (302, 390, "#egui", "b"),
    "pywal": (556, 686, "#pywal", "l"),
    "go": (298, 664, "#bubbletea", "r"),
    "bio": (423, 1168, "#biomedical", "r"),
    "data": (112, 985, "#data-science", "b"),
}
# key: tag, card x, y, width, corner the node sits on, name, line, url
NODES = {
    "opentern":  ("egui", 0, 96, 272, "br", "Opentern", "Market analysis terminal", GH + "/opentern"),
    "spotsie":   ("egui", 584, 124, 262, "bl", "Spotsie", "Native Spotify client", GH + "/spotsie"),
    "magpie":    ("egui", 14, 446, 254, "tr", "Magpie", "Local-first finance", GH + "/magpie"),
    "hyprahaan": ("pywal", 498, 424, 348, "tl", "hyprahaan", "A whole Arch + Hyprland desktop", GH + "/dotfiles"),
    "pear":      ("go", 0, 702, 200, "tr", "pear", "Finance in a TUI", GH + "/pear"),
    "peach":     ("go", 214, 746, 200, "tl", "peach", "Expense splitting", GH + "/peach"),
    "allwrite":  ("pywal", 224, 962, 186, "tl", "allwrite", "Markdown editor", GH + "/allwrite"),
    "docview":   ("pywal", 458, 916, 186, "tl", "docview", "PDF viewer", GH + "/docview"),
    "easycalc":  ("pywal", 666, 946, 180, "tl", "easycalc", "Calculator", GH + "/easycalc"),
    "scanlab":   ("bio", 0, 1226, 292, "tr", "ScanLab", "Interactive 3D scanners", None),
    "wmh":       ("bio", 316, 1284, 244, "tl", "WMH segmentation", "Brain MRI lesions", GH + "/WMH-Segmentation-in-Brain-MRI"),
    "xai":       ("bio", 586, 1212, 260, "tl", "Heart disease XAI", "Do explanations transfer?", GH + "/cross-population-xai-heart-disease"),
}
LOGO_ONLY = {  # key: tag, x, y, name, line, url
    "filefinder": ("pywal", 676, 700, "filefinder", "File manager", None),
}
DOTS = {  # small notes: parent, x, y, label, side
    "gpui": ("filefinder", 742, 790, "gpui fork", "r"),
    "pml": ("data", 48, 916, "practical-ml", "t"),
    "leaflet": ("data", 150, 896, "leaflet atlas", "t"),
    "mpg": ("data", 36, 1052, "mpg predictor", "b"),
    "plotly": ("data", 112, 1080, "plotly deck", "b"),
}
TRUNK = (423, 560)  # where the #pywal branch leaves the trunk
EDGES = [  # a, b, control-point offset (dx, dy) from the midpoint
    ("hub", "bio", (0, 0)), ("hub", "egui", (-4, 8)), ("trunk", "pywal", (-32, 22)),
    ("egui", "opentern", (-30, 14)), ("egui", "spotsie", (10, 34)), ("egui", "magpie", (-6, -8)),
    ("magpie", "pear", (-22, 0)), ("go", "pear", (-10, -12)), ("go", "peach", (4, 12)),
    ("pywal", "hyprahaan", (-14, 0)), ("pywal", "filefinder", (0, -12)), ("pywal", "docview", (24, 0)),
    ("allwrite", "docview", (-16, -38)), ("docview", "easycalc", (0, -44)),
    ("bio", "scanlab", (-10, -18)), ("bio", "wmh", (10, 8)), ("bio", "xai", (14, -40)), ("data", "bio", (-34, 36)),
]
# The slices. Each tile links to one project; None keeps it unlinked to a repo.
REPOS = GH + "?tab=repositories"
ROWS = [
    (0, 90, [(0, 846, "title")]),
    (90, 350, [(0, 284, "opentern"), (284, 570, "hub"), (570, 846, "spotsie")]),
    (350, 634, [(0, 290, "magpie"), (290, 486, "egui"), (486, 846, "hyprahaan")]),
    (634, 868, [(0, 207, "pear"), (207, 432, "peach"), (432, 636, "pywal"), (636, 846, "filefinder")]),
    (868, 1122, [(0, 217, "data"), (217, 434, "allwrite"), (434, 655, "docview"), (655, 846, "easycalc")]),
    (1122, H, [(0, 304, "scanlab"), (304, 573, "wmh"), (573, 846, "xai")]),
]
ASPECT = {"opentern": .6257, "spotsie": .6257, "magpie": .659, "hyprahaan": .5628, "pear": .5217, "peach": .5217,
          "allwrite": .70, "docview": .6722, "easycalc": .8259, "scanlab": .625, "wmh": .6579, "xai": .7147}

# Drawn marks for projects without a logo file (64x64 box).
MARKS = {
    "pear": '<path fill="#a9c466" d="M32 14c7 0 9 6 10 13 1 6 10 10 10 20 0 9-8 13-20 13S12 56 12 47c0-10 9-14 10-20 1-7 3-13 10-13z"/><path fill="none" stroke="#7a5a3c" stroke-width="3.5" stroke-linecap="round" d="M32 15c0-5 2-8 5-10"/><path fill="#5f8f4a" d="M35 9c5-5 11-4 14-2-3 5-9 6-14 2z"/>',
    "peach": '<path fill="#f7a278" d="M32 17c14-6 24 3 24 17 0 15-11 25-24 26C19 59 8 49 8 34c0-14 10-23 24-17z"/><path fill="none" stroke="#d9714c" stroke-width="3" stroke-linecap="round" d="M32 18c-6 8-7 18-3 28"/><path fill="#5f8f4a" d="M33 15c2-8 10-11 18-9-2 8-10 12-18 9z"/>',
    "hyprahaan": '<rect x="4" y="10" width="56" height="44" rx="9" fill="#141b45"/><path fill="#ffcead" d="M18 10h28v5c0 4-3 7-7 7H25c-4 0-7-3-7-7z"/><rect x="18" y="44" width="28" height="5" rx="2.5" fill="#7d82d9"/>',
    "scanlab": '<circle cx="32" cy="32" r="28" fill="#8fb0dd"/><circle cx="32" cy="32" r="19" fill="#22304a"/><circle cx="32" cy="32" r="12.5" fill="#8fb0dd"/><circle cx="32" cy="32" r="6" fill="#22304a"/>',
    "xai": '<path fill="#b8323c" d="M32 57C14 45 6 35 6 23 6 14 13 8 20 8c5 0 9 2 12 7 3-5 7-7 12-7 7 0 14 6 14 15 0 12-8 22-26 34z"/><path fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="M8 32h13l5-10 8 20 6-10h16"/>',
}

# ---------------------------------------------------------------- text as paths
class Face:
    def __init__(self, path, axes=None):
        f = TTFont(path)
        if axes: f = instantiateVariableFont(f, axes)
        self.gs, self.cmap, self.upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    def width(self, s, size, track=0):
        return sum(self.gs[self.cmap[ord(c)]].width for c in s) * size / self.upm + track * len(s)
    def path(self, s, x, y, size, anchor="l", track=0):
        k = size / self.upm
        w = self.width(s, size, track)
        x -= w if anchor == "r" else w / 2 if anchor == "m" else 0
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for c in s:
            g = self.gs[self.cmap[ord(c)]]
            g.draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
            x += g.width * k + track
        return pen.getCommands()

B = HERE / "fonts" / "BricolageGrotesque.ttf"
DISPLAY = Face(B, dict(wght=700, wdth=100, opsz=48))
BOLD = Face(B, dict(wght=650, wdth=100, opsz=20))
BODY = Face(B, dict(wght=430, wdth=100, opsz=14))
MONO = Face(HERE / "fonts" / "JetBrainsMono-Medium.ttf")

ICON, BORDER, GAP, X = 42, 2.5, 3, 4   # icon size, border and cut-out widths, raster scale
def icon(k, color, page):
    """The logo, outlined along its own silhouette in the group colour (needs rsvg-convert and magick)."""
    logo = HERE / "logos" / f"{k}.webp"
    n, full = ICON * X, round((ICON + 2 * (BORDER + GAP)) * X)
    with tempfile.TemporaryDirectory() as d:
        src = logo
        if not logo.exists():
            svg = pathlib.Path(d) / "m.svg"; src = pathlib.Path(d) / "m.png"
            svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{MARKS[k]}</svg>')
            subprocess.run(["rsvg-convert", "-w", "400", svg, "-o", src], check=True)
        out = pathlib.Path(d) / "o.webp"
        # a hard alpha edge drops the drop shadows some app icons carry
        base = ["(", src, "-channel", "A", "-level", "55%,80%", "+channel", "-trim", "+repage", "-resize", f"{n}x{n}",
                "-background", "none", "-gravity", "center", "-extent", f"{full}x{full}", ")"]
        def grow(px, c):
            return ["(", "-clone", "0", "-channel", "A", "-morphology", "Dilate", f"Disk:{px * X:g}", "-blur", "0x0.7", "+channel",
                    "-fill", c, "-colorize", "100", ")"]
        subprocess.run(["magick", *base, *grow(BORDER + GAP - .5, page), *grow(BORDER, color),
                        "(", "-clone", "0", ")", "-delete", "0", "-background", "none", "-layers", "flatten",
                        "-quality", "92", out], check=True)
        return b64(out), full / X

def b64(p): return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()

# ---------------------------------------------------------------- geometry
R = 25
def card(k):
    _, x, y, w, *_ = NODES[k]
    return x, y, w, round(w * ASPECT[k])
def pos(k):
    if k == "hub": return HUB
    if k == "trunk": return TRUNK
    if k in TAGS: return TAGS[k][:2]
    if k in LOGO_ONLY: return LOGO_ONLY[k][1:3]
    if k in DOTS: return DOTS[k][1:3]
    x, y, w, h = card(k); c = NODES[k][4]
    return (x + R + 6 if c[1] == "l" else x + w - R - 6, y - 6 if c[0] == "t" else y + h + 6)

def text(face, s, x, y, size, fill, page, anchor="l", halo=4):
    d = face.path(s, x, y, size, anchor)
    w = face.width(s, size); x0 = x - (w if anchor == "r" else w / 2 if anchor == "m" else 0)
    return ((x0 - 6, y - size * 1.1, x0 + w + 6, y + size * .4),
            f'<path d="{d}" fill="{fill}" stroke="{page}" stroke-width="{halo}" stroke-linejoin="round" paint-order="stroke"/>')

def planet(t):
    """A dotted globe. 32 meridians, so an 11.25 degree turn loops seamlessly."""
    cx, cy = HUB; r, n, frames = 74, 32, 18
    tilt = math.radians(-20); lx, ly, lz = -.5, -.55, .67
    out = []
    for f in range(frames):
        buckets = [[], [], []]
        for li in range(1, 18):
            lat = math.pi * (li / 18 - .5)
            for m in range(n):
                lon = 2 * math.pi * (m + f / frames + (li % 2) * .5) / n
                x, y, z = math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon)
                if z < .06: continue
                X, Y = x * math.cos(tilt) - y * math.sin(tilt), x * math.sin(tilt) + y * math.cos(tilt)
                light = X * lx + Y * ly + z * lz
                buckets[2 if light > .62 else 1 if light > .12 else 0].append(f"M{cx + X*r:.1f} {cy + Y*r:.1f}h0")
        g = "".join(f'<path d="{"".join(p)}" stroke="{c}" stroke-width="{s}" opacity="{o}"/>'
                    for p, s, c, o in zip(buckets, (1.6, 2.5, 3.4), (t["ring"], t["ring"], t["dot"]), (.65, 1, 1)))
        out.append(f'<g class="f" style="animation-delay:{-3 * (frames - f) / frames:.3f}s">{g}</g>')
    tx = f'transform="rotate(-20 {cx} {cy})"'
    rx, ry = 122, 27
    back = f'<path {tx} class="orb" d="M{cx-rx} {cy}A{rx} {ry} 0 0 1 {cx+rx} {cy}" stroke="{t["ring"]}" stroke-width="2.2" stroke-dasharray="0 6.5" opacity=".5"/>'
    front = f'<path {tx} class="orb" d="M{cx+rx} {cy}A{rx} {ry} 0 0 1 {cx-rx} {cy}" stroke="{t["dot"]}" stroke-width="2.8" stroke-dasharray="0 6.5"/>'
    css = (f'.f{{opacity:0;animation:f 3s step-end infinite}}.f:nth-of-type(1){{opacity:1}}'
           f'@keyframes f{{0%{{opacity:1}}{100/frames:.3f}%{{opacity:0}}}}'
           '.orb{animation:o 2.4s linear infinite}@keyframes o{to{stroke-dashoffset:-6.5}}'
           '@media(prefers-reduced-motion:reduce){.f,.orb{animation:none}}')
    return css, f'<g fill="none" stroke-linecap="round">{back}<circle cx="{cx}" cy="{cy}" r="{r+3}" fill="{t["page"]}"/><g>{"".join(out)}</g>{front}</g>'

def scene(theme):
    """Ordered list of (bbox, svg, css) pieces."""
    t = THEMES[theme]; P = []; page = t["page"]
    add = lambda bb, s, css="": P.append((bb, s, css))
    # edges
    for a, b, (dx, dy) in EDGES:
        (x1, y1), (x2, y2) = pos(a), pos(b)
        mx, my = (x1 + x2) / 2 + 2 * dx, (y1 + y2) / 2 + 2 * dy
        xs, ys = (x1, mx, x2), (y1, my, y2)
        add((min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5),
            f'<path d="M{x1:g} {y1:g}Q{mx:g} {my:g} {x2:g} {y2:g}" fill="none" stroke="{t["line"]}" stroke-width="1.4"/>')
    for k, (par, x, y, lab, side) in DOTS.items():
        x1, y1 = pos(par)
        add((min(x, x1) - 5, min(y, y1) - 5, max(x, x1) + 5, max(y, y1) + 5),
            f'<path d="M{x1} {y1}L{x} {y}" stroke="{t["line"]}" stroke-width="1.2"/>')
    css, svg = planet(t)
    add((HUB[0] - 126, HUB[1] - 80, HUB[0] + 126, HUB[1] + 80), svg, css)
    add(*text(DISPLAY, "Ahaan Shah", 423, 46, 50, t["name"], page, "m", 0))
    add(*text(BODY, "Native apps, A beautiful Linux desktop, Biomedical Engineering", 423, 74, 15.5, t["muted"], page, "m", 0))
    # cards
    for k, (tag, _, _, _, corner, name, line, _) in NODES.items():
        x, y, w, h = card(k); cx, cy = pos(k); col = t[tag]
        src = HERE / "src" / f"{k}.webp"
        if not src.exists(): src = HERE / "src" / f"{k}-{theme}.webp"
        add((x, y, x + w, y + h),
            f'<clipPath id="c-{k}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9"/></clipPath>'
            f'<image href="{b64(src)}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" clip-path="url(#c-{k})"/>'
            f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="8.5" fill="none" stroke="{t["border"]}"/>')
    def node(k, cx, cy, col, name, line, right, top):
        uri, w = icon(k, col, page)
        add((cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2),
            f'<image href="{uri}" x="{cx - w / 2}" y="{cy - w / 2}" width="{w}" height="{w}"/>')
        tx = cx + R + 10 if right else cx - R - 10; a = "l" if right else "r"
        y1, y2 = {"t": (cy - 21, cy - 3), "b": (cy + 23, cy + 42), "m": (cy - 2, cy + 17)}[top]
        add(*text(BOLD, name, tx, y1, 20, t["text"], page, a))
        add(*text(BODY, line, tx, y2, 14, t["muted"], page, a))
    for k, (tag, _, _, _, corner, name, line, _) in NODES.items():
        node(k, *pos(k), t[tag], name, line, corner[1] == "l", corner[0])
    for k, (tag, x, y, name, line, _) in LOGO_ONLY.items():
        node(k, x, y, t[tag], name, line, True, "m")
    # tags and small notes
    for k, (x, y, lab, side) in TAGS.items():
        add((x - 14, y - 14, x + 14, y + 14), f'<circle cx="{x}" cy="{y}" r="11" fill="{page}"/><circle class="h" cx="{x}" cy="{y}" r="8" fill="{t[k]}"/>')
        px, py, a = {"r": (x + 18, y + 5, "l"), "l": (x - 18, y + 5, "r"), "b": (x, y + 29, "m")}[side]
        add(*text(MONO, lab, px, py, 14.5, t[k], page, a, 5))
    for k, (par, x, y, lab, side) in DOTS.items():
        col = t["data"] if par == "data" else t["pywal"]
        add((x - 8, y - 8, x + 8, y + 8), f'<circle cx="{x}" cy="{y}" r="4.5" fill="{col}" stroke="{page}" stroke-width="2"/>')
        if lab:
            px, py, a = {"r": (x + 12, y + 5, "l"), "t": (max(x, 48), y - 11, "m"), "b": (max(x, 50), y + 21, "m")}[side]
            add(*text(BODY, lab, px, py, 13.5, t["muted"], page, a))
    return P


def render(P, x0, y0, x1, y1, title):
    hit = [p for p in P if p[0][0] < x1 and p[0][2] > x0 and p[0][1] < y1 and p[0][3] > y0]
    css = "".join(p[2] for p in hit)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {x1-x0} {y1-y0}" width="{x1-x0}" height="{y1-y0}">'
            f'<title>{title}</title><style>{css}</style>' + "".join(p[1] for p in hit) + "</svg>")

LINKS = {"title": (GH, "Ahaan Shah: Native apps, A beautiful Linux desktop, Biomedical Engineering"), "hub": (GH, "The project map"), "egui": (REPOS, "egui apps"), "pywal": (REPOS, "apps that follow pywal"),
         "data": (REPOS, "Data science coursework"), "filefinder": (REPOS, "filefinder, a file manager (private)")}
LINKS |= {k: (v[7] or REPOS, f"{v[5]}: {v[6]}") for k, v in NODES.items()}

def main():
    out = ROOT / "map"; out.mkdir(exist_ok=True)
    scenes = {th: scene(th) for th in THEMES}
    for f in out.glob("*.svg"): f.unlink()
    rows = []
    for y0, y1, tiles in ROWS:
        cells = []
        for x0, x1, k in tiles:
            url, alt = LINKS[k]
            for th, P in scenes.items():
                (out / f"{k}-{th}.svg").write_text(render(P, x0, y0, x1, y1, alt))
            w = math.floor((x1 - x0) / W * 1e6) / 1e4
            cells.append(f'<a href="{url}"><picture><source media="(prefers-color-scheme: dark)" srcset="./map/{k}-dark.svg" />'
                         f'<img src="./map/{k}-light.svg" alt="{alt}" width="{w}%" align="top" /></picture></a>')
        rows.append("".join(cells))
    for th, P in scenes.items():
        (HERE / f"full-{th}.svg").write_text(render(P, 0, 0, W, H, "map"))
    idx = (HERE / "index.md").read_text() if (HERE / "index.md").exists() else ""
    (ROOT / "README.md").write_text("<p>" + "<br />".join(rows) + "</p>\n\n" + idx)
    print(sum(f.stat().st_size for f in out.glob("*-dark.svg")) // 1024, "KB per theme,", len(list(out.glob("*.svg"))), "tiles")

main()
