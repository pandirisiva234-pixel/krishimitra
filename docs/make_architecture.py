"""Draw docs/architecture.svg (layered system architecture of KrishiMitra).

    python docs/make_architecture.py                     # writes docs/architecture.svg
    rsvg-convert -z 2 docs/architecture.svg -o docs/architecture.png   # optional PNG (Linux/macOS)

Plain SVG, so it opens in any browser and can be inserted into Word/PowerPoint.
"""
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1600, 1110
GREEN, GREEN_D, GOLD, GOLD_L = "#1f5c3a", "#164429", "#c48a12", "#fff4d6"
MINT, MINT_D, INK, MUTED = "#eef6f0", "#d9ebdf", "#1d2b23", "#55615a"
BLUE, BLUE_L, GREY, GREY_L = "#4c5d8a", "#e9edf7", "#7b847f", "#f1f2f1"
FONT = "DejaVu Sans, Segoe UI, Arial, sans-serif"

out: list[str] = []


def text(x, y, s, size=14, weight="normal", color=INK, anchor="middle"):
    out.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
               f'fill="{color}" text-anchor="{anchor}">{escape(s)}</text>')


def box(x, y, w, h, title, lines=(), fill=MINT, stroke=GREEN, title_color=INK, r=12, size=15):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" '
               f'stroke-width="1.6"/>')
    n = len(lines)
    top = y + h / 2 - (n * 16) / 2 + (4 if n else 6)
    text(x + w / 2, top, title, size, "bold", title_color)
    for i, ln in enumerate(lines):
        text(x + w / 2, top + 19 + i * 16, ln, 12, color=MUTED if title_color == INK else "#e8f1eb")


def band(x, y, w, h, label, sub="", fill="#f7faf8", stroke=GREEN, dashed=False):
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" '
               f'stroke-width="1.4"{dash}/>')
    text(x + 18, y + 26, label, 16, "bold", stroke, "start")
    if sub:
        text(x + 18 + len(label) * 10 + 14, y + 26, sub, 12.5, color=MUTED, anchor="start")


def arrow(x1, y1, x2, y2, color=GREEN, dashed=False, width=1.8, label=None):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash} '
               f'marker-end="url(#arrow-{color[1:]})"/>')
    if label:
        text((x1 + x2) / 2 + 14, (y1 + y2) / 2 + 4, label, 11.5, color=MUTED, anchor="start")


def markers():
    defs = ["<defs>"]
    for c in (GREEN, GOLD, BLUE, GREY):
        defs.append(f'<marker id="arrow-{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                    f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    defs.append("</defs>")
    out.extend(defs)


def build():
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    markers()
    out.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    text(40, 48, "KrishiMitra — System Architecture", 28, "bold", GREEN_D, "start")
    text(40, 74, "Multilingual voice farming assistant with camera-based plant disease detection", 15,
         color=MUTED, anchor="start")

    L, R = 40, 1250  # main column; external services to the right of R

    # 1. Users
    band(L, 100, R - L, 100, "Users", dashed=True, stroke=GOLD, fill="#fffdf6")
    box(330, 128, 260, 58, "Farmer", ["voice · text · camera · GPS"], GOLD_L, GOLD)
    box(700, 128, 260, 58, "Admin", ["users · knowledge documents"], GOLD_L, GOLD)

    # 2. Frontend
    band(L, 225, R - L, 125, "Presentation layer", "React 19 + Vite · light / dark theme · 10 languages")
    pages = [("Voice assistant", "mic · speech player"), ("Disease detection", "leaf photo"),
             ("Farm item scanner", "bottle / packet"), ("Weather", "current location"),
             ("Knowledge & History", "search · past chats"), ("Admin panel", "users · documents")]
    pw, gap = 182, 14
    for i, (t, s) in enumerate(pages):
        box(L + 20 + i * (pw + gap), 262, pw, 70, t, [s], "white", GREEN, size=14)

    # 3. API
    band(L, 375, R - L, 95, "API layer", "FastAPI")
    box(L + 20, 410, R - L - 40, 46, "REST API  ·  JWT login  ·  rate limiting  ·  input validation  ·  "
        "/auth  /assistant  /disease  /items  /weather  /knowledge  /admin", fill=GREEN, stroke=GREEN,
        title_color="white", size=14)

    # 4. AI services
    band(L, 495, R - L, 420, "AI services layer", "Python · runs on the laptop CPU (int8 models)")
    text(L + 20, 548, "Voice question pipeline", 14, "bold", GREEN, "start")
    steps = [("1 · Speech to text", ["Whisper (language ID)", "IIT Madras te / kn"]),
             ("2 · To English", ["AI4Bharat IndicTrans2", "+ farm glossary"]),
             ("3 · Intent", ["TF-IDF classifier", "+ keywords"]),
             ("4 · Retrieve (RAG)", ["MiniLM → ChromaDB", "FlashRank · crop-aware"]),
             ("5 · Answer", ["Gemini, cited [1]", "problem · cure · prevent"]),
             ("6 · Translate back", ["Gemini · backup", "IndicTrans2 → NLLB"]),
             ("7 · Speak", ["Edge-TTS", "gTTS backup"])]
    sw, sg, sy = 152, 17, 562
    for i, (t, ls) in enumerate(steps):
        gem = t.startswith(("5", "6"))
        x = L + 20 + i * (sw + sg)
        box(x, sy, sw, 86, t, ls, GOLD_L if gem else MINT, GOLD if gem else GREEN, size=13.5)
        if i < len(steps) - 1:
            arrow(x + sw + 2, sy + 43, x + sw + sg - 2, sy + 43)

    text(L + 20, 690, "Camera and other services", 14, "bold", GREEN, "start")
    box(L + 20, 704, 250, 86, "Disease detection", ["OpenCV → MobileNetV3-Large", "ONNX · 38 classes · 99.45%"])
    arrow(L + 272, 747, L + 318, 747, GOLD, dashed=True)
    text(L + 276, 735, "unsure", 11, color=MUTED, anchor="start")
    box(L + 320, 704, 220, 86, "AI second opinion", ["Gemini vision", "for unsure photos"], GOLD_L, GOLD)
    box(L + 560, 704, 200, 86, "Farm item scanner", ["Gemini vision: use,", "safety, toxicity"], GOLD_L, GOLD)
    box(L + 780, 704, 200, 86, "Weather advisories", ["forecast + farm rules", "spray · rain · irrigation"])
    box(L + 1000, 704, 190, 86, "Document ingestion", ["PDF → chunks", "→ embeddings"])

    # legend
    out.append(f'<rect x="{L + 20}" y="820" width="22" height="16" rx="4" fill="{GOLD_L}" stroke="{GOLD}"/>')
    text(L + 50, 833, "uses the Gemini API", 12.5, color=MUTED, anchor="start")
    out.append(f'<rect x="{L + 220}" y="820" width="22" height="16" rx="4" fill="{MINT}" stroke="{GREEN}"/>')
    text(L + 250, 833, "runs locally (no internet needed)", 12.5, color=MUTED, anchor="start")
    text(L + 20, 870, "Answers in Telugu, Hindi, Kannada, Tamil, Malayalam, Marathi, Bengali, Gujarati, Urdu and "
         "English. Weather questions go from step 3 to the weather service.", 12.5, color=MUTED, anchor="start")
    text(L + 20, 892, "Translation backups: if Gemini is busy, AI4Bharat IndicTrans2 translates; if that fails, "
         "Meta NLLB-200.", 12.5, color=MUTED, anchor="start")

    # 5. Data
    band(L, 940, R - L, 150, "Data layer", stroke=BLUE, fill="#f7f8fc")
    cyl = [("PostgreSQL", ["users · languages · conversations", "queries · predictions · documents"]),
           ("ChromaDB (vector store)", ["11 government documents", "1,416 text chunks"]),
           ("File storage", ["voice recordings · spoken answers", "leaf photos · PDFs"])]
    cw = 360
    for i, (t, ls) in enumerate(cyl):
        x = L + 30 + i * (cw + 40)
        out.append(f'<path d="M{x},992 a{cw / 2},12 0 0,0 {cw},0 v62 a{cw / 2},12 0 0,1 -{cw},0 z" '
                   f'fill="{BLUE_L}" stroke="{BLUE}" stroke-width="1.6"/>')
        out.append(f'<ellipse cx="{x + cw / 2}" cy="992" rx="{cw / 2}" ry="12" fill="{BLUE_L}" stroke="{BLUE}" '
                   f'stroke-width="1.6"/>')
        text(x + cw / 2, 1024, t, 14.5, "bold", INK)
        for j, ln in enumerate(ls):
            text(x + cw / 2, 1043 + j * 16, ln, 12, color=MUTED)

    # layer arrows (between bands)
    cx = (L + R) / 2
    arrow(cx, 200, cx, 223, GREEN, width=2.4)
    arrow(cx, 350, cx, 373, GREEN, width=2.4, label="HTTPS / JSON")
    arrow(cx, 470, cx, 493, GREEN, width=2.4)
    arrow(cx, 915, cx, 938, BLUE, width=2.4, label="save · read · search")

    # External services column
    ex = R + 30
    band(ex, 100, W - ex - 30, 990, "External", stroke=GREY, fill="#fbfbfb", dashed=True)
    ext = [("Google Gemini API", ["answers · translation", "vision · query check"], GOLD_L, GOLD, 560),
           ("OpenWeather API", ["live weather", "5-day forecast"], GREY_L, GREY, 720),
           ("Microsoft Edge TTS", ["spoken answers"], GREY_L, GREY, 840),
           ("Hugging Face Hub", ["model downloads", "(first run only)"], GREY_L, GREY, 950)]
    for t, ls, f, s, y in ext:
        box(ex + 18, y, W - ex - 66, 78, t, ls, f, s, size=14)
    arrow(R + 2, 605, ex + 16, 599, GOLD, dashed=True, width=2)
    arrow(R + 2, 760, ex + 16, 759, GREY, dashed=True, width=2)
    arrow(R + 2, 879, ex + 16, 879, GREY, dashed=True, width=2)
    out.append("</svg>")


if __name__ == "__main__":
    build()
    path = Path(__file__).with_name("architecture.svg")
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {path}")
