#!/usr/bin/env python3
# THE NEWS - daily PDF + EPUB newspaper generator (prototype v5.5)
# Uso: python3 odiario.py [config.json] [saida.pdf] [saida.epub]
import json, re, html, random, sys, io, os, textwrap, datetime, socket
socket.setdefaulttimeout(5)
import requests, feedparser
import numpy as np, cv2
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from PIL import Image, ImageOps, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "config.json")
OUT_PDF = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "o-diario.pdf")
CFG = json.load(open(CFG_PATH, encoding="utf-8"))

UA = {"User-Agent": "TheNews/1.0 (+https://github.com/AElise08/news-hermes-agent)"}
NOW = datetime.datetime.now()
DOY = NOW.timetuple().tm_yday
random.seed(DOY)

MESES = ["janeiro","fevereiro","marco","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
DIAS = ["segunda-feira","terca-feira","quarta-feira","quinta-feira","sexta-feira","sabado","domingo"]
DATA_PT = f"{DIAS[NOW.weekday()]}, {NOW.day} de {MESES[NOW.month-1]} de {NOW.year}"

# ---------- fontes ----------
FD = "/usr/share/fonts/truetype/dejavu/"
def reg(name, path):
    pdfmetrics.registerFont(TTFont(name, FD + path))
reg("Serif", "DejaVuSerif.ttf"); reg("Serif-Bold", "DejaVuSerif-Bold.ttf")
reg("Serif-Italic", "DejaVuSerif-Italic.ttf"); reg("Serif-BoldItalic", "DejaVuSerif-BoldItalic.ttf")
reg("Sans", "DejaVuSans.ttf"); reg("Sans-Bold", "DejaVuSans-Bold.ttf"); reg("Mono", "DejaVuSansMono.ttf")
# Vogue usa uma Didone de alto contraste; Bodoni Moda (OFL) e a aproximacao livre
VOGUE_PATH = os.path.join(BASE, "BodoniModa.ttf")
VOGUE_FONT = "Serif-Bold"
if os.path.exists(VOGUE_PATH):
    pdfmetrics.registerFont(TTFont("Vogue", VOGUE_PATH))
    VOGUE_FONT = "Vogue"

# ---------- geometria ----------
PAGE_W, PAGE_H = A4
MARGIN = 42
GUTTER = 20
COL_W = (PAGE_W - 2 * MARGIN - GUTTER) / 2.0
TOP = PAGE_H - MARGIN
BOTTOM = MARGIN
HEADER_H = 26  # faixa de continuação nas páginas 2+
BLOCK_GAP = 10

INK = HexColor("#1a1a1a"); GRAY = HexColor("#5a5a5a"); LGRAY = HexColor("#8a8a8a")
PAPER = HexColor("#fbf8f1"); BOXBG = HexColor("#f4eee1"); BOXBG2 = HexColor("#eef3ee")

# ---------- utils texto ----------
CRED = re.compile(r"(?:REUTERS|Reuters|AP Photo|AFP|Alamy|Getty Images|Getty|Reprodução|Dado Ruvic|Illustration|Foto:|Crédito:)(?:/[A-Za-zÀ-ÿ0-9 .&\-]+)?")
def clean_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    # Repair the common case where a feed decoded UTF-8 bytes as Windows-1252.
    if any(marker in s for marker in ("â", "Ã", "Â")):
        try:
            s = s.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    # Normalize broken punctuation sequences left by partially decoded feeds.
    s = re.sub(r"â\s+(?=t\b|s\b|re\b|ve\b|ll\b|d\b|m\b)", "’", s)
    s = re.sub(r"â\s*", "’", s)
    s = re.sub(r"n['’]\s+t\b", "n’t", s)
    s = re.sub(r"['’]\s+(?=s\b|re\b|ve\b|ll\b|d\b|m\b)", "’", s)
    # Drop invalid control characters and replacement runs left by broken feeds.
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", s)
    s = re.sub(r"\ufffd+", "'", s)
    s = CRED.sub(" ", s)
    s = re.sub(r"\bAP\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def trunc(s, n):
    s = s.strip()
    if len(s) <= n: return s
    return s[:n].rsplit(" ", 1)[0].rstrip(".,;:") + "..."

def wrap(text, font, size, width):
    words = []
    for tok in text.split():
        while tok and pdfmetrics.stringWidth(tok, font, size) > width:
            k = len(tok)
            while k > 1 and pdfmetrics.stringWidth(tok[:k], font, size) > width:
                k -= 1
            words.append(tok[:k]); tok = tok[k:]
        if tok: words.append(tok)
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= width:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

BANNED = [re.compile(p, re.I) for p in CFG["banned_patterns"]]
BANNED_MUSIC = [re.compile(p, re.I) for p in CFG.get("banned_music_patterns", [])]
MUSIC_ALLOW = [re.compile(p, re.I) for p in CFG.get("music_allow_patterns", [])]
POSITIVE = [re.compile(p, re.I) for p in CFG["positive_patterns"]]
QUIRKY = [re.compile(p, re.I) for p in CFG.get("quirky_human_interest_patterns", [])]
LOCAL_CITY = [re.compile(p, re.I) for p in CFG.get("local_news_filter", {}).get("city_patterns", [])]
LOCAL_ALLOW = [re.compile(p, re.I) for p in CFG.get("local_news_filter", {}).get("allow_patterns", [])]
def is_banned(text):
    # Keep the default edition focused by excluding generic human-interest and local stories,
    # while retaining locally relevant university coverage.
    if QUIRKY and any(p.search(text) for p in QUIRKY):
        return True
    if LOCAL_CITY and any(p.search(text) for p in LOCAL_CITY):
        if not any(p.search(text) for p in LOCAL_ALLOW):
            return True
    if any(p.search(text) for p in BANNED):
        return True
    if BANNED_MUSIC and any(p.search(text) for p in BANNED_MUSIC):
        if any(p.search(text) for p in MUSIC_ALLOW):
            return False
        return True
    return False
def pos_score(text):
    return sum(1 for p in POSITIVE if p.search(text))

def strip_accents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def ago_str(parsed):
    if not parsed: return ""
    try:
        dt = datetime.datetime(*parsed[:6])
        delta = NOW - dt
        h = int(delta.total_seconds() // 3600)
        if h < 1: return "agora há pouco"
        if h < 24: return f"há {h} h"
        d = h // 24
        return f"há {d} d" if d > 1 else "ontem"
    except Exception:
        return ""

# ---------- coleta ----------
def fetch_feed(spec):
    try:
        d = feedparser.parse(spec["url"])
        items = []
        for e in d.entries[: spec.get("max_items", 5) * 2]:
            title = clean_html(getattr(e, "title", ""))
            summary = "" if spec.get("no_summary") else trunc(clean_html(getattr(e, "summary", getattr(e, "description", ""))), 330)
            alvo = title if spec.get("filter_title_only") else title + " " + summary
            if not title or is_banned(alvo):
                continue
            items.append({
                "title": title, "summary": summary, "source": spec["name"],
                "when": ago_str(getattr(e, "published_parsed", getattr(e, "updated_parsed", None))),
                "url": getattr(e, "link", ""),
                "pos": pos_score(title + " " + summary),
            })
        return items
    except Exception as ex:
        print(f"[feed falhou] {spec['name']}: {ex}")
        return []

def dedupe(items):
    seen, out = set(), []
    for it in items:
        k = re.sub(r"\W+", "", it["title"].lower())[:60]
        if k in seen: continue
        seen.add(k); out.append(it)
    return out

def fetch_weather():
    w = CFG["weather"]
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": w["latitude"], "longitude": w["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": w["timezone"], "forecast_days": 1}, headers=UA, timeout=6)
        j = r.json()
        code = j["current"]["weather_code"]
        desc = {0:"céu limpo",1:"quase limpo",2:"parcialmente nublado",3:"nublado",45:"nevoeiro",48:"nevoeiro",
                51:"garoa fraca",53:"garoa",55:"garoa forte",61:"chuva fraca",63:"chuva",65:"chuva forte",
                80:"pancadas de chuva",81:"pancadas de chuva",82:"pancadas fortes",95:"trovoadas",96:"trovoadas",99:"trovoadas"}.get(code, "tempo fechado")
        t = j["current"]["temperature_2m"]; st = j["current"]["apparent_temperature"]
        tmax = j["daily"]["temperature_2m_max"][0]; tmin = j["daily"]["temperature_2m_min"][0]
        chuva = j["daily"]["precipitation_probability_max"][0]
        return f"Tempo em Belém: agora {t:.0f}°C (sensação {st:.0f}°C), {desc}. Máx {tmax:.0f}° / mín {tmin:.0f}°. Chance de chuva: {chuva}%."
    except Exception as ex:
        print(f"[clima falhou] {ex}")
        return "Tempo em Belém: típico dia de equador - calor, umidade e aquela pancada da tarde."

def fetch_onthisday(n=3):
    try:
        r = requests.get(f"https://pt.wikipedia.org/api/rest_v1/feed/onthisday/events/{NOW.month:02d}/{NOW.day:02d}",
                         headers=UA, timeout=6)
        evs = r.json().get("events", [])
        picks = []
        for ev in evs:
            txt = clean_html(ev.get("text", ""))
            if not txt or is_banned(txt): continue
            picks.append(f"{ev.get('year','?')} - {trunc(txt, 150)}")
            if len(picks) >= n: break
        return picks
    except Exception as ex:
        print(f"[neste dia falhou] {ex}")
        return []

# ---------- caca-palavras ----------
def gen_wordsearch(words, size=12):
    words = [strip_accents(w).upper().replace(" ", "") for w in words]
    dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    grid = [[None]*size for _ in range(size)]
    placed = {}
    dnames = {(1,0):"→",(-1,0):"←",(0,1):"↓",(0,-1):"↑",(1,1):"↘",(1,-1):"↗",(-1,1):"↙",(-1,-1):"↖"}
    for w in sorted(words, key=len, reverse=True):
        ok = False
        for _ in range(400):
            dx, dy = random.choice(dirs)
            x = random.randrange(size); y = random.randrange(size)
            xe, ye = x + dx*(len(w)-1), y + dy*(len(w)-1)
            if not (0 <= xe < size and 0 <= ye < size): continue
            if all(grid[y+dy*i][x+dx*i] in (None, w[i]) for i in range(len(w))):
                for i in range(len(w)):
                    grid[y+dy*i][x+dx*i] = w[i]
                placed[w] = (y+1, x+1, dnames[(dx,dy)])
                ok = True
                break
        if not ok:
            print(f"[caca-palavras] nao coube: {w}")
    for y in range(size):
        for x in range(size):
            if grid[y][x] is None:
                grid[y][x] = random.choice("ABCDEFGHIJLMNOPQRSTUVWZ")
    return grid, placed

# ---------- texto integral + resumo ----------
JUNK_P = re.compile(r"(newsletter|inscreva-se|subscribe|sign up|cookies|all rights reserved|leia também|publicidade|anuncie|compartilhe|whatsApp|telegram|MELHOR (SÉRIE|ATOR|ATRIZ|FILME)|CONVIDADO EM SÉRIE|EM SÉRIE LIMITADA)", re.I)
def fetch_full_text(url, min_paras=3):
    """Baixa a pagina da materia e extrai os paragrafos do artigo."""
    if not url:
        return []
    try:
        r = requests.get(url, headers=UA, timeout=6, allow_redirects=True)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "header", "footer", "aside", "form", "figure", "figcaption", "iframe"]):
            t.decompose()
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        ps = [clean_html(p) for p in ps]
        def gritado(p):
            letras = [ch for ch in p if ch.isalpha()]
            return len(letras) > 100 and sum(1 for ch in letras if ch.isupper()) / len(letras) > 0.22
        ps = [p for p in ps if p and len(p) > 60 and not JUNK_P.search(p) and not gritado(p)]
        return ps if len(ps) >= min_paras else []
    except Exception:
        return []

def summarize(ps, max_sents=4, max_chars=430):
    """Resumo extrativo CURTO: pontua frases por frequencia de termos e devolve
    um unico paragrafo enxuto, so com o que importa."""
    text = " ".join(ps)
    sents = re.split(r'(?<=[.!?\u203c])\s+(?=[A-ZÀ-Þ0-9“"(])', text)
    sents = [s.strip() for s in sents if 40 < len(s) < 400][:70]
    if len(sents) <= max_sents:
        chosen = sents
    else:
        freq = {}
        for s in sents:
            for w in re.findall(r"[a-zà-ÿ]{4,}", s.lower()):
                if w not in STOP:
                    freq[w] = freq.get(w, 0) + 1
        if freq:
            mx = max(freq.values())
            freq = {k: v / mx for k, v in freq.items()}
        scored = []
        for i, s in enumerate(sents):
            ws = [w for w in re.findall(r"[a-zà-ÿ]{4,}", s.lower()) if w not in STOP]
            sc = sum(freq.get(w, 0) for w in ws) / (len(ws) or 1)
            bonus = 1.15 if i < 3 else 1.0  # lead do artigo
            scored.append((sc * bonus, i, s))
        top = sorted(sorted(scored, key=lambda x: -x[0])[:max_sents], key=lambda x: x[1])
        chosen = [s for _, _, s in top]
    out, total = [], 0
    for s in chosen:
        if total + len(s) > max_chars and out:
            break
        out.append(s); total += len(s)
    return [" ".join(out)] if out else []

def take_full(pool, n):
    """Como take(), mas baixa o texto integral da materia; quem falha e descartado."""
    out, tentados = [], 0
    for it in pool:
        if len(out) >= n or tentados >= n * 4:
            break
        k = re.sub(r"\W+", "", it["title"].lower())[:60]
        if k in used:
            continue
        w = title_words(it["title"])
        if w and any(len(w & u) / max(1, len(w | u)) > 0.45 for u in used_words):
            continue
        tentados += 1
        ps = fetch_full_text(it["url"])
        if not ps:
            print(f"[texto integral falhou] {it['source']}: {it['title'][:60]}")
            continue
        if is_banned(" ".join(ps)[:1600]):
            continue
        it["body"] = summarize(ps)
        used.add(k); used_words.append(w); out.append(it)
    return out

# ---------- charge (tirinha com imagens reais em desenho) ----------
def lineart(pil_img, la_cfg=None):
    """Foto real -> arte de linha P&B (tirinha classica de jornal):
    1) mean-shift duplo achata texturas (grama, pelagem, folhagem);
    2) diferenca de gaussianas estilo xdog extrai os contornos;
    3) supressao por densidade local apaga zonas de rabisco denso;
    4) filtro de componentes remove pontinhos de ruido;
    5) engrossa levemente o traco. Resultado: fundo branco, so o
    contorno preto dos personagens, sem sombreamento."""
    cfg = dict({"ms_sp": 35, "ms_sr": 55, "dog_lo": 0.8, "dog_hi": 2.0,
                "dog_p": 20, "dog_thresh": 24, "dens": 0.55, "dens_k": 17,
                "speck_frac": 0.00004, "dilate": 1},
               **(la_cfg or {}))
    bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    sm = cv2.pyrMeanShiftFiltering(bgr, cfg["ms_sp"], cfg["ms_sr"])
    sm = cv2.pyrMeanShiftFiltering(sm, cfg["ms_sp"], cfg["ms_sr"])
    gray = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
    g_lo = cv2.GaussianBlur(gray, (0, 0), cfg["dog_lo"]).astype(np.float32)
    g_hi = cv2.GaussianBlur(gray, (0, 0), cfg["dog_hi"]).astype(np.float32)
    p = cfg["dog_p"]
    d = (1 + p) * g_lo - p * g_hi
    e = np.where(d >= cfg["dog_thresh"], 255.0,
                 255.0 * (1.0 + np.tanh(250.0 * (d - cfg["dog_thresh"]) / 255.0))).astype(np.uint8)
    inv = (255 - e).astype(np.float32) / 255.0
    loc = cv2.boxFilter(inv, -1, (cfg["dens_k"], cfg["dens_k"]), normalize=True)
    e[loc > cfg["dens"]] = 255
    n, labels, stats, _ = cv2.connectedComponentsWithStats(255 - e, 8)
    h, w = e.shape
    min_area = max(24, int(w * h * cfg["speck_frac"]))
    out = np.full_like(e, 255)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 0
    if cfg["dilate"] > 0:
        out = cv2.erode(out, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)),
                        iterations=cfg["dilate"])
    return Image.fromarray(out)  # tons de cinza: branco com traco preto

COMIC_PATH = os.path.join(BASE, "comic.png")
COMIC_CREDITS = []
def fetch_comic():
    """Monta uma sequência visual de verdade: uma fonte diferente por batida.

    As imagens e licenças são fixadas no config para que uma nova execução não
    transforme os três quadros em variações aleatórias da mesma fotografia.
    """
    global COMIC_CREDITS
    imgs, credits = [], []
    for panel in CFG["comic"].get("panels", []):
        try:
            b = requests.get(panel["url"], headers=UA, timeout=15).content
            photo = Image.open(io.BytesIO(b)).convert("RGB")
            # Tons de cinza preservam pose/rosto e evitam que o filtro de borda
            # apague justamente a ação que faz a piada funcionar.
            art = ImageOps.autocontrast(ImageOps.grayscale(photo)).convert("RGB")
            imgs.append(art)
            artist = clean_html(panel.get("artist", "")) or "autor desconhecido"
            lic = clean_html(panel.get("license", ""))
            credits.append(f"{artist} ({lic})" if lic else artist)
        except Exception as ex:
            print(f"[charge falhou] {panel.get('title','painel')}: {ex}")
    if len(imgs) != 3:
        print("[charge] são necessárias três imagens distintas; charge pulada")
        return None
    PW, PH, IMGH, GAP, OUT = 500, 452, 340, 16, 12
    W = OUT*2 + PW*3 + GAP*2; H = OUT*2 + PH
    strip = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(strip)
    f_cap = ImageFont.truetype(FD + "DejaVuSerif-Italic.ttf", 23)
    for i, img in enumerate(imgs):
        x0 = OUT + i*(PW+GAP); y0 = OUT
        strip.paste(ImageOps.fit(img, (PW, IMGH), Image.LANCZOS), (x0, y0))
        dr.rectangle([x0, y0, x0+PW-1, y0+PH-1], outline="black", width=3)
        bx0, by0, bx1, by1 = x0+10, y0+IMGH+8, x0+PW-10, y0+PH-10
        dr.rounded_rectangle([bx0, by0, bx1, by1], radius=16, fill="white", outline="black", width=3)
        cap = CFG["comic"]["panels_pt"][i]
        words = cap.split(); lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if dr.textlength(t, font=f_cap) <= (bx1-bx0-28): cur = t
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
        ty = by0 + ((by1-by0) - len(lines)*27) / 2
        for ln in lines:
            dr.text(((bx0+bx1)/2, ty), ln, font=f_cap, fill="black", anchor="ma")
            ty += 27
    strip.save(COMIC_PATH)
    COMIC_CREDITS = credits
    return COMIC_PATH, W, H

# ---------- clima / dados ----------
print("Coletando feeds...")
pt_by_feed = {}
for spec in CFG["feeds_pt"]:
    pt_by_feed[spec["name"]] = fetch_feed(spec)
en_by_feed = {}
for spec in CFG["feeds_en"]:
    en_by_feed[spec["name"]] = fetch_feed(spec)
nl_pt = []
for spec in CFG.get("newsletters_pt", []):
    nl_pt += fetch_feed(spec)
nl_en_by_feed = {}
for spec in CFG["newsletters_en"]:
    nl_en_by_feed[spec["name"]] = fetch_feed(spec)
nl_pt = dedupe(nl_pt)
series_pool = dedupe([it for spec in CFG.get("feeds_series", []) for it in fetch_feed(spec)])

all_pt = dedupe([it for lst in pt_by_feed.values() for it in lst])
all_en = dedupe([it for lst in en_by_feed.values() for it in lst])
print(f"Itens PT: {len(all_pt)} | EN: {len(all_en)} | NL PT: {len(nl_pt)} | NL EN: {sum(len(v) for v in nl_en_by_feed.values())}")

weather_txt = fetch_weather()
onthisday = fetch_onthisday(3)

used = set()
used_words = []
STOP = set("de da do das dos a o as os e em um uma no na nos nas com por que se ao à às aos the and of to in on for with".split())
def title_words(t):
    return set(w for w in re.findall(r"[a-zà-ÿ]{4,}", t.lower()) if w not in STOP)
def take(pool, n):
    out = []
    for it in pool:
        k = re.sub(r"\W+", "", it["title"].lower())[:60]
        if k in used: continue
        w = title_words(it["title"])
        if w and any(len(w & u) / max(1, len(w | u)) > 0.45 for u in used_words):
            continue
        used.add(k); used_words.append(w); out.append(it)
        if len(out) >= n: break
    return out
def interleave(*pools):
    out, i = [], 0
    pools = [list(p) for p in pools]
    while any(pools):
        for p in pools:
            if p: out.append(p.pop(0))
        i += 1
    return out

print("Baixando texto integral das materias escolhidas...")
positivos = sorted(all_pt, key=lambda x: -x["pos"])
sec_abertura = take_full(positivos, 2)
sec_boas = take_full(interleave(pt_by_feed.get("Só Notícia Boa", []), pt_by_feed.get("Razões para Acreditar", [])), 2)
sec_series = take_full(series_pool, 2)
sec_tech = take_full(interleave(en_by_feed.get("TechCrunch", []), en_by_feed.get("Hacker News", [])), 2)
sec_science = take_full(interleave(en_by_feed.get("Phys.org", []), en_by_feed.get("Space.com", [])), 1)
nl_pt = take_full(nl_pt, 2)
nl_en = take_full(dedupe(interleave(*nl_en_by_feed.values())), 3)

study_pool = CFG["study_cards_fluids"] if DOY % 2 == 0 else CFG["study_cards_english"]
study = study_pool[(DOY // 2) % len(study_pool)]
study_tag = "Mecânica dos Fluidos - Fox & McDonald, cap. 3" if DOY % 2 == 0 else "Inglês"

theme = CFG["wordsearch_themes"][DOY % len(CFG["wordsearch_themes"])]
grid, placed = gen_wordsearch(theme["palavras"])
gabarito = " · ".join(f"{w}: L{l} C{c} {d}" for w, (l, c, d) in placed.items())

print("Montando charge...")
comic = None
_local_comic = os.path.join(BASE, "comic.png")
if os.path.exists(_local_comic):
    try:
        _ci = Image.open(_local_comic)
        comic = (_local_comic, _ci.width, _ci.height)
        COMIC_CREDITS = ["Dachshund drawing.jpg, Wikimedia Commons"]
    except Exception:
        comic = fetch_comic()
else:
    comic = fetch_comic()

# ---------- blocos ----------
def block_section(title, new_page=False, full=False):
    def h(w): return 26
    def draw(c, x, ytop, w):
        c.setFillColor(INK); c.setFont("Sans-Bold", 13)
        c.drawString(x, ytop - 14, title.upper())
        c.setStrokeColor(INK); c.setLineWidth(1.1)
        c.line(x, ytop - 19, x + w, ytop - 19)
    return {"h": h, "draw": draw, "new_page": new_page, "full": full, "fixed": True, "keep_next": 250}

def block_news(it):
    paras = it.get("body") or ([it["summary"]] if it.get("summary") else [])
    def h(w):
        total = len(wrap(it["title"], "Serif-Bold", 11.5, w)) * 14.5
        for p in paras:
            total += 3 + len(wrap(p, "Serif", 10.5, w)) * 13.5
        return total + 14 + 8
    def draw(c, x, ytop, w):
        y = ytop
        c.setFillColor(INK)
        for ln in wrap(it["title"], "Serif-Bold", 11.5, w):
            c.setFont("Serif-Bold", 11.5); c.drawString(x, y - 12, ln); y -= 14.5
        c.setFillColor(HexColor("#2b2b2b"))
        for p in paras:
            y -= 3
            for ln in wrap(p, "Serif", 10.5, w):
                c.setFont("Serif", 10.5); c.drawString(x, y - 11, ln); y -= 13.5
        src = it["source"] + (" · " + it["when"] if it["when"] else "")
        c.setFont("Serif-Italic", 8.5); c.setFillColor(LGRAY)
        c.drawString(x, y - 10, src)
        if it.get("url"):
            sw = pdfmetrics.stringWidth(src, "Serif-Italic", 8.5)
            c.setFillColor(HexColor("#4a5a8a"))
            c.setFont("Serif-Italic", 8.5)
            c.drawString(x + sw + 6, y - 10, "[continuar lendo]")
            c.linkURL(it["url"], (x + sw + 4, y - 14, x + sw + 6 + pdfmetrics.stringWidth("[continuar lendo]", "Serif-Italic", 8.5) + 2, y - 2), relative=0)
    return {"h": h, "draw": draw, "fixed": True}

def block_box(titulo, linhas, bg=BOXBG, min_h=None):
    """Caixa com titulo e linhas [(font,size,text)]; altura calculada."""
    def h(w):
        total = 30
        for f, s, t in linhas:
            total += len(wrap(t, f, s, w - 22)) * (s + 3.2)
        return max(min_h or 0, total + 12)
    def draw(c, x, ytop, w):
        hh = h(w)
        c.setFillColor(bg); c.setStrokeColor(HexColor("#c9c0aa")); c.setLineWidth(0.8)
        c.roundRect(x, ytop - hh, w, hh, 5, stroke=1, fill=1)
        y = ytop - 20
        c.setFillColor(INK); c.setFont("Sans-Bold", 10.5)
        c.drawString(x + 11, y, titulo.upper()); y -= 8
        c.setStrokeColor(HexColor("#c9c0aa")); c.line(x + 11, y, x + w - 11, y); y -= 8
        for f, s, t in linhas:
            c.setFont(f, s); c.setFillColor(INK if f != "Serif-Italic" else GRAY)
            for ln in wrap(t, f, s, w - 22):
                c.drawString(x + 11, y - s + 2, ln); y -= (s + 3.2)
    return {"h": h, "draw": draw, "fixed": True}

def block_filler(titulo, texto, lang="pt"):
    bg = BOXBG if lang == "pt" else BOXBG2
    def draw_at(c, x, ytop, w, hh):
        c.setFillColor(bg); c.setStrokeColor(HexColor("#c9c0aa")); c.setLineWidth(0.8)
        c.roundRect(x, ytop - hh, w, hh, 5, stroke=1, fill=1)
        c.setFillColor(INK); c.setFont("Sans-Bold", 9.5)
        c.drawString(x + 11, ytop - 17, titulo.upper())
        lines = wrap(texto, "Serif", 10.5, w - 22)
        avail = hh - 26
        ty = ytop - 22 - max(0, (avail - len(lines)*13.5) / 2)
        c.setFont("Serif", 10.5); c.setFillColor(HexColor("#2b2b2b"))
        for ln in lines:
            c.drawString(x + 11, ty - 9, ln); ty -= 13.5
    def text_h(w):
        return 26 + len(wrap(texto, "Serif", 10.5, w - 22)) * 13.5 + 8
    return {"filler": True, "draw_at": draw_at, "text_h": text_h}

def block_masthead():
    def h(w): return 78
    def draw(c, x, ytop, w):
        c.setFillColor(INK)
        c.setFont(VOGUE_FONT, 44)
        c.drawCentredString(x + w/2, ytop - 42, CFG["paper_name"])
        c.setStrokeColor(INK); c.setLineWidth(2.2); c.line(x, ytop - 52, x + w, ytop - 52)
        c.setLineWidth(0.7); c.line(x, ytop - 55.5, x + w, ytop - 55.5)
        c.setFont("Serif", 10)
        c.drawString(x, ytop - 70, DATA_PT)
        c.drawRightString(x + w, ytop - 70, f"{CFG['edition_line']} · {CFG['city']}")
    return {"h": h, "draw": draw, "full": True, "fixed": True}

def block_fullstrip(texto, bg=BOXBG2):
    def h(w):
        return 16 + len(wrap(texto, "Serif", 10.5, w - 24)) * 13.5
    def draw(c, x, ytop, w):
        hh = h(w)
        c.setFillColor(bg); c.setStrokeColor(HexColor("#b9c4b9")); c.setLineWidth(0.8)
        c.roundRect(x, ytop - hh, w, hh, 4, stroke=1, fill=1)
        c.setFillColor(INK); c.setFont("Serif", 10.5)
        y = ytop - 8 - 11
        for ln in wrap(texto, "Serif", 10.5, w - 24):
            c.drawCentredString(x + w/2, y, ln); y -= 13.5
    return {"h": h, "draw": draw, "full": True, "fixed": True}

def block_wordsearch():
    CELL = 16.5
    def h(w):
        return 22 + 12*CELL + 8 + 30 + 6
    def draw(c, x, ytop, w):
        c.setFillColor(INK); c.setFont("Sans-Bold", 10.5)
        c.drawString(x, ytop - 13, f"CAÇA-PALAVRAS · TEMA: {theme['tema'].upper()}")
        y0 = ytop - 22
        gw = 12*CELL
        x0 = x + (w - gw)/2
        c.setFont("Mono", 10.5)
        for r in range(12):
            for col in range(12):
                c.setFillColor(INK)
                c.drawCentredString(x0 + col*CELL + CELL/2, y0 - r*CELL - CELL + 4.5, grid[r][col])
        c.setStrokeColor(HexColor("#bbbbbb")); c.setLineWidth(0.4)
        for i in range(13):
            c.line(x0 + i*CELL, y0, x0 + i*CELL, y0 - 12*CELL)
            c.line(x0, y0 - i*CELL, x0 + gw, y0 - i*CELL)
        words = [strip_accents(w).upper() for w in theme["palavras"]]
        wl = "   ".join(words)
        yy = y0 - 12*CELL - 14
        c.setFont("Serif", 9); c.setFillColor(GRAY)
        for ln in wrap(wl, "Serif", 9, w):
            c.drawString(x, yy, ln); yy -= 11
    return {"h": h, "draw": draw, "fixed": True}

def block_comic(path, iw, ih):
    def h(w): return 30 + w * (ih / iw) + 6
    def draw(c, x, ytop, w):
        c.setFillColor(INK); c.setFont("Sans-Bold", 13)
        c.drawString(x, ytop - 14, "CHARGE DO DIA")
        c.setStrokeColor(INK); c.setLineWidth(1.1); c.line(x, ytop - 19, x + w, ytop - 19)
        hh = w * (ih / iw)
        c.drawImage(path, x, ytop - 26 - hh, width=w, height=hh)
    return {"h": h, "draw": draw, "full": True, "fixed": True}

# ---------- motor de colunas ----------
c = rl_canvas.Canvas(OUT_PDF, pagesize=A4)
c.setTitle("O Diário - " + DATA_PT)
c.setFillColor(PAPER); c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

state = {"col": 0, "y": TOP, "page": 1, "ctop": TOP, "lang": "pt"}
def page_top():
    return TOP if state["page"] == 1 else TOP - HEADER_H

def page_header():
    if state["page"] == 1: return
    c.setFillColor(INK); c.setFont(VOGUE_FONT, 9)
    c.drawString(MARGIN, PAGE_H - MARGIN + 8, CFG["paper_name"])
    c.setFont("Serif", 9); c.setFillColor(GRAY)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 8, DATA_PT)
    c.setStrokeColor(INK); c.setLineWidth(0.7)
    c.line(MARGIN, PAGE_H - MARGIN + 2, PAGE_W - MARGIN, PAGE_H - MARGIN + 2)

def new_page(lang=None):
    c.showPage()
    state["page"] += 1; state["col"] = 0
    c.setFillColor(PAPER); c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    page_header()
    state["y"] = page_top()
    state["ctop"] = page_top()
    if lang: state["lang"] = lang

def col_x():
    return MARGIN + state["col"] * (COL_W + GUTTER)

def remaining():
    return state["y"] - BOTTOM

def build_fillers(boxes, lang):
    grupos = []
    for b in boxes:
        grupos.append([block_filler(b["titulo"], t, lang) for t in b["textos"]])
    for g in grupos: random.shuffle(g)
    out = []
    while any(grupos):
        for g in grupos:
            if g: out.append(g.pop())
    return out
fillers = {"pt": build_fillers(CFG["filler_boxes_pt"], "pt"),
           "en": build_fillers(CFG["filler_boxes_en"], "en")}

def fill_column(reserve=0, lang=None):
    lang = lang or state["lang"]
    usados = 0
    while remaining() - reserve > 38 and usados < 4:
        if not fillers[lang]:
            fillers[lang] = build_fillers(CFG["filler_boxes_" + lang], lang)
        f = fillers[lang].pop()
        usados += 1
        want = remaining() - reserve - BLOCK_GAP
        if want < max(50, f["text_h"](COL_W)) * 0.72:
            fillers[lang].insert(0, f)  # devolve pra outra coluna
            break
        hh = min(want, max(50, f["text_h"](COL_W)))
        f["draw_at"](c, col_x(), state["y"], COL_W, hh)
        state["y"] -= hh + BLOCK_GAP

def finish_page():
    """Fecha a pagina atual preenchendo as colunas restantes com a lingua da pagina."""
    if state["col"] == 0 and state["y"] >= state["ctop"]:
        return  # pagina vazia, nada a fechar
    fill_column()
    if state["col"] == 0:
        advance()
        fill_column()

def advance():
    if state["col"] == 0:
        state["col"] = 1; state["y"] = state["ctop"]
    else:
        new_page()

def place(b, lang=None):
    if b.get("new_page"):
        finish_page()
        new_page(lang=lang)
    if lang: state["lang"] = lang
    if b.get("full"):
        if state["col"] != 0:
            fill_column(); advance()
        hh = b["h"](PAGE_W - 2*MARGIN)
        if state["y"] - hh < BOTTOM:
            fill_column(); new_page(lang=state["lang"])
        b["draw"](c, MARGIN, state["y"], PAGE_W - 2*MARGIN)
        state["y"] -= hh + BLOCK_GAP
        state["ctop"] = state["y"]
        return
    hh = b["h"](COL_W)
    need = hh + (b.get("keep_next", 0))
    if need > remaining():
        fill_column()
        advance()
    b["draw"](c, col_x(), state["y"], COL_W)
    state["y"] -= hh + BLOCK_GAP

# ---------- montagem ----------
page_header()
place(block_masthead())
place(block_fullstrip(weather_txt))

place(block_section("Para começar bem"))
for it in sec_abertura: place(block_news(it))

sc_lines = [("Serif-Italic", 9.5, study_tag),
            ("Serif", 10.5, study["conceito"]),
            ("Serif-Bold", 10.5, "Questão: " + study["questao"]),
            ("Serif-Italic", 9.5, "Resposta: " + study["resposta"])]
place(block_box("O que estudar hoje", sc_lines))

if sec_boas:
    place(block_section("Boas notícias"))
    for it in sec_boas: place(block_news(it))

place(block_wordsearch())

if sec_series:
    place(block_section("Séries & filmes"))
    for it in sec_series: place(block_news(it))

if nl_pt:
    place(block_section("Newsletters"))
    for it in nl_pt: place(block_news(it))

if onthisday:
    nd = [("Serif", 10, t) for t in onthisday]
    place(block_box("Neste dia", nd))

# ---- páginas em inglês ----
place(block_section("In English, to start the day", new_page=True), lang="en")
en_note = block_box("Note", [("Serif", 10.5,
    "Uma página inteira em inglês: leitura leve de tecnologia, ciência e newsletters - "
    "treino diário sem esforço.")], bg=BOXBG2)
place(en_note, lang="en")

if sec_tech:
    place(block_section("Tech & AI"), lang="en")
    for it in sec_tech: place(block_news(it), lang="en")

if sec_science:
    place(block_section("Science & Space"), lang="en")
    for it in sec_science: place(block_news(it), lang="en")

if nl_en:
    place(block_section("Newsletters"), lang="en")
    for it in nl_en: place(block_news(it), lang="en")

# ---- página da charge ----
COLOPHON_H = 92
comic_block = None
if comic:
    cb = block_comic(comic[0], comic[1], comic[2])
    cb["new_page"] = True
    comic_block = cb
if comic_block:
    place(comic_block, lang="pt")

# preenche e fecha com colofão ancorado
fill_column(reserve=COLOPHON_H, lang="pt")
if state["col"] == 0:
    advance()
    fill_column(reserve=COLOPHON_H, lang="pt")

ybase = BOTTOM + COLOPHON_H
c.setStrokeColor(INK); c.setLineWidth(0.9)
c.line(MARGIN, ybase, PAGE_W - MARGIN, ybase)
c.setFont("Serif", 7.5); c.setFillColor(GRAY)
fontes = "Fontes: G1 Tecnologia, Canaltech, Só Notícia Boa, Razões para Acreditar, TechCrunch, Hacker News, Phys.org, Space.com, CinePOP, ComingSoon, Rotten Tomatoes, The Marginalian, Dense Discovery, Austin Kleon, Farnam Street · Clima: Open-Meteo · Neste dia: Wikipédia"
cred = " · Charge: imagens distintas do Wikimedia Commons - " + "; ".join(COMIC_CREDITS) if COMIC_CREDITS else ""
col_lines = wrap(f"THE NEWS · protótipo v5 · gerado em {NOW.strftime('%d/%m/%Y %H:%M')} · {fontes}{cred}", "Serif", 7.5, PAGE_W - 2*MARGIN)
yy = ybase - 10
for ln in col_lines[:4]:
    c.drawString(MARGIN, yy, ln); yy -= 9.5
# gabarito de ponta-cabeça
c.saveState()
c.translate(PAGE_W/2, BOTTOM + 12)
c.rotate(180)
c.setFont("Serif", 7); c.setFillColor(LGRAY)
c.drawCentredString(0, 0, trunc("Gabarito do caça-palavras: " + gabarito, 180))
c.restoreState()

c.showPage()
c.save()
print("PDF:", OUT_PDF)


# ---------- EPUB (Kindle / Send to Kindle) ----------
# Saida reflowavel: mesmas secoes do PDF em XHTML; charge e caca-palavras
# entram como imagens para renderizarem intactos no Kindle.
OUT_EPUB = sys.argv[3] if len(sys.argv) > 3 else re.sub(r"\.pdf$", "", OUT_PDF, flags=re.I) + ".epub"
EPUB_CFG = CFG.get("epub", {})

def epub_esc(s):
    return html.escape(s or "", quote=False)

def epub_news_html(it):
    paras = it.get("body") or ([it["summary"]] if it.get("summary") else [])
    parts = [f"<h2>{epub_esc(it['title'])}</h2>"]
    for p in paras:
        parts.append(f"<p>{epub_esc(p)}</p>")
    src = it["source"] + (" · " + it["when"] if it["when"] else "")
    link = (f' &middot; <a href="{html.escape(it["url"], quote=True)}">continuar lendo</a>'
            if it.get("url") else "")
    parts.append(f'<p class="src">{epub_esc(src)}{link}</p>')
    return "\n".join(parts)

def epub_wordsearch_png(path):
    CELL, N = 46, 12
    W = N * CELL + 2
    img = Image.new("RGB", (W, W), "white")
    dr = ImageDraw.Draw(img)
    f = ImageFont.truetype(FD + "DejaVuSansMono.ttf", 30)
    for r in range(N):
        for col in range(N):
            dr.text((1 + col*CELL + CELL/2, 1 + r*CELL + CELL/2), grid[r][col],
                    font=f, fill="black", anchor="mm")
    for i in range(N + 1):
        dr.line([(1 + i*CELL, 1), (1 + i*CELL, W - 1)], fill="#bbbbbb", width=1)
        dr.line([(1, 1 + i*CELL), (W - 1, 1 + i*CELL)], fill="#bbbbbb", width=1)
    img.save(path)

def build_epub(path):
    import zipfile, uuid
    book_id = "urn:uuid:" + str(uuid.uuid4())
    stamp = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

    tmp = os.path.join(BASE, "_epub_build")
    os.makedirs(tmp, exist_ok=True)
    ws_png = os.path.join(tmp, "cacapalavras.png")
    epub_wordsearch_png(ws_png)
    comic_png = comic[0] if comic else None

    frase = random.choice(CFG["filler_boxes_pt"][0]["textos"])  # Frase do dia

    chapters = []  # (id, titulo, body_html)

    cover = [f'<p class="masthead">{epub_esc(CFG["paper_name"])}</p>',
             '<div class="rule2"></div><div class="rule1"></div>',
             f'<p class="dateline">{epub_esc(DATA_PT)}<br/>{epub_esc(CFG["edition_line"])} &middot; {epub_esc(CFG["city"])}</p>',
             f'<div class="box"><p>{epub_esc(weather_txt)}</p></div>',
             f'<div class="box"><p class="src">FRASE DO DIA</p><p>{epub_esc(frase)}</p></div>']
    chapters.append(("capa", "Capa", "\n".join(cover)))

    if sec_abertura:
        body = [epub_news_html(it) for it in sec_abertura]
        sc = (f'<div class="box"><p class="src">O QUE ESTUDAR HOJE</p>'
              f'<p class="src">{epub_esc(study_tag)}</p>'
              f'<p>{epub_esc(study["conceito"])}</p>'
              f'<p><b>Questão:</b> {epub_esc(study["questao"])}</p>'
              f'<p class="src"><i>Resposta: {epub_esc(study["resposta"])}</i></p></div>')
        body.append(sc)
        chapters.append(("abertura", "Para começar bem", "\n".join(body)))

    if sec_boas:
        chapters.append(("boas", "Boas notícias",
                         "\n".join(epub_news_html(it) for it in sec_boas)))

    words = [strip_accents(w).upper() for w in theme["palavras"]]
    cp_body = [f'<p class="src">TEMA: {epub_esc(theme["tema"].upper())}</p>',
               '<p class="center"><img src="img/cacapalavras.png" alt="Caça-palavras"/></p>',
               f'<p class="wordlist">{"&nbsp;&nbsp;&nbsp;".join(epub_esc(w) for w in words)}</p>',
               f'<p class="src">Gabarito: {epub_esc(trunc(gabarito, 300))}</p>']
    chapters.append(("cacapalavras", "Caça-palavras", "\n".join(cp_body)))

    if sec_series:
        chapters.append(("series", "Séries &amp; filmes",
                         "\n".join(epub_news_html(it) for it in sec_series)))
    if nl_pt:
        chapters.append(("newsletters", "Newsletters",
                         "\n".join(epub_news_html(it) for it in nl_pt)))
    if onthisday:
        nd = "".join(f"<p>{epub_esc(t)}</p>" for t in onthisday)
        chapters.append(("nestedie", "Neste dia",
                         f'<div class="box">{nd}</div>'))

    en_parts = ['<div class="box"><p>Uma seção inteira em inglês: leitura leve de '
                'tecnologia, ciência e newsletters - treino diário sem esforço.</p></div>']
    if sec_tech:
        en_parts.append("<h1>Tech &amp; AI</h1>")
        en_parts += [epub_news_html(it) for it in sec_tech]
    if sec_science:
        en_parts.append("<h1>Science &amp; Space</h1>")
        en_parts += [epub_news_html(it) for it in sec_science]
    if nl_en:
        en_parts.append("<h1>Newsletters</h1>")
        en_parts += [epub_news_html(it) for it in nl_en]
    chapters.append(("english", "In English, to start the day", "\n".join(en_parts)))

    pausa = []
    for b in CFG["filler_boxes_pt"] + CFG["filler_boxes_en"]:
        pausa.append(f'<div class="box"><p class="src">{epub_esc(b["titulo"].upper())}</p>'
                     f'<p>{epub_esc(random.choice(b["textos"]))}</p></div>')
    chapters.append(("pausas", "Pausas do dia", "\n".join(pausa)))

    if comic_png:
        cred = ("; ".join(COMIC_CREDITS)) if COMIC_CREDITS else ""
        ch_body = ['<p class="center"><img src="img/charge.png" alt="Charge do dia"/></p>']
        if cred:
            ch_body.append(f'<p class="src">Charge: imagens do Wikimedia Commons - {epub_esc(cred)}</p>')
        chapters.append(("charge", "Charge do dia", "\n".join(ch_body)))

    colofon = (f'<p class="src">THE NEWS &middot; protótipo v5 &middot; gerado em '
               f'{NOW.strftime("%d/%m/%Y %H:%M")}</p>'
               f'<p class="src">Fontes: G1 Tecnologia, Canaltech, Só Notícia Boa, Razões para '
               f'Acreditar, TechCrunch, Hacker News, Phys.org, Space.com, CinePOP, ComingSoon, '
               f'Rotten Tomatoes, The Marginalian, Dense Discovery, Austin Kleon, Farnam Street '
               f'&middot; Clima: Open-Meteo &middot; Neste dia: Wikipédia</p>')
    chapters.append(("colofao", "Colofão", colofon))

    css = """
@font-face { font-family: 'Bodoni'; src: url('fonts/BodoniModa.ttf'); }
body { font-family: serif; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 1.25em; text-transform: uppercase; border-bottom: 2px solid #1a1a1a;
     padding-bottom: 0.2em; margin-top: 1.2em; }
h2 { font-size: 1.05em; margin-bottom: 0.2em; }
p { margin: 0.5em 0; text-align: justify; }
.masthead { font-family: 'Bodoni', serif; font-weight: bold; font-size: 2.4em;
            text-align: center; margin: 0.6em 0 0.1em; }
.dateline { text-align: left; font-size: 0.95em; margin-bottom: 1em; }
.rule2 { border-top: 3px solid #1a1a1a; margin: 0 0 2px; }
.rule1 { border-top: 1px solid #1a1a1a; margin: 0 0 0.8em; }
.box { border: 1px solid #c9c0aa; background: #f4eee1; padding: 0.4em 0.8em;
       margin: 0.8em 0; border-radius: 6px; }
.src { font-size: 0.85em; font-style: italic; color: #5a5a5a; }
.center { text-align: center; }
.wordlist { font-size: 0.9em; color: #444; }
img { max-width: 100%; }
"""

    def xhtml(title, body):
        return ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<!DOCTYPE html>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="pt-BR" lang="pt-BR">\n<head>'
                f'<meta charset="utf-8"/><title>{title}</title>'
                '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
                f'<body>{body}</body></html>')

    nav_items = "\n".join(f'<li><a href="cap_{cid}.xhtml">{title}</a></li>'
                           for cid, title, _ in chapters)
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
           'xml:lang="pt-BR" lang="pt-BR"><head><meta charset="utf-8"/>'
           f'<title>{epub_esc(CFG["paper_name"])} - Sumário</title>'
           '<link rel="stylesheet" type="text/css" href="style.css"/></head><body>'
           '<nav epub:type="toc"><h1>Sumário</h1><ol>' + nav_items + '</ol></nav></body></html>')

    ncx_points = "\n".join(
        f'<navPoint id="np{i+1}" playOrder="{i+1}"><navLabel><text>{title}</text></navLabel>'
        f'<content src="cap_{cid}.xhtml"/></navPoint>'
        for i, (cid, title, _) in enumerate(chapters))
    ncx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{book_id}"/></head>'
           f'<docTitle><text>{epub_esc(CFG["paper_name"])}</text></docTitle>'
           f'<navMap>{ncx_points}</navMap></ncx>')

    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>',
                '<item id="font-bodoni" href="fonts/BodoniModa.ttf" media-type="font/ttf"/>',
                '<item id="img-ws" href="img/cacapalavras.png" media-type="image/png"/>']
    spine = []
    for cid, title, _ in chapters:
        manifest.append(f'<item id="{cid}" href="cap_{cid}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{cid}"/>')
    if comic_png:
        manifest.append('<item id="img-charge" href="img/charge.png" media-type="image/png"/>')

    title_full = f'{CFG["paper_name"]} - {DATA_PT}'
    author = EPUB_CFG.get("author", "The News")
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="bookid">{book_id}</dc:identifier>'
           f'<dc:title>{epub_esc(title_full)}</dc:title>'
           f'<dc:creator>{epub_esc(author)}</dc:creator>'
           f'<dc:language>{EPUB_CFG.get("lang", "pt-BR")}</dc:language>'
           f'<meta property="dcterms:modified">{stamp}</meta>'
           '</metadata>'
           '<manifest>' + "".join(manifest) + '</manifest>'
           '<spine toc="ncx">' + "".join(spine) + '</spine></package>')

    container = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/></rootfiles></container>')

    font_src = VOGUE_PATH if os.path.exists(VOGUE_PATH) else FD + "DejaVuSerif-Bold.ttf"

    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", css, compress_type=zipfile.ZIP_DEFLATED)
        z.write(font_src, "OEBPS/fonts/BodoniModa.ttf", compress_type=zipfile.ZIP_DEFLATED)
        z.write(ws_png, "OEBPS/img/cacapalavras.png", compress_type=zipfile.ZIP_DEFLATED)
        if comic_png:
            z.write(comic_png, "OEBPS/img/charge.png", compress_type=zipfile.ZIP_DEFLATED)
        for cid, title, body in chapters:
            z.writestr(f"OEBPS/cap_{cid}.xhtml", xhtml(title, body),
                       compress_type=zipfile.ZIP_DEFLATED)
    return path

if EPUB_CFG.get("enabled", True):
    print("Montando EPUB...")
    build_epub(OUT_EPUB)
    print("EPUB:", OUT_EPUB)
