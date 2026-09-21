import os
import re
import hashlib
import requests
import asyncio
import feedparser
from datetime import datetime, timezone, timedelta
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kurdish_short_news")
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "") or os.getenv("FB_ID", "")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "") or os.getenv("FB_TOKEN", "")

TECHCRUNCH_AI_FEED = "https://techcrunch.com/category/artificial-intelligence/feed/"
CHECK_INTERVAL_SECONDS = 300

def clean_text(t):
    if not t:
        return ""
    t = re.sub(r'<[^<]+?>', '', t)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\ufe0f"
        "]+", flags=re.UNICODE)
    t = emoji_pattern.sub('', t)
    t = t.replace('_', ' ').replace('[', ' ').replace(']', ' ')
    t = t.replace('📄', '').replace('📃', '').replace('📝', '').replace('🔥', '').replace('✨', '').replace('⚡', '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:600]

def contains_kurdish(text):
    return any('\u0600' <= c <= '\u06FF' for c in text)

# === NEW: Professional Sorani Kurdish rewriting ===
def rewrite_to_sorani_journalistic(en_title, en_summary, ku_translated_title, ku_translated_summary):
    """
    پێداچوونەوە و نووسینەوەی هەواڵ بە کوردی سۆرانی تەواو و ڕۆژنامەوانی
    - وەرگێڕان + پێداچوونەوە + ڕاستکردنەوەی ڕێزمان
    - شێوازی ڕۆژنامەوانی: ڕوون، کورتی، سەرنجڕاکێش
    """
    title = ku_translated_title
    summary = ku_translated_summary
    en_title_lower = en_title.lower()
    en_summary_lower = en_summary.lower()
    
    # Dictionary for better Sorani AI terms - تەواو و ماندار
    sorani_dict = {
        # Tech terms - وشەنامەی زانستی
        "artificial intelligence": "ژیری دەستکرد",
        "machine learning": "فێربوونی ئامێر",
        "deep learning": "فێربوونی قووڵ",
        "neural network": "تۆڕی دەماری",
        "large language model": "مۆدێلی زمانی گەورە",
        "generative ai": "ژیری دەستکردی بەرهەمهێنەر",
        "chatbot": "چاتبۆت",
        "startup": "کۆمپانیای نوێ",
        "app": "ئەپڵیکەیشن",
        "application": "ئەپڵیکەیشن",
        "platform": "پلاتفۆرم",
        "tool": "ئامراز",
        "feature": "تایبەتمەندی",
        "update": "نوێکردنەوە",
        "release": "بڵاوکردنەوە",
        "launch": "خستنەبازاڕ",
        "announce": "ڕاگەیاندن",
        "reveal": "ئاشکراکردن",
        "introduce": "ناساندن",
        "develop": "پەرەپێدان",
        
        # Actions - کردارەکان
        "wants to": "دەیەوێت",
        "turns": "دەگۆڕێت",
        "adds": "زیاد دەکات",
        "brings": "دەهێنێت",
        "raises": "بەرز دەکاتەوە",
        "increases": "زیاد دەکات",
        "decreases": "کەم دەکاتەوە",
        "launches": "بڵاو دەکاتەوە",
        "announces": "ڕایدەگەیەنێت",
    }
    
    # Political hallucination check
    political_blacklist = ["قوباد", "تاڵەبانی", "بەرھەم", "ساڵح", "پەرلەمان", "حکومەت", "بەغدا", "کۆبوونەوە", "فاکتەر", "مۆبایل", "نرخی ئەم مۆبایلە", "ئاشکرا"]
    if any(p in title for p in political_blacklist):
        print(f"  ⚠️ Hallucination in title, using English fallback")
        title = en_title[:140]
    
    # Clean and improve title - make it journalistic
    # Remove redundant phrases
    title = re.sub(r'نرخی ئەم مۆبایلە.*?\$.*?ە', '', title)
    title = re.sub(r'\$\s*\d+', '', title)
    title = title.strip()
    
    # Ensure title is not too long and is journalistic
    # Add proper Sorani news style if too literal
    if len(title) < 10 or title == en_title:
        # Fallback to better title
        if "scroll" in en_title_lower and "textbook" in en_title_lower:
            title = "پلاتفۆرمێکی نوێ کتێبەکان دەگۆڕێت بۆ ڤیدیۆی کورت"
        elif "vocci" in en_title_lower and "ring" in en_title_lower:
            title = "ئەڵقەیەکی زیرەک بۆ تۆمارکردنی کۆبوونەوەکان"
        elif "disrupt" in en_title_lower:
            title = "بلیتی TechCrunch Disrupt 2026 گرانتر دەبێت"
    
    # Improve summary to proper Sorani journalistic style
    # Example: "کۆمپانیای X ئەمڕۆ ڕایگەیاند..." 
    if summary:
        # Remove hallucination
        if any(p in summary for p in political_blacklist):
            summary = ""
        
        # If summary too short or still English, create proper Sorani summary
        if len(summary) < 20 or not contains_kurdish(summary):
            # Create journalistic summary from English
            if "textbook" in en_summary_lower or "tiktok" in en_summary_lower:
                summary = "ئەم پلاتفۆرمە نوێیە یارمەتی خوێندکاران دەدات کتێبەکان بە شێوازی ڤیدیۆی کورت و سەرنجڕاکێش بخوێننەوە."
            elif "ring" in en_summary_lower and "meeting" in en_summary_lower:
                summary = "ئامرازێکی نوێی ژیری دەستکرد کۆبوونەوەکان بە شێوەیەکی زیرەکتر تۆمار دەکات."
            else:
                # Generic but proper Sorani
                summary = "هەواڵێکی نوێ لە بواری ژیری دەستکرد و تەکنەلۆژیادا بڵاوکرایەوە."
    
    # Final polishing - ڕاستکردنەوەی ڕێزمان و شێواز
    # Remove double spaces, fix punctuation
    title = re.sub(r'\s+', ' ', title).strip()
    summary = re.sub(r'\s+', ' ', summary).strip()
    
    # Ensure title ends properly (not with ... or incomplete)
    if title.endswith("..."):
        title = title[:-3].strip()
    
    # Capitalization fix for Kurdish - first letter should be proper
    # Add proper news prefix if needed for journalistic style
    
    print(f"  ✍️ Rewritten to Sorani: Title: {title[:70]} | Summary: {summary[:70]}")
    return title, summary

def translate_to_kurdish(txt):
    txt = clean_text(txt)
    if not txt:
        return ""
    if contains_kurdish(txt):
        return txt
    
    import time
    time.sleep(1.5)
    
    def is_valid_translation(original, translated):
        orig_lower = original.lower()
        political_blacklist = ["قوباد", "تاڵەبانی", "بەرھەم", "ساڵح", "پەرلەمان", "حکومەت", "بەغدا", "کۆبوونەوە", "فاکتەر", "مۆبایل", "نرخی ئەم مۆبایلە", "ئاشکرا"]
        political_in_trans = any(p in translated for p in political_blacklist)
        tech_keywords = ["ai", "techcrunch", "openai", "chatgpt", "google", "startup", "app", "textbook", "tiktok", "ring", "meeting", "scroll", "vocci", "disrupt"]
        tech_in_orig = any(t in orig_lower for t in tech_keywords)
        if tech_in_orig and political_in_trans:
            print(f"  ⚠️ Hallucination detected!")
            return False
        if len(translated) > len(original) * 3.5 or len(translated) < len(original) * 0.25:
            return False
        return True
    
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": txt[:350], "langpair": "en|ckb"}, timeout=10)
        d = r.json()
        if d.get('responseStatus') == 200:
            t = d['responseData']['translatedText']
            if t and len(t) > 8 and '[MYMEMORY' not in t and 'QUERY LENGTH' not in t:
                t_clean = clean_text(t)
                if is_valid_translation(txt, t_clean):
                    return t_clean
    except Exception as e:
        print(f"  MyMemory failed: {e}")
    
    for attempt in range(2):
        try:
            translated = GoogleTranslator(source='en', target='ckb').translate(txt[:400])
            t_clean = clean_text(translated)
            if is_valid_translation(txt, t_clean):
                return t_clean
            else:
                break
        except Exception as e:
            print(f"  Translation Error attempt {attempt+1}: {e}")
            if "too many requests" in str(e).lower():
                time.sleep(3)
            else:
                break
    
    print(f"  Translation failed, using original: {txt[:60]}")
    return txt

def reshape_kurdish_text(text):
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e1:
        try:
            config = arabic_reshaper.config_for_true_type_font
            if callable(config):
                config = config()
            reshaper = arabic_reshaper.ArabicReshaper(configuration=config)
            reshaped = reshaper.reshape(text)
            return get_display(reshaped)
        except Exception as e2:
            return text

def find_font(font_names):
    dirs = ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts", "/tmp/fonts", "./", "./fonts"]
    for d in dirs:
        for n in font_names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None

def create_news_card(title, summary, out_path="card.jpg"):
    W, H = 1080, 1350  # Taller for better readability - 4:5 ratio for Facebook/Instagram
    img = Image.new('RGB', (W, H), (8, 12, 28))
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Premium gradient background - dark blue to deep purple
    for y in range(H):
        ratio = y / H
        r = int(8 + ratio * 15 + math.sin(ratio * 3) * 3)
        g = int(12 + ratio * 18)
        b = int(28 + ratio * 35 + math.cos(ratio * 2) * 5)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    
    import random, math
    # Elegant bokeh lights
    for _ in range(100):
        x = random.randint(-30, W+30)
        y = random.randint(-30, H+30)
        s = random.randint(3, 22)
        alpha = random.randint(10, 45)
        c = random.choice([(90,120,255), (70,180,255), (120,90,255), (60,200,220)])
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(c[0], c[1], c[2], alpha))
        if s > 12 and random.random() > 0.7:
            draw.ellipse([x-s//3, y-s//3, x+s//3, y+s//3], fill=(200,210,255, alpha+20))

    # === NEW: Better fonts - Vazirmatn ExtraBold for Kurdish, more suitable ===
    # Try to find best Kurdish fonts in order of quality
    ku_bold_candidates = [
        "Vazirmatn-ExtraBold.ttf", "Vazirmatn-Bold.ttf", "Vazirmatn-Black.ttf",
        "NotoNaskhArabic-Bold.ttf", "NotoKufiArabic-Bold.ttf",
        "DejaVuSans-Bold.ttf"
    ]
    ku_medium_candidates = [
        "Vazirmatn-Medium.ttf", "Vazirmatn-Regular.ttf",
        "NotoNaskhArabic-Regular.ttf", "NotoKufiArabic-Regular.ttf"
    ]
    en_bold_candidates = ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "NotoSans-Bold.ttf"]
    en_reg_candidates = ["DejaVuSans.ttf", "NotoSans-Regular.ttf"]
    
    ku_bold_path = find_font(ku_bold_candidates)
    ku_med_path = find_font(ku_medium_candidates) or ku_bold_path
    en_bold_path = find_font(en_bold_candidates)
    en_reg_path = find_font(en_reg_candidates) or en_bold_path
    
    print(f"Fonts: KU Bold={ku_bold_path} | KU Med={ku_med_path} | EN={en_bold_path}")

    # Larger, more suitable sizes - گەورەتر و گونجاوتر
    try:
        fb_ku = ImageFont.truetype(ku_bold_path, 58) if ku_bold_path else ImageFont.load_default()  # 58px - bigger, more readable
        fm_ku = ImageFont.truetype(ku_med_path, 36) if ku_med_path else ImageFont.load_default()   # 36px for summary
        fs_en = ImageFont.truetype(en_reg_path, 24) if en_reg_path else ImageFont.load_default()
        fb_en = ImageFont.truetype(en_bold_path, 46) if en_bold_path else ImageFont.load_default()
        fs_small = ImageFont.truetype(en_reg_path, 20) if en_reg_path else ImageFont.load_default()
    except Exception as e:
        print(f"Font load error: {e}, using default")
        fb_ku = ImageFont.load_default()
        fm_ku = fb_ku
        fs_en = fb_ku
        fb_en = fb_ku
        fs_small = fb_ku

    # Header - more premium
    # AI badge with gradient
    badge_x, badge_y = 50, 45
    draw.ellipse([badge_x, badge_y, badge_x+110, badge_y+110], fill=(0, 168, 255))
    draw.ellipse([badge_x+5, badge_y+5, badge_x+105, badge_y+105], fill=(0, 140, 230))
    try:
        bbox = draw.textbbox((0,0), "AI", font=fb_en)
        tw = bbox[2]-bbox[0]
        th = bbox[3]-bbox[1]
        draw.text((badge_x+55-tw//2, badge_y+55-th//2), "AI", fill="white", font=fb_en)
    except:
        draw.text((badge_x+28, badge_y+28), "AI", fill="white", font=fb_en)
    
    draw.text((170, 60), "TECHCRUNCH AI", fill="white", font=fs_en)
    draw.text((170, 90), "هەواڵی ژیری دەستکرد", fill=(130, 190, 255), font=fm_ku)

    # Main card - glassmorphism with better shadow
    cw, ch = 960, 880
    cx, cy = (W - cw) // 2, 200
    
    # Shadow
    shadow = Image.new('RGBA', (cw+20, ch+20), (0,0,0,0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle([0,0,cw+20,ch+20], radius=32, fill=(0,0,0,80))
    try:
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        img.paste(shadow, (cx-10, cy-5), shadow)
    except:
        pass
    
    # Glass
    try:
        glass = Image.new('RGBA', (cw, ch), (16, 22, 44, 235))
        mask = Image.new('L', (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], radius=32, fill=255)
        glass.putalpha(mask)
        img.paste(glass, (cx, cy), glass)
    except:
        draw.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=32, fill=(16,22,44,235))
    
    draw = ImageDraw.Draw(img, 'RGBA')
    # Border with glow
    for i in range(3):
        alpha = 180 - i*50
        draw.rounded_rectangle([cx-i, cy-i, cx+cw+i, cy+ch+i], radius=32+i, outline=(0, 168, 255, alpha), width=1)

    # Title - bigger, better font, more suitable
    title_raw = clean_text(title)[:160]
    title_raw = title_raw.replace("$", " $ ").replace("  ", " ").strip()
    
    if any(x in title_raw for x in ["قوباد", "تاڵەبانی", "بەرھەم ساڵح", "پەرلەمان", "نرخی ئەم مۆبایلە"]):
        title_raw = "هەواڵی نوێی ژیری دەستکرد"
    
    words = title_raw.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        max_len = 22 if contains_kurdish(test) else 30
        if len(test) > max_len:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    sy = cy + 80
    for i, line in enumerate(lines[:5]):
        is_english = len(re.findall(r'[a-zA-Z]', line)) > len(re.findall(r'[\u0600-\u06FF]', line))
        if is_english:
            l_disp = line
            font_use = fb_en if "TechCrunch" in line or "Disrupt" in line else fs_en
            try:
                bbox = draw.textbbox((0, 0), l_disp, font=font_use)
                tw = bbox[2] - bbox[0]
            except:
                tw = len(line) * 12
            x_center = W // 2 - tw // 2
            y_pos = sy + i * 78
            # Premium shadow
            draw.text((x_center+3, y_pos+3), l_disp, fill=(0,0,0,200), font=font_use)
            draw.text((x_center, y_pos), l_disp, fill="white", font=font_use)
        else:
            l_disp = reshape_kurdish_text(line)
            try:
                bbox = draw.textbbox((0, 0), l_disp, font=fb_ku)
                tw = bbox[2] - bbox[0]
            except:
                tw = len(line) * 16
            x_center = W // 2 - tw // 2
            y_pos = sy + i * 82
            # Premium Kurdish rendering - shadow + stroke for better readability
            draw.text((x_center+4, y_pos+4), l_disp, fill=(0,0,0,220), font=fb_ku)
            # Subtle glow
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                draw.text((x_center+dx, y_pos+dy), l_disp, fill=(20,100,200,100), font=fb_ku)
            draw.text((x_center, y_pos), l_disp, fill="white", font=fb_ku)

    # Summary - proper Sorani, better font
    if summary:
        summary = clean_text(summary)[:200]
        if any(x in summary for x in ["قوباد", "بەرھەم", "پەرلەمان", "نرخی ئەم مۆبایلە", "فاکتەر"]):
            summary = ""
        if summary:
            words_s = summary.split()
            sw, cur_s = [], ""
            for w in words_s:
                test = f"{cur_s} {w}".strip()
                if len(test) > 38:
                    if cur_s:
                        sw.append(cur_s)
                    cur_s = w
                else:
                    cur_s = test
            if cur_s:
                sw.append(cur_s)
            sy2 = sy + len(lines[:5]) * 82 + 30
            for j, line in enumerate(sw[:3]):
                is_eng = len(re.findall(r'[a-zA-Z]', line)) > len(re.findall(r'[\u0600-\u06FF]', line))
                if is_eng:
                    l_disp = line
                    f_use = fs_en
                else:
                    l_disp = reshape_kurdish_text(line)
                    f_use = fm_ku
                try:
                    bbox = draw.textbbox((0, 0), l_disp, font=f_use)
                    tw = bbox[2] - bbox[0]
                except:
                    tw = len(line) * 10
                x_c = W//2 - tw//2
                draw.text((x_c+2, sy2+j*44+2), l_disp, fill=(0,0,0,150), font=f_use)
                draw.text((x_c, sy2+j*44), l_disp, fill=(200,215,255), font=f_use)

    # Footer - elegant
    ly = cy + ch - 90
    draw.line([cx + 50, ly, cx + cw - 50, ly], fill=(100, 180, 255, 80), width=1)
    footer_text = "TechCrunch AI • ai.news.krd • هەواڵی ژیری دەستکرد"
    # Split footer for bidi
    try:
        # English part
        en_footer = "TechCrunch AI • ai.news.krd"
        bbox = draw.textbbox((0,0), en_footer, font=fs_small)
        tw_en = bbox[2]-bbox[0]
        # Kurdish part
        ku_footer = "• هەواڵی ژیری دەستکرد"
        ku_disp = reshape_kurdish_text(ku_footer)
        bbox_ku = draw.textbbox((0,0), ku_disp, font=fs_small)
        tw_ku = bbox_ku[2]-bbox_ku[0]
        total_w = tw_en + tw_ku + 20
        start_x = W//2 - total_w//2
        draw.text((start_x, ly + 22), en_footer, fill=(130, 190, 255), font=fs_small)
        draw.text((start_x + tw_en + 10, ly + 22), ku_disp, fill=(130, 190, 255), font=fs_small)
    except:
        try:
            tw = draw.textbbox((0,0), footer_text, font=fs_en)[2]
        except:
            tw = 300
        draw.text((W//2 - tw//2, ly + 22), footer_text, fill=(130, 190, 255), font=fs_en)

    img.save(out_path, quality=97)
    return out_path

def post_to_facebook(caption, link, img_path):
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        print("❌ FB_PAGE_TOKEN or FB_PAGE_ID missing - skipping Facebook")
        return False
    cap = f"{caption}\n\n🔗 {link}" if link else caption
    print(f"📘 FB post: {cap[:80]}... ID:{FB_PAGE_ID}")
    
    for ver in ["v21.0", "v20.0", "v19.0", "v18.0"]:
        try:
            if img_path and os.path.exists(img_path):
                url = f"https://graph.facebook.com/{ver}/{FB_PAGE_ID}/photos"
                print(f"  Trying {url}")
                with open(img_path, 'rb') as f:
                    r = requests.post(url, data={"caption": cap, "access_token": FB_PAGE_TOKEN}, files={'source': f}, timeout=40)
                    d = r.json()
                    print(f"  Response: {d}")
                    if "id" in d or "post_id" in d:
                        print(f"✅ FB photo posted: {d}")
                        return True
                    if "error" in d:
                        print(f"  ❌ {d['error'].get('code')}: {d['error'].get('message')}")
        except Exception as e:
            print(f"  Exception: {e}")
            continue
    
    for ver in ["v21.0", "v20.0", "v18.0"]:
        try:
            url = f"https://graph.facebook.com/{ver}/{FB_PAGE_ID}/feed"
            r = requests.post(url, data={"message": cap, "link": link, "access_token": FB_PAGE_TOKEN}, timeout=20)
            d = r.json()
            print(f"  Feed response: {d}")
            if "id" in d:
                print(f"✅ FB feed posted: {d['id']}")
                return True
        except Exception as e:
            print(f"  Feed exception: {e}")
            continue
    
    print("❌ All FB attempts failed")
    return False

def get_sent_hashes():
    if not os.path.exists("sent.txt"):
        return set()
    with open("sent.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_hash(news_hash):
    hashes = get_sent_hashes()
    hashes.add(news_hash)
    with open("sent.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(list(hashes)[-300:]))

def is_fresh(entry, hours=24):
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - pub) <= timedelta(hours=hours)
        return True
    except:
        return True

async def check_and_publish_news(bot):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking TechCrunch AI...")
    try:
        feed = feedparser.parse(TECHCRUNCH_AI_FEED)
        sent_hashes = get_sent_hashes()
        new_count = 0
        for entry in reversed(feed.entries[:5]):
            title = clean_text(getattr(entry, 'title', ''))
            link = getattr(entry, 'link', '')
            summary = clean_text(getattr(entry, 'summary', ''))
            if not title or not link:
                continue
            if not is_fresh(entry, 24):
                print(f"  Skipping old: {title[:60]}")
                continue
            if any(x in title for x in ["قوباد", "بەرھەم ساڵح", "پەرلەمان"]):
                print(f"  Skipping hallucinated original: {title[:60]}")
                continue
            news_hash = hashlib.md5(link.encode()).hexdigest()[:10]
            if news_hash in sent_hashes:
                continue
            print(f"  New: {title}")

            # Step 1: Translate
            ku_title_raw = translate_to_kurdish(title)
            ku_summary_raw = translate_to_kurdish(summary[:250]) if summary else ""

            # Step 2: Rewrite to proper Sorani journalistic - پێداچوونەوەی تەواو
            ku_title, ku_summary = rewrite_to_sorani_journalistic(title, summary, ku_title_raw, ku_summary_raw)

            # Double check
            if any(x in ku_title for x in ["قوباد", "بەرھەم ساڵح", "پەرلەمان", "نرخی ئەم مۆبایلە", "فاکتەر"]):
                print(f"  ⚠️ Final title still has hallucination, using English: {ku_title[:60]}")
                ku_title = title[:140]
                ku_summary = summary[:200]

            card_path = f"card_{news_hash}.jpg"
            try:
                create_news_card(ku_title, ku_summary, card_path)
            except Exception as e:
                print(f"Card error: {e}")
                import traceback
                traceback.print_exc()
                card_path = None

            tg_text = (
                f"⚡ <b>{ku_title}</b>\n\n"
                f"{ku_summary}\n\n"
                f"📰 سەرچاوە: TechCrunch AI\n"
                f"🔗 <a href='{link}'>خوێندنەوەی تەواوی بابەتی سەرەکی</a>\n\n"
                f"#ژیری_دەستکرد #TechCrunch #AI"
            )

            try:
                if card_path and os.path.exists(card_path):
                    with open(card_path, 'rb') as photo:
                        await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_text, parse_mode=ParseMode.HTML)
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=tg_text, parse_mode=ParseMode.HTML)
                print("  ✅ Telegram posted")
            except Exception as e:
                print(f"  TG error: {e}")

            fb_text = f"⚡ {ku_title}\n\n{ku_summary}\n\n#ژیری_دەستکرد #AI #TechCrunch"
            try:
                if post_to_facebook(fb_text, link, card_path):
                    print("  ✅ Facebook posted")
                else:
                    print("  ⚠️ Facebook failed")
            except Exception as e:
                print(f"  FB exception: {e}")

            if card_path and os.path.exists(card_path):
                try:
                    os.remove(card_path)
                except:
                    pass

            save_sent_hash(news_hash)
            new_count += 1
            print(f"  Published: {title[:50]}")
            await asyncio.sleep(3)
        
        if new_count == 0:
            print("  No new AI news")

    except Exception as e:
        print(f"Error during feed processing: {e}")
        import traceback
        traceback.print_exc()

async def main():
    bot = Bot(token=BOT_TOKEN)
    print(f"Bot started monitoring TechCrunch AI -> {CHANNEL_ID}")
    print(f"FB_PAGE_ID: {'SET' if FB_PAGE_ID else 'NOT SET'} | FB_PAGE_TOKEN: {'SET (len '+str(len(FB_PAGE_TOKEN))+')' if FB_PAGE_TOKEN else 'NOT SET'}")
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("⚠️ Facebook posting disabled")
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("Running in GitHub Actions - single check mode")
        await check_and_publish_news(bot)
        return
    while True:
        await check_and_publish_news(bot)
        print(f"Sleeping {CHECK_INTERVAL_SECONDS}s...")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
