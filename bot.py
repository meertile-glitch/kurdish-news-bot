import textwrap
import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

def reshape_ku(text):
    """بۆ بەستنەوەی پیتە کوردییەکان و ڕاستکردنەوەی چەپ/ڕاست (RTL)"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def card(title, summary, out="card.jpg"):
    W, H = 1080, 1080
    base = create_beautiful_background(W, H)
    img = base.copy()
    draw = ImageDraw.Draw(img, 'RGBA')

    try:
        LAYOUT = ImageFont.Layout.RAQM
    except Exception:
        LAYOUT = None

    def find_font(names):
        dirs = ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/dejavu", "./", "./fonts"]
        for d in dirs:
            for n in names:
                p = os.path.join(d, n)
                if os.path.exists(p):
                    return p
        return None

    def load(p, size):
        try:
            return ImageFont.truetype(p, size, layout_engine=LAYOUT) if LAYOUT else ImageFont.truetype(p, size)
        except Exception:
            return ImageFont.load_default()

    en_bold = find_font(["DejaVuSans-Bold.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    en_reg = find_font(["DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ku_bold = find_font(["NotoKufiArabic-Bold.ttf", "NotoNaskhArabic-Bold.ttf", "Vazirmatn-Bold.ttf"]) or en_bold
    ku_reg = find_font(["NotoKufiArabic-Regular.ttf", "NotoNaskhArabic-Regular.ttf", "Vazirmatn-Regular.ttf"]) or en_reg

    fb_en = load(en_bold, 46)
    fs_en = load(en_reg, 22)
    fb_ku = load(ku_bold, 52)
    fr_ku = load(ku_reg, 32)

    # دیزاینی لۆگۆ
    x, y = 45, 40
    draw.ellipse([x, y, x + 100, y + 100], fill=(255, 108, 20))
    draw.text((x + 28, y + 22), "AI", fill="white", font=fb_en)
    draw.text((x + 130, y + 18), "AI NEWS", fill="white", font=fs_en)
    draw.text((x + 130, y + 44), "KURDISH", fill="white", font=fs_en)

    # دیزاینی کارتەکە (Glass effect)
    cw, ch = 880, 680
    cx, cy = (W - cw) // 2, (H - ch) // 2 + 40
    glass = Image.new('RGBA', (cw, ch), (18, 22, 48, 210))
    mask = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw, ch], radius=32, fill=255)
    glass.putalpha(mask)
    img.paste(glass, (cx, cy), glass)
    draw = ImageDraw.Draw(img, 'RGBA')

    # ------------------ بەشی سەرەکی چاککراوی دەق ------------------
    
    # ۱. سەرەتا دەقەکە wrap بکە بە بێ reshape
    title_clean = title[:130].strip()
    wr = textwrap.wrap(title_clean, width=28)[:4]
    
    sy = cy + 70
    for i, line in enumerate(wr):
        if not line.strip():
            continue
        
        # ۲. بەستنەوەی پیتەکان بۆ ئەم دێڕە دیاریکراوە
        shaped_line = reshape_ku(line)
        
        try:
            bbox = draw.textbbox((0, 0), shaped_line, font=fb_ku)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(shaped_line) * 20
            
        x_center = W // 2 - tw // 2
        y_pos = sy + i * 75
        
        # نووسینی دەقەکە لە ناوەڕاستی کارتەکە
        draw.text((x_center, y_pos), shaped_line, fill="white", font=fb_ku)

    # ۳. جێبەجێکردنی هەمان ڕێگە بۆ پوختەی هەواڵەکە (Summary)
    if summary:
        summary_clean = summary[:120].strip()
        sw = textwrap.wrap(summary_clean, width=38)[:2]
        sy2 = sy + len(wr) * 75 + 30
        
        for j, line in enumerate(sw):
            if not line.strip():
                continue
            
            shaped_summary_line = reshape_ku(line)
            
            try:
                bbox = draw.textbbox((0, 0), shaped_summary_line, font=fr_ku)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(shaped_summary_line) * 12
                
            x_center = W // 2 - tw // 2
            draw.text((x_center, sy2 + j * 42), shaped_summary_line, fill=(220, 225, 255), font=fr_ku)

    # ------------------------------------------------------------------

    # بەشی Footer
    ly = cy + ch - 100
    draw.line([cx + 60, ly, cx + cw - 60, ly], fill=(100, 180, 255, 120), width=1)
    draw.text((W // 2 - 80, ly + 20), "AI News Kurdish", fill=(130, 190, 255), font=fs_en)
    
    img.save(out, quality=95)
    return out
