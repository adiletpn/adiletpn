#!/usr/bin/env python3
"""Draw the profile's animated SVGs, in a dark and a light version.

    python3 scripts/generate.py

Reads data/repos.json (refreshed weekly by .github/workflows/galaxy.yml),
the logos in scripts/logos and the subset fonts in scripts/fonts, and writes
assets/*-dark.svg and assets/*-light.svg. Standard library only.

Every SVG is shown through <img>, so there is no JS and no external font:
fonts are embedded as base64 woff2, and all motion is CSS or SMIL. Such an
image is repainted as a whole on every frame, so star fields are drifting
<pattern> tiles rather than hundreds of animated dots, and nothing is blurred.
"""
import base64
import json
import math
import random
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS, LOGOS, ASSETS = ROOT / "scripts/fonts", ROOT / "scripts/logos", ROOT / "assets"
REPOS = ROOT / "data/repos.json"
NOW = datetime.now(timezone.utc)

# what the hero says, and which repos are not projects
NAME = ("Adilet", "Zholdasbek")
ROLE = "Mobile, backend and AI/ML engineer"
MOTTO = "Making the impossible possible"
PLACE = "Taraz, Kazakhstan"
TELEGRAM, EMAIL = "@lladill", "877555666zzz@gmail.com"
EXCLUDE = {"adiletpn", "github-achievements-lab"}
STACK = [("python", "Python"), ("flutter", "Flutter"), ("dart", "Dart"), ("ts", "TypeScript"),
         ("nestjs", "NestJS"), ("firebase", "Firebase"), ("postgres", "PostgreSQL"),
         ("c", "C"), ("cpp", "C++"), ("git", "Git")]

TILT = -14  # the signature: every orbit in every image leans -14 degrees

THEMES = {
    "dark": dict(
        bg=("#09090B", "#141417"), ink="#FFFFFF", t1="#FAFAFA", t2="#C4C4C4", t3="#8F8F94",
        line=0.14, surface="#1C1C20", horizon="#050506", hole="#000000",
        planets={"a": ("#FFFFFF", "#D4D4D4", "#404040"), "b": ("#F5F5F5", "#B0B0B0", "#3A3A3A"),
                 "c": ("#D4D4D4", "#7A7A7A", "#2A2A2A")},
        halo=0.45, haze=0.16, ring=0.30, logo="light"),
    "light": dict(
        bg=("#FAFAFA", "#EEEEF1"), ink="#111114", t1="#111114", t2="#45454D", t3="#6E6E78",
        line=0.12, surface="#FFFFFF", horizon="#E6E6EA", hole="#09090B",
        planets={"a": ("#9A9AA2", "#3F3F46", "#09090B"), "b": ("#B4B4BA", "#6B6B73", "#2A2A30"),
                 "c": ("#D0D0D4", "#9A9AA2", "#55555C")},
        halo=0.22, haze=0.07, ring=0.34, logo="dark"),
}

SANS = "SG, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "JBM, ui-monospace, SFMono-Regular, Menlo, monospace"


def fonts(*faces):
    """@font-face rules for the given ('SG', 600) style pairs, embedded."""
    files = {"SG": "SpaceGrotesk", "JBM": "JetBrainsMono"}
    out = []
    for fam, weight in faces:
        data = base64.b64encode((FONTS / f"{files[fam]}-{weight}.woff2").read_bytes()).decode()
        out.append(f"@font-face {{ font-family: {fam}; font-weight: {weight}; "
                   f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    return "\n    ".join(out)


def head(th, W, H, rx):
    """Shared <defs>: background, trail and card clip."""
    return (f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{th["bg"][0]}"/>'
            f'<stop offset="1" stop-color="{th["bg"][1]}"/></linearGradient>'
            f'<linearGradient id="trail" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="{th["ink"]}"/>'
            f'<stop offset="1" stop-color="{th["ink"]}" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="card"><rect width="{W}" height="{H}" rx="{rx}"/></clipPath>')


def frame(th, W, H, rx):
    return (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{rx}" fill="none" '
            f'stroke="{th["ink"]}" stroke-opacity="{th["line"]}"/>')


def ellipse(rx, ry):
    return f"M {rx} 0 A {rx} {ry} 0 1 1 {-rx} 0 A {rx} {ry} 0 1 1 {rx} 0 Z"


# ---------------------------------------------------------------- living star field
LAYERS = [  # tile w, tile h, stars per tile, radius range, opacity range, seconds per loop
    (230, 190, 18, (0.4, 0.7), (0.35, 0.7), 240),
    (350, 270, 12, (0.6, 1.1), (0.5, 0.85), 150),
    (510, 390, 7, (1.0, 1.7), (0.7, 1.0), 95),
]


def particles(th, rng, W, H, density=1.0, speed=1.0):
    """Three parallax layers drifting left and down. Each moves by whole tiles,
    so the loop is seamless. Returns (defs, body, css)."""
    defs, body, css = [], [], []
    for i, (tw, tht, n, (r0, r1), (o0, o1), dur) in enumerate(LAYERS):
        dots = "".join(
            f'<circle cx="{rng.uniform(2, tw - 2):.1f}" cy="{rng.uniform(2, tht - 2):.1f}" '
            f'r="{rng.uniform(r0, r1):.2f}" fill="{th["ink"]}" opacity="{rng.uniform(o0, o1):.2f}"/>'
            for _ in range(max(2, round(n * density))))
        defs.append(f'<pattern id="L{i}" width="{tw}" height="{tht}" patternUnits="userSpaceOnUse">{dots}</pattern>')
        layer = (f'<g class="d{i}"><rect x="{-2 * tw}" y="{-tht}" width="{W + 4 * tw}" '
                 f'height="{H + 2 * tht}" fill="url(#L{i})"/></g>')
        body.append(f'<g class="sway">{layer}</g>' if i == 2 else layer)
        css.append(f".d{i} {{ animation: d{i} {dur / speed:.0f}s linear infinite; }} "
                   f"@keyframes d{i} {{ to {{ transform: translate({-2 * tw}px, {tht}px); }} }}")
    css.append(".sway { animation: sway 11s ease-in-out infinite alternate; } "
               "@keyframes sway { to { transform: translateY(-6px); } }")
    return "".join(defs), "\n    ".join(body), "\n    ".join(css)


def twinkles(th, rng, W, H, n, keep):
    out = []
    while len(out) < n:
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        if keep(x, y):
            d = rng.uniform(4, 9)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.choice([0.7, 0.9, 1.1, 1.3])}" '
                       f'fill="{th["ink"]}" class="tw" style="animation-duration:{d:.1f}s;'
                       f'animation-delay:-{rng.uniform(0, d):.1f}s"/>')
    return "\n    ".join(out)


TW_CSS = (".tw { animation: tw 6s ease-in-out infinite; } "
          "@keyframes tw { 0%, 100% { opacity: 0.15; } 50% { opacity: 1; } }")
SHOOT_CSS = (".shoot { opacity: 0; animation: shoot 14s cubic-bezier(.3,0,.7,1) infinite; } "
             "@keyframes shoot { 0% { opacity: 0; transform: translate(0, 0); } 2% { opacity: 0.9; } "
             "10%, 100% { opacity: 0; transform: translate(-260px, 116px); } }")


def shooting(x, y, delay, length=80):
    return (f'<g class="shoot" style="animation-delay:{delay}s"><rect x="{x}" y="{y}" width="{length}" '
            f'height="1.2" rx="0.6" fill="url(#trail)" transform="rotate(-24 {x} {y})"/></g>')


# ---------------------------------------------------------------- hero
def hero(th):
    repos = [r for r in json.loads(REPOS.read_text()) if r["name"] not in EXCLUDE]
    groups = {
        "c/c++": lambda r: r["lang"] in ("C", "C++"),
        "dart": lambda r: r["lang"] == "Dart" or "flutter" in r["name"].lower(),
        "ts/js": lambda r: r["lang"] in ("TypeScript", "JavaScript"),
        "python": lambda r: r["lang"] == "Python",
    }
    rings = {k: [] for k in [*groups, "other"]}
    for r in repos:
        rings[next((k for k, f in groups.items() if f(r)), "other")].append(r)
    biggest = {r["name"] for r in sorted(repos, key=lambda r: -r["kb"])[:3]}

    W, H, cx, cy = 880, 380, 668, 196
    geom = {"c/c++": (58, 40), "dart": (96, 62), "ts/js": (138, 88), "python": (186, 124), "other": (236, 168)}
    rng = random.Random(3)
    ink = th["ink"]

    ring_svg, planet_svg = [], []
    for i, (key, members) in enumerate(rings.items()):
        rx, period = geom[key]
        ring_svg.append(f'<path id="o{i}" d="{ellipse(rx, round(rx * 0.34, 1))}" fill="none" stroke="{ink}" '
                        f'stroke-opacity="{th["ring"] - i * 0.03:.2f}"/>')
        offset = rng.random()
        for j, r in enumerate(sorted(members, key=lambda r: r["name"])):
            size = 2.4 + 4.6 * math.log10(r["kb"] + 10) / math.log10(110000)
            days = (NOW - datetime.fromisoformat(r["pushed"].replace("Z", "+00:00"))).days
            shade = "a" if days < 30 else "b" if days < 100 else "c"
            phase = (offset + j / len(members) + rng.uniform(-0.06, 0.06)) % 1
            ringed = (f'<ellipse rx="{size * 2:.1f}" ry="{size * 0.55:.1f}" fill="none" stroke="{ink}" '
                      f'stroke-opacity="0.55" stroke-width="0.8" transform="rotate(-20)"/>'
                      if r["name"] in biggest else "")
            planet_svg.append(
                f'<g><title>{r["name"]}</title><circle r="{size:.1f}" fill="url(#p{shade})"/>{ringed}'
                f'<animateMotion dur="{period}s" begin="{-phase * period:.1f}s" repeatCount="indefinite">'
                f'<mpath href="#o{i}"/></animateMotion></g>')

    pgrads = "".join(
        f'<radialGradient id="p{k}" cx="0.32" cy="0.3" r="0.85"><stop offset="0" stop-color="{a}"/>'
        f'<stop offset="0.45" stop-color="{b}"/><stop offset="1" stop-color="{c}"/></radialGradient>'
        for k, (a, b, c) in th["planets"].items())
    pdefs, pbody, pcss = particles(th, rng, W, H)
    tw = twinkles(th, rng, W, H, 30, keep=lambda x, y: not (x < 430 and 80 < y < 340))
    nl = "\n      "
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <title>{" ".join(NAME)}: {ROLE.lower()}. {len(repos)} public projects drawn as planets</title>
  <style>
    {fonts(("SG", 400), ("SG", 500), ("SG", 600))}
    {pcss}
    {TW_CSS}
    .haze {{ animation: haze 22s ease-in-out infinite alternate; }}
    @keyframes haze {{ to {{ transform: translate(-22px, 10px); opacity: 0.55; }} }}
    .disk {{ animation: spin 30s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    {SHOOT_CSS}
  </style>
  <defs>
    {head(th, W, H, 20)}
    {pgrads}
    <radialGradient id="halo"><stop offset="0" stop-color="{ink}" stop-opacity="{th["halo"]}"/><stop offset="0.4" stop-color="{ink}" stop-opacity="{th["halo"] / 4:.2f}"/><stop offset="1" stop-color="{ink}" stop-opacity="0"/></radialGradient>
    <radialGradient id="haze"><stop offset="0" stop-color="{ink}" stop-opacity="{th["haze"]}"/><stop offset="1" stop-color="{ink}" stop-opacity="0"/></radialGradient>
    <linearGradient id="disk" x1="0" x2="1"><stop offset="0" stop-color="{ink}"/><stop offset="0.5" stop-color="{ink}" stop-opacity="0.08"/><stop offset="1" stop-color="{ink}" stop-opacity="0.75"/></linearGradient>
    {pdefs}
  </defs>

  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <ellipse class="haze" cx="{cx}" cy="{cy}" rx="300" ry="160" fill="url(#haze)"/>
    {pbody}
    {tw}
    {shooting(600, 36, 2)}
    {shooting(860, 90, 9, 60)}
    <g transform="translate({cx} {cy}) rotate({TILT})">{nl}{nl.join(ring_svg)}
    </g>
    <circle cx="{cx}" cy="{cy}" r="74" fill="url(#halo)"/>
    <g transform="translate({cx} {cy}) rotate({TILT})">
      <g transform="scale(1 0.32)"><g class="disk">
        <circle r="27" fill="none" stroke="url(#disk)" stroke-width="7"/>
        <circle r="35" fill="none" stroke="url(#disk)" stroke-width="1.2" opacity="0.5"/>
      </g></g>
      <circle r="13" fill="{th["hole"]}"/>
      <circle r="13.6" fill="none" stroke="{ink}" stroke-opacity="0.9" stroke-width="1"/>
      <path d="M -27 0 A 27 8.6 0 0 0 27 0" fill="none" stroke="{ink}" stroke-opacity="0.7" stroke-width="2.2"/>{nl}{nl.join(planet_svg)}
    </g>
  </g>
  {frame(th, W, H, 20)}

  <text x="46" y="124" font-family="{SANS}" font-size="58" font-weight="600" fill="{th["t1"]}" letter-spacing="-2">{NAME[0]}</text>
  <text x="46" y="186" font-family="{SANS}" font-size="58" font-weight="600" fill="{th["t1"]}" letter-spacing="-2">{NAME[1]}</text>
  <text x="49" y="232" font-family="{SANS}" font-size="22" font-weight="500" fill="{th["t2"]}">{ROLE}</text>
  <text x="49" y="264" font-family="{SANS}" font-size="22" font-weight="400" fill="{th["t3"]}">{MOTTO}</text>
  <g transform="translate(49 292)">
    <rect width="200" height="40" rx="20" fill="{th["surface"]}" stroke="{ink}" stroke-opacity="{th["line"]}"/>
    <g transform="translate(14 9)" fill="none" stroke="{th["t2"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M11 20s6.5-5.7 6.5-11a6.5 6.5 0 0 0-13 0c0 5.3 6.5 11 6.5 11z"/><circle cx="11" cy="9" r="2.2"/>
    </g>
    <text x="44" y="26" font-family="{SANS}" font-size="16" font-weight="500" fill="{th["t1"]}">{PLACE}</text>
  </g>
</svg>
'''


# ---------------------------------------------------------------- tech stack as a constellation
def logo(th, key):
    """A logo with its brand tile removed and its colours baked to greys,
    so no filter has to run on every frame."""
    def grey(m):
        h = m.group(1)
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        if th["logo"] == "light":
            v = 0.42 * r + 0.84 * g + 0.14 * b + 38
        else:
            v = 225 - 0.85 * (0.3 * r + 0.59 * g + 0.11 * b)
        v = max(0, min(255, round(v)))
        return f"#{v:02X}{v:02X}{v:02X}"

    s = (LOGOS / f"{key}.svg").read_text()
    s = re.sub(r'<rect width="256" height="256"[^>]*/>', "", s, count=1)
    s = re.sub(r'^\s*<svg[^>]*>', "", s.strip(), count=1)
    s = re.sub(r'</svg>\s*$', "", s)
    if th["logo"] == "dark":
        s = s.replace('fill="white"', 'fill="#FFFFFF"')
    s = re.sub(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b(?=["\s);])', grey, s)
    s = re.sub(r'id="([^"]+)"', rf'id="{key}_\1"', s)
    s = re.sub(r'url\(#([^)]+)\)', rf'url(#{key}_\1)', s)
    s = re.sub(r'href="#([^"]+)"', rf'href="#{key}_\1"', s)
    return s.replace('font-weight="700"', 'font-weight="600"')


def stack(th):
    W, H = 880, 232
    rng = random.Random(11)
    ink = th["ink"]
    nodes = [(key, label, 68 + (W - 136) * i / (len(STACK) - 1),
              (88 if i % 2 == 0 else 136) + rng.uniform(-10, 10)) for i, (key, label) in enumerate(STACK)]
    edges = [(i, i + 1) for i in range(len(nodes) - 1)] + [(0, 2), (6, 8)]
    lines = "".join(
        f'<path d="M {nodes[a][2]:.1f} {nodes[a][3]:.1f} L {nodes[b][2]:.1f} {nodes[b][3]:.1f}" '
        f'stroke="{ink}" stroke-opacity="0.2"/>'
        f'<path d="M {nodes[a][2]:.1f} {nodes[a][3]:.1f} L {nodes[b][2]:.1f} {nodes[b][3]:.1f}" class="flow" '
        f'stroke="{ink}" stroke-opacity="0.5" style="animation-delay:-{rng.uniform(0, 14):.1f}s"/>'
        for a, b in edges)
    node_svg = []
    for key, label, x, y in nodes:
        d = rng.uniform(7, 11)
        node_svg.append(
            f'<g transform="translate({x:.1f} {y:.1f})"><g class="bob" style="animation-duration:{d:.1f}s;'
            f'animation-delay:-{rng.uniform(0, d):.1f}s">'
            f'<circle r="31" fill="{th["surface"]}" stroke="{ink}" stroke-opacity="{th["line"]}"/>'
            f'<g transform="scale(0.148) translate(-128 -128)">{logo(th, key)}</g>'
            f'<text y="54" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{th["t3"]}">{label}</text>'
            f'</g></g>')
    pdefs, pbody, pcss = particles(th, rng, W, H, density=0.8, speed=0.8)
    nl = "\n    "
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <title>Tech stack: {", ".join(n[1] for n in nodes)}</title>
  <style>
    {fonts(("JBM", 400))}
    {pcss}
    .bob {{ animation: bob 9s ease-in-out infinite alternate; }}
    @keyframes bob {{ from {{ transform: translateY(-3px); }} to {{ transform: translateY(3px); }} }}
    .flow {{ fill: none; stroke-dasharray: 3 21; animation: flow 14s linear infinite; }}
    @keyframes flow {{ to {{ stroke-dashoffset: -240; }} }}
  </style>
  <defs>
    {head(th, W, H, 20)}
    {pdefs}
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    {pbody}
    <g fill="none">{lines}</g>{nl}{nl.join(node_svg)}
  </g>
  {frame(th, W, H, 20)}
</svg>
'''


# ---------------------------------------------------------------- contact cards, each with its own motif
TG_ICON = '<path d="M21 3 2 10.5l6.5 2.5L18 6l-7.5 8.5L11 21l3.5-4.5L19 20z"/>'
MAIL_ICON = '<rect x="1.5" y="4" width="19" height="15" rx="2.5"/><path d="m2.5 6 8.5 6.5L19.5 6"/>'


def card(th, label, value, icon, seed, motif):
    rng = random.Random(seed)
    W, H = 880, 96
    ink = th["ink"]
    pdefs, pbody, pcss = particles(th, rng, W, H, density=0.6, speed=0.7)
    if motif == "orbit":
        extra = ""
        badge = (f'<g transform="rotate({TILT})"><path id="ring" d="{ellipse(34, 10)}" fill="none" '
                 f'stroke="{ink}" stroke-opacity="0.22"/><circle r="2.4" fill="{th["t1"]}">'
                 f'<animateMotion dur="20s" repeatCount="indefinite"><mpath href="#ring"/></animateMotion></circle></g>')
    else:
        extra = (".wave { transform-box: fill-box; transform-origin: center; animation: wave 6s ease-out infinite; } "
                 "@keyframes wave { from { transform: scale(1); opacity: 0.45; } to { transform: scale(1.75); opacity: 0; } }")
        badge = "".join(f'<circle r="24" fill="none" stroke="{ink}" stroke-width="0.8" class="wave" '
                        f'style="animation-delay:-{d}s"/>' for d in (0, 2, 4))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <title>{label}: {value}</title>
  <style>
    {fonts(("SG", 500), ("JBM", 500))}
    {pcss}
    {extra}
  </style>
  <defs>
    {head(th, W, H, 16)}
    {pdefs}
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    {pbody}
    <g transform="translate(56 48)">{badge}</g>
  </g>
  {frame(th, W, H, 16)}
  <g transform="translate(56 48)">
    <circle r="24" fill="{th["surface"]}" stroke="{ink}" stroke-opacity="{th["line"]}"/>
    <g transform="translate(-11 -11)" fill="none" stroke="{th["t1"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{icon}</g>
  </g>
  <text x="112" y="40" font-family="{SANS}" font-size="16" font-weight="500" fill="{th["t3"]}">{label}</text>
  <text x="112" y="71" font-family="{MONO}" font-size="24" font-weight="500" fill="{th["t1"]}">{value}</text>
  <path d="M836 40l8 8-8 8" fill="none" stroke="{th["t2"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
'''


# ---------------------------------------------------------------- footer: horizon with a slow sunrise
def footer(th):
    rng = random.Random(42)
    W, H = 880, 96
    ink = th["ink"]
    pdefs, pbody, pcss = particles(th, rng, W, H, density=0.8, speed=0.8)
    arc = f"M -40 {H + 60} Q {W / 2} -12 {W + 40} {H + 60}"
    sun = 0.32 if ink == "#FFFFFF" else 0.12
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <style>
    {pcss}
    .rise {{ animation: rise 18s ease-in-out infinite alternate; }}
    @keyframes rise {{ from {{ opacity: 0.35; }} to {{ opacity: 1; }} }}
    .comet {{ animation: comet 36s linear infinite; }}
    @keyframes comet {{ from {{ transform: translate(-80px, 0); }} to {{ transform: translate({W + 80}px, 0); }} }}
  </style>
  <defs>
    {head(th, W, H, 16)}
    <linearGradient id="rim" x1="0" x2="1"><stop offset="0" stop-color="{ink}" stop-opacity="0"/><stop offset="0.5" stop-color="{ink}"/><stop offset="1" stop-color="{ink}" stop-opacity="0"/></linearGradient>
    <radialGradient id="sun" cx="0.5" cy="1" r="0.75"><stop offset="0" stop-color="{ink}" stop-opacity="{sun}"/><stop offset="0.5" stop-color="{ink}" stop-opacity="{sun / 4:.2f}"/><stop offset="1" stop-color="{ink}" stop-opacity="0"/></radialGradient>
    {pdefs}
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    {pbody}
    <g class="comet"><rect x="0" y="26" width="46" height="1.2" rx="0.6" fill="url(#trail)" transform="rotate(4 0 26)"/><circle cx="46" cy="29.2" r="1.4" fill="{ink}"/></g>
    <ellipse class="rise" cx="{W / 2}" cy="{H}" rx="420" ry="70" fill="url(#sun)"/>
    <path d="{arc} Z" fill="{th["horizon"]}"/>
    <path d="{arc}" fill="none" stroke="url(#rim)" stroke-width="6" opacity="0.18" class="rise"/>
    <path d="{arc}" fill="none" stroke="url(#rim)" stroke-width="1"/>
  </g>
  {frame(th, W, H, 16)}
</svg>
'''


# ---------------------------------------------------------------- section icons
def icon_orbit(th):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="4.5" fill="none" stroke="{th["t2"]}" stroke-width="1.5"/>
  <g transform="translate(12 12) rotate({TILT})">
    <path id="r" d="{ellipse(10.5, 3.6)}" fill="none" stroke="{th["t2"]}" stroke-width="1.5"/>
    <circle r="1.8" fill="{th["t1"]}"><animateMotion dur="20s" repeatCount="indefinite"><mpath href="#r"/></animateMotion></circle>
  </g>
</svg>
'''


def icon_signal(th):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="5" cy="17" r="2.6" fill="none" stroke="{th["t2"]}" stroke-width="1.5"/>
  <circle cx="19" cy="7" r="2.6" fill="none" stroke="{th["t2"]}" stroke-width="1.5"/>
  <path id="a" d="M7.3 15.6 Q 9 7.5 16.7 8.4" fill="none" stroke="{th["t2"]}" stroke-width="1.2" stroke-dasharray="1.5 2"/>
  <circle r="1.4" fill="{th["t1"]}"><animateMotion dur="4s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.6;1" calcMode="linear"><mpath href="#a"/></animateMotion>
    <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.1;0.5;0.6;1" dur="4s" repeatCount="indefinite"/></circle>
</svg>
'''


def main():
    ASSETS.mkdir(exist_ok=True)
    for name, th in THEMES.items():
        files = {
            "hero": hero(th),
            "stack": stack(th),
            "telegram": card(th, "Telegram", TELEGRAM, TG_ICON, "tg", "orbit"),
            "email": card(th, "Email", EMAIL, MAIL_ICON, "mail", "waves"),
            "footer": footer(th),
            "icon-orbit": icon_orbit(th),
            "icon-signal": icon_signal(th),
        }
        for key, svg in files.items():
            path = ASSETS / f"{key}-{name}.svg"
            path.write_text(svg)
            print(f"{path.relative_to(ROOT)}  {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
