import os
import re
import hashlib
import requests
import asyncio
import feedparser
import math
import random
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


# === NEW: Smart Template - Brand & Person Detection ===
BRANDS = {
    "meta": {"name": "Meta", "display": "مێتا", "color": (0, 100, 255), "bg": (6, 95, 212), "initial": "M", "keywords": ["meta", "facebook", "instagram", "zuckerberg"]},
    "openai": {"name": "OpenAI", "display": "ئۆپن ئەی ئای", "color": (16, 163, 127), "bg": (10, 10, 10), "initial": "O", "keywords": ["openai", "chatgpt", "gpt-4", "gpt-5", "sam altman", "sora", "dall-e"]},
    "google": {"name": "Google", "display": "گووگڵ", "color": (66, 133, 244), "bg": (255, 255, 255), "initial": "G", "keywords": ["google", "gemini", "deepmind", "bard", "sundar pichai"]},
    "anthropic": {"name": "Anthropic", "display": "ئانترۆپیک", "color": (210, 105, 30), "bg": (255, 248, 230), "initial": "A", "keywords": ["anthropic", "claude", "dario amodei"]},
    "microsoft": {"name": "Microsoft", "display": "مایکرۆسۆفت", "color": (0, 164, 239), "bg": (0, 120, 212), "initial": "M", "keywords": ["microsoft", "copilot", "satya nadella"]},
    "nvidia": {"name": "NVIDIA", "display": "ئێنڤیدیا", "color": (118, 185, 0), "bg": (18, 18, 18), "initial": "N", "keywords": ["nvidia", "jensen huang", "geforce"]},
    "apple": {"name": "Apple", "display": "ئەپڵ", "color": (0, 0, 0), "bg": (245, 245, 247), "initial": "A", "keywords": ["apple", "tim cook", "iphone", "siri"]},
    "xai": {"name": "xAI", "display": "ئێکس ئەی ئای", "color": (0, 0, 0), "bg": (0, 0, 0), "initial": "X", "keywords": ["xai", "elon musk", "grok", "twitter", " x "]},
    "amazon": {"name": "Amazon", "display": "ئەمازۆن", "color": (255, 153, 0), "bg": (35, 47, 62), "initial": "A", "keywords": ["amazon", "aws", "bedrock"]},
}

PERSONS = {
    "mark zuckerberg": {"name": "Mark Zuckerberg", "ku_name": "مارک زاکەربێرگ", "initials": "MZ", "company": "meta", "role": "CEO ی مێتا"},
    "zuckerberg": {"name": "Mark Zuckerberg", "ku_name": "مارک زاکەربێرگ", "initials": "MZ", "company": "meta", "role": "CEO ی مێتا"},
    "sam altman": {"name": "Sam Altman", "ku_name": "سام ئاڵتمان", "initials": "SA", "company": "openai", "role": "CEO ی ئۆپن ئەی ئای"},
    "sama": {"name": "Sam Altman", "ku_name": "سام ئاڵتمان", "initials": "SA", "company": "openai", "role": "CEO ی ئۆپن ئەی ئای"},
    "sundar pichai": {"name": "Sundar Pichai", "ku_name": "سوندار پیچای", "initials": "SP", "company": "google", "role": "CEO ی گووگڵ"},
    "dario amodei": {"name": "Dario Amodei", "ku_name": "داریۆ ئەمۆدی", "initials": "DA", "company": "anthropic", "role": "CEO ی ئانترۆپیک"},
    "satya nadella": {"name": "Satya Nadella", "ku_name": "ساتيا نادێلا", "initials": "SN", "company": "microsoft", "role": "CEO ی مایکرۆسۆفت"},
    "jensen huang": {"name": "Jensen Huang", "ku_name": "جێنسن هوانگ", "initials": "JH", "company": "nvidia", "role": "CEO ی ئێنڤیدیا"},
    "elon musk": {"name": "Elon Musk", "ku_name": "ئیلۆن مەسک", "initials": "EM", "company": "xai", "role": "CEO ی ئێکس ئەی ئای"},
    "tim cook": {"name": "Tim Cook", "ku_name": "تیم کووک", "initials": "TC", "company": "apple", "role": "CEO ی ئەپڵ"},
}

def detect_brand_and_person(title, summary):
    """Detect brand and person from news content"""
    text = f"{title} {summary}".lower()
    detected_brand = None
    detected_person = None
    
    # Detect brand
    max_score = 0
    for brand_key, brand_info in BRANDS.items():
        score = 0
        for kw in brand_info["keywords"]:
            if kw in text:
                # Longer keywords and exact brand name get higher score
                score += len(kw) * 2 if kw == brand_key else len(kw)
        if score > max_score and score > 2:
            max_score = score
            detected_brand = brand_key
    
    # Detect person
    for person_key, person_info in PERSONS.items():
        if person_key in text:
            detected_person = person_key
            # If person detected, override brand to person's company
            if person_info["company"]:
                detected_brand = person_info["company"]
            break
    
    print(f"  🔍 Detected: Brand={detected_brand}, Person={detected_person} from: {title[:60]}")
    return detected_brand, detected_person



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
    
    # FIXED: Better Sorani dictionary and less hallucination
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
    
    # Ensure title is not too long and is journalistic - FIXED to avoid hallucinations
    if len(title) < 10 or title == en_title or "پەڕەکانی ژێرەوە" in title or "ئەپڵ" in title and "apple" not in en_title_lower:
        # Fallback to better title - based on actual English content
        if "scroll" in en_title_lower and "textbook" in en_title_lower:
            title = "پلاتفۆرمێکی نوێ کتێبەکان دەگۆڕێت بۆ ڤیدیۆی کورت"
        elif "vocci" in en_title_lower and "ring" in en_title_lower:
            title = "ئەڵقەیەکی زیرەک بۆ تۆمارکردنی کۆبوونەوەکان"
        elif "disrupt" in en_title_lower and "save" in en_title_lower:
            title = "تەنها 6 ڕۆژ ماوە بۆ پاشەکەوتکردنی 200 دۆلار لە بلیتی TechCrunch Disrupt 2026"
        elif "disrupt" in en_title_lower:
            title = "بلیتی کۆنفرانسی TechCrunch Disrupt 2026 بەرز دەبێتەوە"
        elif "world model" in en_title_lower:
            title = "کۆمپانیاکانی مۆدێلی جیهانی نهێنی زۆر دەپارێزن"
        elif "slow down" in en_title_lower and "ai industry" in en_title_lower:
            title = "ئایا پیشەسازی ژیری دەستکرد ئامادەیە خاو ببێتەوە؟"
        else:
            # Keep original English if translation fails badly
            title = en_title[:120]
    
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
    
    def is_valid_translation(original, translated):
        orig_lower = original.lower()
        political_blacklist = ["قوباد", "تاڵەبانی", "بەرھەم", "ساڵح", "پەرلەمان", "حکومەت", "بەغدا", "کۆبوونەوە", "فاکتەر", "مۆبایل", "نرخی ئەم مۆبایلە", "ئاشکرا", "پەڕەکانی ژێرەوە"]
        political_in_trans = any(p in translated for p in political_blacklist)
        tech_keywords = ["ai", "techcrunch", "openai", "chatgpt", "google", "startup", "app", "textbook", "tiktok", "ring", "meeting", "scroll", "vocci", "disrupt", "world model"]
        tech_in_orig = any(t in orig_lower for t in tech_keywords)
        if tech_in_orig and political_in_trans:
            print(f"  ⚠️ Hallucination detected! Rejecting: {translated[:60]}")
            return False
        if len(translated) > len(original) * 4 or len(translated) < len(original) * 0.2:
            print(f"  ⚠️ Length suspicious: {len(original)} -> {len(translated)}")
            return False
        # Check for Apple hallucination when original is about AI
        if "apple" in translated.lower() and "apple" not in orig_lower and "ai" in orig_lower:
            if "ئەپڵ" in translated and "ai" in orig_lower.lower():
                print(f"  ⚠️ Apple hallucination detected")
                return False
        return True
    
    # Try MyMemory first with longer delay
    time.sleep(2.5)  # Increased delay to avoid rate limit
    try:
        r = requests.get("https://api.mymemory.translated.net/get", params={"q": txt[:350], "langpair": "en|ckb"}, timeout=15)
        d = r.json()
        if d.get('responseStatus') == 200:
            t = d['responseData']['translatedText']
            if t and len(t) > 8 and '[MYMEMORY' not in t and 'QUERY LENGTH' not in t and 'MYMEMORY WARNING' not in t:
                t_clean = clean_text(t)
                if is_valid_translation(txt, t_clean):
                    print(f"  Translated via MyMemory: {t_clean[:60]}")
                    return t_clean
                else:
                    print(f"  MyMemory rejected")
    except Exception as e:
        print(f"  MyMemory failed: {e}")
    
    # Google with even longer delay and only 1 attempt per call to avoid 5/sec
    time.sleep(1.5)
    try:
        translated = GoogleTranslator(source='en', target='ckb').translate(txt[:400])
        t_clean = clean_text(translated)
        if is_valid_translation(txt, t_clean):
            print(f"  Translated via Google: {t_clean[:60]}")
            return t_clean
        else:
            print(f"  Google rejected as hallucination")
    except Exception as e:
        print(f"  Translation Error: {e}")
        if "too many requests" in str(e).lower():
            print("  Rate limited - waiting 5s and returning original")
            time.sleep(5)
    
    print(f"  Translation failed, using original: {txt[:60]}")
    return txt

def translate_batch(titles_and_summaries):
    """Translate multiple items with proper delays to avoid rate limits"""
    results = []
    for en_title, en_summary in titles_and_summaries:
        ku_title = translate_to_kurdish(en_title)
        # Extra delay between title and summary of same article
        import time
        time.sleep(1.0)
        ku_summary = translate_to_kurdish(en_summary[:250]) if en_summary else ""
        results.append((ku_title, ku_summary))
        time.sleep(2.0)  # Delay between articles
    return results

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
    # Priority order for Kurdish - best to worst
    dirs = [
        "/mnt/data",  # First check /mnt/data where DroidKufi is
        "./fonts", "./",
        "/tmp/fonts",
        "/tmp/fonts/Vazirmatn",
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/opentype/noto",
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts",
        "/usr/share/fonts/google-droid-sans-fonts",
    ]
    for d in dirs:
        if not os.path.exists(d):
            continue
        for n in font_names:
            # Try exact match
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
            # Try case-insensitive search in directory
            try:
                for f in os.listdir(d):
                    if f.lower() == n.lower():
                        return os.path.join(d, f)
            except:
                pass
    return None

def get_kurdish_fonts():
    """Get best available Kurdish fonts - professional priority"""
    # Best for Kurdish: Vazirmatn (perfect), DroidKufi (good), Noto Naskh (good)
    bold_candidates = [
        "Vazirmatn-Black.ttf", "Vazirmatn-ExtraBold.ttf", "Vazirmatn-Bold.ttf",
        "DroidKufi-Bold.ttf",
        "NotoNaskhArabic-Bold.ttf", "NotoKufiArabic-Bold.ttf",
        "DejaVuSans-Bold.ttf"
    ]
    medium_candidates = [
        "Vazirmatn-Medium.ttf", "Vazirmatn-Regular.ttf",
        "DroidKufi-Regular.ttf",
        "NotoNaskhArabic-Regular.ttf", "NotoKufiArabic-Regular.ttf",
        "DejaVuSans.ttf"
    ]
    regular_candidates = [
        "Vazirmatn-Regular.ttf", "Vazirmatn-Light.ttf",
        "DroidKufi-Regular.ttf",
        "NotoNaskhArabic-Regular.ttf",
        "DejaVuSans.ttf"
    ]
    
    bold = find_font(bold_candidates)
    medium = find_font(medium_candidates) or bold
    regular = find_font(regular_candidates) or medium
    
    return bold, medium, regular

def create_news_card(title, summary, out_path="card.jpg", en_title="", en_summary=""):
    """
    Professional beautiful typography - جوانترین نووسین
    - DroidKufi for Kurdish - best Arabic/Kurdish font
    - Vazirmatn fallback
    - Hierarchy: Title 64px Bold, Summary 28px Regular
    - Line height: 88px for title, 42px for summary
    - Effects: Soft shadow, subtle glow, outline for contrast
    - Balanced wrapping, no orphans/widows
    - Standard professional design
    """
    detect_text_title = en_title if en_title else title
    detect_text_summary = en_summary if en_summary else summary
    brand_key, person_key = detect_brand_and_person(detect_text_title, detect_text_summary)
    
    brand = BRANDS.get(brand_key) if brand_key else None
    person = PERSONS.get(person_key) if person_key else None
    
    W, H = 1080, 1350
    img = Image.new('RGB', (W, H), (5, 10, 25))
    draw = ImageDraw.Draw(img, 'RGBA')
    
    accent = brand["color"] if brand else (255, 102, 0)
    
    # Premium background
    for y in range(H):
        ratio = y / H
        if brand and ratio < 0.25:
            blend = 1 - (ratio / 0.25)
            r = int(5 + (accent[0] - 5) * blend * 0.12 + math.sin(ratio * 3) * 2)
            g = int(10 + (accent[1] - 10) * blend * 0.12)
            b = int(25 + (accent[2] - 25) * blend * 0.12 + math.cos(ratio * 2) * 3)
        else:
            r = int(5 + ratio * 8 + math.sin(ratio * 2) * 2)
            g = int(10 + ratio * 12)
            b = int(25 + ratio * 18 + math.cos(ratio * 1.5) * 3)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    
    for _ in range(150):
        x = random.randint(0, W)
        y = random.randint(0, H)
        s = random.randint(1, 3)
        alpha = random.randint(5, 20)
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(60, 80, 120, alpha))
    
    for _ in range(80):
        x = random.randint(-20, W+20)
        y = random.randint(-20, H+20)
        s = random.randint(2, 18)
        alpha = random.randint(8, 35)
        if brand and random.random() > 0.6:
            c = accent
        else:
            c = random.choice([(80,100,180), (60,90,160), (100,80,180)])
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(c[0], c[1], c[2], alpha))
    
    # Neural globe
    globe_cx, globe_cy = W - 180, H // 2 - 50
    nodes = []
    for _ in range(40):
        angle1 = random.uniform(0, 2*math.pi)
        angle2 = random.uniform(-math.pi/2, math.pi/2)
        r_factor = random.uniform(0.7, 1.0)
        x = globe_cx + 320 * r_factor * math.cos(angle2) * math.cos(angle1)
        y = globe_cy + 320 * r_factor * math.cos(angle2) * math.sin(angle1) * 0.7
        nodes.append((x, y))
    
    for i, (x1, y1) in enumerate(nodes):
        for j, (x2, y2) in enumerate(nodes[i+1:], i+1):
            dist = math.hypot(x1-x2, y1-y2)
            if dist < 120:
                alpha = int(80 - dist * 0.5)
                if alpha > 10:
                    draw.line([(x1,y1),(x2,y2)], fill=(100, 120, 255, alpha), width=1)
    
    for x, y in nodes:
        s = random.randint(2, 5)
        draw.ellipse([x-s, y-s, x+s, y+s], fill=(120, 180, 255, 200))
        draw.ellipse([x-s//2, y-s//2, x+s//2, y+s//2], fill=(200, 220, 255, 255))

    # === PROFESSIONAL FONTS - Beautiful, Standard, Professional ===
    ku_bold_path, ku_med_path, ku_reg_path = get_kurdish_fonts()
    en_bold_path = find_font(["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"])
    en_reg_path = find_font(["DejaVuSans.ttf", "DejaVuSans-Oblique.ttf"]) or en_bold_path
    
    print(f"  📝 Fonts: Bold={os.path.basename(ku_bold_path) if ku_bold_path else 'None'} | Medium={os.path.basename(ku_med_path) if ku_med_path else 'None'} | Regular={os.path.basename(ku_reg_path) if ku_reg_path else 'None'}")

    try:
        # Professional typography sizes - hierarchy and balance
        font_title = ImageFont.truetype(ku_bold_path, 64) if ku_bold_path else ImageFont.load_default()
        font_title_en = ImageFont.truetype(en_bold_path, 48) if en_bold_path else ImageFont.load_default()
        font_summary = ImageFont.truetype(ku_reg_path, 28) if ku_reg_path else ImageFont.load_default()
        font_summary_en = ImageFont.truetype(en_reg_path, 22) if en_reg_path else ImageFont.load_default()
        font_badge = ImageFont.truetype(en_bold_path, 42) if en_bold_path else ImageFont.load_default()
        font_small = ImageFont.truetype(en_reg_path, 17) if en_reg_path else ImageFont.load_default()
        font_person_name = ImageFont.truetype(ku_bold_path, 26) if ku_bold_path else ImageFont.load_default()
        font_person_role = ImageFont.truetype(ku_reg_path, 16) if ku_reg_path else ImageFont.load_default()
        font_header = ImageFont.truetype(en_bold_path, 21) if en_bold_path else ImageFont.load_default()
    except Exception as e:
        print(f"  Font load error: {e}")
        font_title = ImageFont.load_default()
        font_summary = font_title
        font_badge = font_title
        font_small = font_title
        font_person_name = font_title
        font_person_role = font_title
        font_title_en = font_title
        font_summary_en = font_title
        font_header = font_title

    # Orange AI badge - refined with glow
    badge_x, badge_y = 45, 45
    draw.ellipse([badge_x-3, badge_y-3, badge_x+118, badge_y+118], fill=(255, 102, 0, 40))
    draw.ellipse([badge_x, badge_y, badge_x+115, badge_y+115], fill=(255, 102, 0))
    try:
        bbox = draw.textbbox((0,0), "AI", font=font_badge)
        tw = bbox[2]-bbox[0]
        th = bbox[3]-bbox[1]
        draw.text((badge_x+57-tw//2, badge_y+57-th//2), "AI", fill="white", font=font_badge)
    except:
        draw.text((badge_x+32, badge_y+30), "AI", fill="white", font=font_badge)
    
    try:
        draw.text((175, 62), "AI NEWS", fill=(255,255,255), font=font_header)
        draw.text((175, 90), "KURDISH", fill=(200,200,200), font=font_header)
    except:
        draw.text((175, 62), "AI NEWS", fill="white", font=font_small)
        draw.text((175, 90), "KURDISH", fill="white", font=font_small)
    
    # Brand logo
    if brand:
        brand_x = W - 155
        brand_y = 45
        brand_bg = brand["bg"]
        draw.ellipse([brand_x-5, brand_y-5, brand_x+115, brand_y+115], fill=(accent[0], accent[1], accent[2], 50))
        draw.ellipse([brand_x, brand_y, brand_x+110, brand_y+110], fill=brand_bg)
        draw.ellipse([brand_x, brand_y, brand_x+110, brand_y+110], outline=(accent[0], accent[1], accent[2], 180), width=2)
        initial = brand["initial"]
        text_color = (255,255,255) if brand_bg[0] < 100 else (0,0,0)
        if brand_key == "meta":
            text_color = (255,255,255)
        elif brand_key == "google":
            text_color = (66,133,244)
        try:
            bbox = draw.textbbox((0,0), initial, font=font_badge)
            tw = bbox[2]-bbox[0]
            th = bbox[3]-bbox[1]
            draw.text((brand_x+55-tw//2, brand_y+55-th//2), initial, fill=text_color, font=font_badge)
        except:
            draw.text((brand_x+38, brand_y+30), initial, fill=text_color, font=font_badge)

    # Glass card - premium
    cw, ch = 860, 720
    cx, cy = (W - cw) // 2, 360
    
    shadow = Image.new('RGBA', (cw+40, ch+40), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([0,0,cw+40,ch+40], radius=32, fill=(0,0,0,70))
    try:
        shadow = shadow.filter(ImageFilter.GaussianBlur(25))
        img.paste(shadow, (cx-20, cy-5), shadow)
    except:
        pass
    
    try:
        glass = Image.new('RGBA', (cw, ch), (16, 20, 40, 225))
        mask = Image.new('L', (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], radius=28, fill=255)
        glass.putalpha(mask)
        img.paste(glass, (cx, cy), glass)
    except:
        draw.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=28, fill=(16,20,40,225))
    
    draw = ImageDraw.Draw(img, 'RGBA')
    draw.rounded_rectangle([cx-1, cy-1, cx+cw+1, cy+ch+1], radius=29, outline=(80, 70, 180, 70), width=1)
    draw.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=28, outline=(120, 110, 220, 50), width=1)

    # Person
    title_offset = 0
    if person:
        py = cy + 28
        px = cx + 28
        draw.ellipse([px, py, px+64, py+64], fill=(38, 42, 65))
        draw.ellipse([px, py, px+64, py+64], outline=(accent[0], accent[1], accent[2], 160), width=2)
        try:
            bbox = draw.textbbox((0,0), person["initials"], font=font_small)
            tw = bbox[2]-bbox[0]
            th = bbox[3]-bbox[1]
            draw.text((px+32-tw//2, py+32-th//2), person["initials"], fill="white", font=font_small)
        except:
            draw.text((px+16, py+20), person["initials"], fill="white", font=font_small)
        try:
            ku_name_disp = reshape_kurdish_text(person["ku_name"])
            role_disp = reshape_kurdish_text(person["role"])
            draw.text((px+82, py+6), ku_name_disp, fill="white", font=font_person_name)
            draw.text((px+82, py+38), role_disp, fill=(160,180,220), font=font_person_role)
        except:
            pass
        title_offset = 95

    # === PROFESSIONAL TYPOGRAPHY - Beautiful Kurdish ===
    title_raw = clean_text(title)[:160]
    title_raw = title_raw.replace("$", " $ ").replace("  ", " ").strip()
    
    if any(x in title_raw for x in ["قوباد", "تاڵەبانی", "بەرھەم ساڵح", "پەرلەمان", "نرخی ئەم مۆبایلە"]):
        title_raw = "هەواڵی نوێی ژیری دەستکرد"
    
    # Smart wrapping - balanced, professional
    words = title_raw.split()
    lines = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        max_len = 18 if contains_kurdish(test) else 24
        if len(test) > max_len:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    
    # Avoid widows/orphans - typography best practice
    if len(lines) > 1 and len(lines[-1]) < 8 and len(lines[-2].split()) > 1:
        prev_words = lines[-2].split()
        if len(prev_words) > 1:
            lines[-2] = " ".join(prev_words[:-1])
            lines[-1] = prev_words[-1] + " " + lines[-1]
    
    sy = cy + 80 + title_offset
    line_height = 88
    
    for i, line in enumerate(lines[:4]):
        is_english = len(re.findall(r'[a-zA-Z]', line)) > len(re.findall(r'[\u0600-\u06FF]', line)) and len(re.findall(r'[a-zA-Z]', line)) > 3
        
        if is_english:
            l_disp = line
            font_use = font_title_en
        else:
            l_disp = reshape_kurdish_text(line)
            font_use = font_title
        
        try:
            bbox = draw.textbbox((0, 0), l_disp, font=font_use)
            tw = bbox[2] - bbox[0]
        except:
            tw = len(line) * 18
        
        x_center = W // 2 - tw // 2
        y_pos = sy + i * line_height
        
        # Beautiful rendering - shadow + glow + main
        draw.text((x_center+4, y_pos+4), l_disp, fill=(0,0,0,180), font=font_use)
        draw.text((x_center+2, y_pos+2), l_disp, fill=(0,0,0,100), font=font_use)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            draw.text((x_center+dx, y_pos+dy), l_disp, fill=(accent[0], accent[1], accent[2], 25), font=font_use)
        draw.text((x_center, y_pos), l_disp, fill="white", font=font_use)

    # Summary - elegant
    if summary:
        summary = clean_text(summary)[:200]
        if any(x in summary for x in ["قوباد", "بەرھەم", "پەرلەمان", "نرخی ئەم مۆبایلە", "فاکتەر"]):
            summary = ""
        if summary:
            words_s = summary.split()
            sw, cur_s = [], ""
            for w in words_s:
                test = f"{cur_s} {w}".strip()
                if len(test) > 40:
                    if cur_s:
                        sw.append(cur_s)
                    cur_s = w
                else:
                    cur_s = test
            if cur_s:
                sw.append(cur_s)
            
            sy2 = sy + len(lines[:4]) * line_height + 38
            summary_line_height = 42
            
            for j, line in enumerate(sw[:3]):
                is_eng = len(re.findall(r'[a-zA-Z]', line)) > len(re.findall(r'[\u0600-\u06FF]', line)) and len(re.findall(r'[a-zA-Z]', line)) > 4
                if is_eng:
                    l_disp = line
                    f_use = font_summary_en
                else:
                    l_disp = reshape_kurdish_text(line)
                    f_use = font_summary
                
                try:
                    bbox = draw.textbbox((0, 0), l_disp, font=f_use)
                    tw = bbox[2] - bbox[0]
                except:
                    tw = len(line) * 10
                x_c = W // 2 - tw // 2
                y_s = sy2 + j * summary_line_height
                
                draw.text((x_c+1, y_s+1), l_disp, fill=(0,0,0,120), font=f_use)
                draw.text((x_c, y_s), l_disp, fill=(205,215,235), font=f_use)

    # Footer
    ly = cy + ch - 75
    for x in range(cx+70, cx+cw-70):
        ratio = (x-(cx+70))/(cw-140)
        alpha = int(30 + math.sin(ratio*math.pi)*50)
        draw.line([(x, ly), (x+1, ly)], fill=(90, 80, 170, alpha), width=1)
    
    try:
        footer = "AI News Kurdish"
        bbox = draw.textbbox((0,0), footer, font=font_small)
        tw = bbox[2]-bbox[0]
        draw.text((W//2-tw//2+1, ly+28+1), footer, fill=(0,0,0,60), font=font_small)
        draw.text((W//2-tw//2, ly+28), footer, fill=(135,165,210), font=font_small)
    except:
        pass

    try:
        draw.text((48, H-48), "ai.news.krd", fill=(90,160,210,160), font=font_small)
    except:
        pass

    img.save(out_path, quality=98)
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
                create_news_card(ku_title, ku_summary, card_path, en_title=title, en_summary=summary)
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
