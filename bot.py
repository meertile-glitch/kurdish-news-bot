import os
import re
import hashlib
import requests
import asyncio
import random
import math
import feedparser
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_PAGE_ID = os.getenv("FB_PAGE_ID") or os.getenv("FB_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_TOKEN")

FEEDS = {
    "G AI": "https://news.google.com/rss/search?q=artificial+intelligence+when:1d&hl=en-US&gl=US&ceid=US:en",
    "G ChatGPT": "https://news.google.com/rss/search?q=ChatGPT+when:1d&hl=en-US&gl=US&ceid=US:en",
    "G Gemini": "https://news.google.com/rss/search?q=Gemini+AI+when:1d&hl=en-US&gl=US&ceid=US:en",
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "TheVerge": "https://www.theverge.com/rss/ai/index.xml",
    "Wired": "https://www.wired.com/feed/tag/ai/latest/rss"
}

FONT_BOLD = "Vazirmatn-Bold.ttf"
FONT_REG = "Vazirmatn-Regular.ttf"

def ensure_fonts():
    urls = {
        FONT_BOLD: "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf",
        FONT_REG: "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Regular.ttf"
    }
    for path, url in urls.items():
        if not os.path.exists(path):
            try:
                print(f"📥 Downloading {path}...")
                r = requests.get(url, timeout=20)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"❌ Font download failed {path}: {e}")

def cl(t):
    if not t: return ""
    t = re.sub(r'<[^<]+?>', '', t)
    return re.sub(r'\s+', ' ', t).strip()[:500]

def tr_mem(txt, src='en', tgt='ckb'):
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": txt[:400], "langpair": f"{src}|{tgt}"}, timeout=10)
        d = r.json()
        if d.get('responseStatus') == 200:
            trans = d['responseData']['translatedText']
            if trans and len(trans) > 8 and 'MYMEMORY' not in trans:
                return trans
    except: pass
    return None

def to_ku(txt, src='en'):
    txt = cl(txt)
    if not txt: return ""
    for s, t in [(src, 'ckb'), ('en', 'ckb'), (src, 'ku'), ('en', 'ku')]:
        r = tr_mem(txt, s, t)
        if r: return r
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target='ckb').translate(txt[:400])
    except: return txt

def fresh(e, h=24):
    if hasattr(e, 'published_parsed') and e.published_parsed:
        try:
            pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - pub <= timedelta(hours=h)
        except: return True
    return True

def render_kurdish_text(text, max_chars=28):
    if not text: return []
    words, lines, cur, cur_len = text.split(), [], [], 0
    for w in words:
        if cur_len + len(w) + 1 <= max_chars:
            cur.append(w); cur_len += len(w) + 1
        else:
            if cur: lines.append(" ".join(cur))
            cur, cur_len = [w], len(w)
    if cur: lines.append(" ".join(cur))
    return [get_display(arabic_reshaper.reshape(l)) for l in lines]

# Fonts loaded once globally
ensure_fonts()
try:
    FB_KU = ImageFont.truetype(FONT_BOLD, 48)
    FR_KU = ImageFont.truetype(FONT_REG, 30)
    FS_EN = ImageFont.truetype(FONT_BOLD, 20)
except:
    FB_KU = FR_KU = FS_EN = ImageFont.load_default()

def create_beautiful_background(W, H):
    img = Image.new('RGB', (W, H), (4, 6, 22))
    draw = ImageDraw.Draw(img, 'RGBA')
    for y in range(H):
        r = int(4 + y * 0.02); g = int(6 + y * 0.025); b = int(22 + y * 0.06)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    for _ in range(80): # 150 زۆرە، 80 بەسە بۆ جوانی
        x, y = random.randint(-50, W+50), random.randint(-50, H+50)
        s, alpha = random.randint(10, 40), random.randint(20, 80)
        c = random.choice([(100,80,255),(80,130,255),(140,90,255),(70,200,255)])
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(*c, alpha))
    return img

def card(title, summary, out="card.jpg"):
    W, H = 1080, 1080
    base = create_beautiful_background(W, H)
    img = base.copy()
    draw = ImageDraw.Draw(img, 'RGBA')

    # Logo
    draw.ellipse([45,40,145,140], fill=(255,108,20))
    draw.text((73,62), "AI", fill="white", font=FB_KU)
    draw.text((175,58), "AI NEWS KURDISH", fill="white", font=FS_EN)

    cw, ch = 880, 680
    cx, cy = (W-cw)//2, (H-ch)//2 + 40
    glass = Image.new('RGBA', (cw, ch), (18,22,48,210))
    mask = Image.new('L', (cw,ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,cw,ch], radius=32, fill=255)
    glass.putalpha(mask)
    img.paste(glass, (cx,cy), glass)
    draw = ImageDraw.Draw(img, 'RGBA')

    title_lines = render_kurdish_text(title[:130], 26)[:4]
    sy = cy + 80
    for i, line in enumerate(title_lines):
        tw = draw.textbbox((0,0), line, font=FB_KU)[2]
        draw.text((W//2 - tw//2, sy + i*70), line, fill="white", font=FB_KU)

    if summary:
        summary_lines = render_kurdish_text(summary[:120], 36)[:2]
        sy2 = sy + len(title_lines)*70 + 25
        for j, line in enumerate(summary_lines):
            tw = draw.textbbox((0,0), line, font=FR_KU)[2]
            draw.text((W//2 - tw//2, sy2 + j*40), line, fill=(220,225,255), font=FR_KU)

    ly = cy + ch - 90
    draw.line([cx+60, ly, cx+cw-60, ly], fill=(100,180,255,120), width=1)
    draw.text((W//2-75, ly+20), "AI News Kurdish", fill=(130,190,255), font=FS_EN)

    img.save(out, quality=92, optimize=True)
    return out
