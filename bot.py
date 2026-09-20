import os,re,hashlib,requests,textwrap,asyncio,random,math
import feedparser
from datetime import datetime,timedelta,timezone
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image,ImageDraw,ImageFont, features

BOT=os.getenv("BOT_TOKEN") or "8921906381:AAEtOy3QDFFuwNMxHWeYSA9PsLvlqxQG24I"
CH=os.getenv("CHANNEL_ID") or "@kurdish_short_news"
FID=os.getenv("FB_PAGE_ID") or os.getenv("FB_ID")
FTOK=os.getenv("FB_PAGE_TOKEN") or os.getenv("FB_TOKEN")
# TPL removed - using CODE beautiful background only, no upload needed

FEEDS={
"G AI":"https://news.google.com/rss/search?q=artificial+intelligence+when:1d&hl=en-US&gl=US&ceid=US:en",
"G ChatGPT":"https://news.google.com/rss/search?q=ChatGPT+when:1d&hl=en-US&gl=US&ceid=US:en",
"G Gemini":"https://news.google.com/rss/search?q=Gemini+AI+when:1d&hl=en-US&gl=US&ceid=US:en",
"TechCrunch":"https://techcrunch.com/category/artificial-intelligence/feed/",
"TheVerge":"https://www.theverge.com/rss/ai/index.xml",
"Wired":"https://www.wired.com/feed/tag/ai/latest/rss"
}

def cl(t):
 if not t: return ""
 t=re.sub('<[^<]+?>','',t)
 return re.sub(r'\s+',' ',t).strip()[:500]

def tr_mem(txt,src='en',tgt='ckb'):
 try:
  r=requests.get("https://api.mymemory.translated.net/get",params={"q":txt[:350],"langpair":f"{src}|{tgt}"},timeout=8)
  d=r.json()
  if d.get('responseStatus')==200:
   t=d['responseData']['translatedText']
   if t and len(t)>8 and '[MYMEMORY' not in t and t.lower()!=txt.lower()[:20]:
    return t
 except: pass
 return None

def to_ku(txt,src='en'):
 txt=cl(txt)
 if not txt: return txt
 if any(x in txt.lower() for x in [' ve ',' bir ',' için']): src='tr'
 for s,t in [(src,'ckb'),('en','ckb'),('tr','ckb'),(src,'ku'),('en','ku')]:
  r=tr_mem(txt,s,t)
  if r: return r
 try:
  from deep_translator import GoogleTranslator
  return GoogleTranslator(source=src,target='ckb').translate(txt[:350])
 except: pass
 return txt

def fresh(e,h=24):
 try:
  if hasattr(e,'published_parsed') and e.published_parsed:
   pub=datetime(*e.published_parsed[:6],tzinfo=timezone.utc)
   return (datetime.now(timezone.utc)-pub)<=timedelta(hours=h)
  return True
 except: return True

def is_ai(t): 
 k=["ai","artificial intelligence","chatgpt","openai","gemini","gpt","llm","machine learning","anthropic","nvidia","neural"]
 return any(x in t.lower() for x in k)

def create_beautiful_background(W,H):
 """Ultra beautiful background - premium tech like original Coming Soon but even better"""
 img = Image.new('RGB',(W,H),(4,6,22))
 draw = ImageDraw.Draw(img,'RGBA')
 for y in range(H):
  r = int(4 + y*0.02 + math.sin(y*0.01)*2)
  g = int(6 + y*0.025)
  b = int(22 + y*0.06 + math.sin(y*0.008)*5)
  draw.line([(0,y),(W,y)],fill=(r,g,b))
 for _ in range(150):
  x = random.randint(-50,W+50)
  y = random.randint(-50,H+50)
  s = random.randint(6,45)
  alpha = random.randint(20,90)
  c = random.choice([(100,80,255),(80,130,255),(140,90,255),(70,200,255),(110,90,230),(60,180,220)])
  draw.ellipse([x-s,y-s,x+s,y+s],fill=(c[0],c[1],c[2],alpha))
  if s > 20 and random.random() > 0.6:
   draw.ellipse([x-s//3,y-s//3,x+s//3,y+s//3],fill=(200,180,255,alpha+30))
 for _ in range(45):
  x = random.randint(0,W//3)
  y = random.randint(0,H)
  w = random.randint(60,180)
  draw.rectangle([x,y,x+w,y+2],fill=(50,75,140,80))
  draw.rectangle([x,y,x+2,y+random.randint(60,180)],fill=(50,75,140,80))
  if random.random() > 0.4:
   draw.ellipse([x+w-3,y-3,x+w+3,y+3],fill=(80,110,200,100))
 for _ in range(60):
  x = random.randint(0,W)
  y = random.randint(int(H*0.65),H)
  w = random.randint(70,220)
  draw.rectangle([x,y,x+w,y+1],fill=(40,65,120,70))
 cx_sphere = int(W*0.82)
 cy_sphere = int(H*0.25)
 radius = 380
 points = []
 for _ in range(280):
  theta = random.uniform(0, 2*math.pi)
  phi = random.uniform(0, math.pi*0.85)
  r = radius * (0.88 + random.random()*0.22)
  x = cx_sphere + r * math.sin(phi) * math.cos(theta)
  y = cy_sphere + r * math.sin(phi) * math.sin(theta) * 0.7
  z = r * math.cos(phi)
  if z > -radius*0.4:
   points.append((x,y,z))
 for i,(x1,y1,z1) in enumerate(points):
  for j in range(i+1, len(points)):
   x2,y2,z2 = points[j]
   dist = math.sqrt((x1-x2)**2 + (y1-y2)**2)
   if dist < 130 and z1 > -60 and z2 > -60:
    alpha = int(160 - dist*0.7)
    if alpha > 20:
     if dist < 60:
      draw.line([(x1,y1),(x2,y2)],fill=(150,120,255,alpha),width=1)
     else:
      draw.line([(x1,y1),(x2,y2)],fill=(100,140,255,alpha),width=1)
 for x,y,z in points:
  if z > -60:
   s = 5 if z > 100 else 4
   if z > 180:
    s = 6
   draw.ellipse([x-s,y-s,x+s,y+s],fill=(240,220,255,255))
   draw.ellipse([x-s*2,y-s*2,x+s*2,y+s*2],fill=(140,120,255,90))
   draw.ellipse([x-s*3.5,y-s*3.5,x+s*3.5,y+s*3.5],fill=(100,80,200,35))
   draw.ellipse([x-s*5,y-s*5,x+s*5,y+s*5],fill=(80,60,180,15))
   if z > 120 and random.random() > 0.5:
    draw.ellipse([x-1,y-1,x+1,y+1],fill=(255,255,255,255))
 return img



def card(title,summary,out="card.jpg"):
 W,H=1080,1080
 print(f"RAQM={features.check('raqm')} HarfBuzz={features.check('harfbuzz')}")
 # Try template file first, if not exists create beautiful background in code
 if os.path.exists(TPL):
  try:
   base=Image.open(TPL).convert('RGB').resize((W,H))
   print(f"Using file template: {TPL}")
  except:
   base=create_beautiful_background(W,H)
   print("Using CODE beautiful background (file failed)")
 else:
  base=create_beautiful_background(W,H)
  print("Using CODE beautiful background (no file) - like the image you sent!")

 img=base.copy()
 draw=ImageDraw.Draw(img,'RGBA')
 try:
  LAYOUT=ImageFont.Layout.RAQM
 except:
  LAYOUT=None

 def find_font(names):
  for d in ["/usr/share/fonts/truetype/noto","/usr/share/fonts/opentype/noto","/usr/share/fonts/truetype/dejavu","/usr/share/fonts/google-droid-sans-fonts","/usr/share/fonts","./","./fonts","/tmp/fonts"]:
   for n in names:
    p=os.path.join(d,n)
    if os.path.exists(p):
     return p
  return None

 # === BEAUTIFUL KURDISH FONTS - like Rudaw/NRT ===
 # Title: NotoKufiArabic-Bold (geometric, modern, beautiful for Kurdish headlines)
 # This is the font used by many Kurdish news sites - very beautiful
 en_bold = find_font(["DejaVuSans-Bold.ttf","DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
 en_reg = find_font(["DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
 # Kurdish beautiful fonts priority - Kufi is more beautiful than Naskh for titles
 ku_bold_candidates = [
  "NotoKufiArabic-Bold.ttf",      # Most beautiful for headlines - modern geometric
  "Vazirmatn-Bold.ttf",           # Very beautiful Persian/Kurdish font
  "NotoNaskhArabic-Bold.ttf",     # Beautiful Naskh
  "DroidKufi-Bold.ttf",           # Fallback old
  "DejaVuSans-Bold.ttf"
 ]
 ku_reg_candidates = [
  "NotoKufiArabic-Regular.ttf",
  "NotoKufiArabic-Medium.ttf",
  "Vazirmatn-Regular.ttf",
  "NotoNaskhArabic-Regular.ttf",
  "DroidKufi-Regular.ttf"
 ]
 ku_bold = find_font(ku_bold_candidates) or en_bold
 ku_reg = find_font(ku_reg_candidates) or en_reg
 print(f"Using beautiful Kurdish fonts: Bold={ku_bold} Regular={ku_reg}")

 def load(p,size, beautiful=False):
  try:
   if LAYOUT:
    font = ImageFont.truetype(p,size,layout_engine=LAYOUT)
   else:
    font = ImageFont.truetype(p,size)
   return font
  except Exception as e:
   print(f"Font load fail {p}: {e}")
   return ImageFont.load_default()

 # Beautiful sizes - larger and bolder for beauty
 fb_en = load(en_bold,46)
 fs_en = load(en_reg,22)
 # Kurdish - BIGGER and more beautiful
 fb_ku = load(ku_bold,58) if ku_bold else fb_en  # 58px - very big and beautiful like Rudaw
 fr_ku = load(ku_reg,34) if ku_reg else fs_en   # 34px for summary


 # Logo - top left like image
 x,y=45,40
 draw.ellipse([x,y,x+100,y+100],fill=(255,108,20))
 draw.text((x+28,y+22),"AI",fill="white",font=fb_en)
 draw.text((x+130,y+18),"AI NEWS",fill="white",font=fs_en)
 draw.text((x+130,y+44),"KURDISH",fill="white",font=fs_en)

 # Glass card - center like image with neon border
 cw,ch=880,680
 cx,cy=(W-cw)//2,(H-ch)//2+40
 # Glass effect
 glass = Image.new('RGBA',(cw,ch),(18,22,48,210))
 mask = Image.new('L',(cw,ch),0)
 ImageDraw.Draw(mask).rounded_rectangle([0,0,cw,ch],radius=32,fill=255)
 glass.putalpha(mask)
 # Blur background behind glass
 bg_crop = img.crop((cx,cy,cx+cw,cy+ch)).filter(ImageFilter.GaussianBlur(2)) if 'ImageFilter' in dir(Image) else img.crop((cx,cy,cx+cw,cy+ch))
 try:
  from PIL import ImageFilter
  bg_crop = img.crop((cx,cy,cx+cw,cy+ch)).filter(ImageFilter.GaussianBlur(12))
  img.paste(bg_crop,(cx,cy))
 except:
  pass
 img.paste(glass,(cx,cy),glass)
 draw=ImageDraw.Draw(img)
 # Neon borders like image
 for i in range(3):
  alpha = 200 - i*50
  draw.rounded_rectangle([cx-i,cy-i,cx+cw+i,cy+ch+i],radius=32+i,outline=(130+i*15,90,255,alpha),width=1)
 # Inner highlight
 draw.rounded_rectangle([cx+8,cy+8,cx+cw-8,cy+ch-8],radius=26,outline=(180,180,255,60),width=1)

 # Title - ULTRA BEAUTIFUL with purple stroke like premium Rudaw/NRT
 tl=title[:130].strip()
 wr=textwrap.wrap(tl,width=22)[:4]
 sy=cy+70
 for i,l in enumerate(wr):
  if not l.strip(): continue
  try:
   bbox=draw.textbbox((0,0),l,font=fb_ku)
   tw=bbox[2]-bbox[0]
  except: tw=len(l)*22
  x_center = W//2 - tw//2
  y_pos = sy + i*82
  # 1. Deep shadow for depth
  draw.text((x_center+5,y_pos+5),l,fill=(0,0,0,230),font=fb_ku)
  # 2. Purple glow outline - 8 directions for beautiful stroke effect
  for dx, dy in [(-2,-2),(-2,2),(2,-2),(2,2),(-2,0),(2,0),(0,-2),(0,2)]:
   draw.text((x_center+dx,y_pos+dy),l,fill=(140,100,255,140),font=fb_ku)
  # 3. Extra purple outer glow
  for dx, dy in [(-3,0),(3,0),(0,-3),(0,3)]:
   draw.text((x_center+dx,y_pos+dy),l,fill=(120,80,220,80),font=fb_ku)
  # 4. Main beautiful white
  draw.text((x_center,y_pos),l,fill="white",font=fb_ku)

 if summary:
  sm=summary[:120].strip()
  sw=textwrap.wrap(sm,width=32)[:2]
  sy2=sy+len(wr)*82+40
  for j,l in enumerate(sw):
   if not l.strip(): continue
   try:
    bbox=draw.textbbox((0,0),l,font=fr_ku)
    tw=bbox[2]-bbox[0]
   except: tw=len(l)*14
   draw.text((W//2-tw//2+1,sy2+j*46+1),l,fill=(0,0,0,150),font=fr_ku)
   draw.text((W//2-tw//2,sy2+j*46),l,fill=(220,225,255),font=fr_ku)

 ly=cy+ch-130
 draw.line([cx+60,ly,cx+cw-60,ly],fill=(100,180,255,120),width=1)
 b="AI News Kurdish"
 try: tw=draw.textbbox((0,0),b,font=fs_en)[2]
 except: tw=len(b)*8
 draw.text((W//2-tw//2,ly+35),b,fill=(130,190,255),font=fs_en)
 draw.text((35,H-45),"ai.news.krd",fill=(100,180,255),font=fs_en)
 img.save(out,quality=95)
 print(f"Card saved: {out} with beautiful CODE background")
 return out

def fb_post(msg,link="",img_path=None):
 try:
  cap=f"{msg}\n\n🔗 {link}" if link else msg
  if img_path and os.path.exists(img_path):
   with open(img_path,'rb') as f:
    r=requests.post(f"https://graph.facebook.com/v18.0/me/photos",data={"caption":cap,"access_token":FTOK},files={'source':f},timeout=30)
    d=r.json()
    if "id" in d or "post_id" in d: return True
  for ep in [f"https://graph.facebook.com/v18.0/me/feed",f"https://graph.facebook.com/v18.0/{FID}/feed"]:
   r=requests.post(ep,data={"message":cap,"access_token":FTOK,"link":link},timeout=20)
   if "id" in r.json(): return True
  return False
 except: return False

async def main():
 bot=Bot(token=BOT)
 sent=set()
 try:
  with open("sent.txt","r",encoding="utf-8") as f: sent=set(l.strip() for l in f if l.strip())
 except: pass
 coll=[]; seen=set()
 for name,url in FEEDS.items():
  try:
   feed=feedparser.parse(url)
   for e in feed.entries[:8]:
    t=cl(getattr(e,'title','')); s=cl(getattr(e,'summary','') or getattr(e,'description','')); lk=getattr(e,'link','')
    if not t or not lk or lk in seen: continue
    seen.add(lk)
    if not fresh(e,24): continue
    if not is_ai(f"{t} {s}"): continue
    h=hashlib.md5(lk.encode()).hexdigest()[:10]
    if h in sent: continue
    pt=""
    if hasattr(e,'published_parsed') and e.published_parsed:
     pt=datetime(*e.published_parsed[:6],tzinfo=timezone.utc).strftime("%H:%M")
    coll.append({"title":t,"summary":s,"link":lk,"source":name,"lang":'tr' if 'tr' in url.lower() else 'en',"hash":h,"time":pt})
  except: continue
 if not coll: return
 sel=coll[:3]
 trans=[]
 for it in sel:
  try:
   kt=to_ku(it['title'],it['lang'])
   # Only use summary if it's different from title
   sum_raw = it['summary'][:160] if it['summary'] else ""
   if sum_raw and sum_raw[:35].lower() != it['title'][:35].lower():
    ks=to_ku(sum_raw,it['lang'])
   else:
    ks=""
   trans.append({**it,"ku_title":kt[:140],"ku_summary":ks[:110]})
  except:
   trans.append({**it,"ku_title":it['title'][:140],"ku_summary":""})
for it in trans:
  cp=f"c_{it['hash']}.jpg"
  try: card(it['ku_title'],it['ku_summary'],cp)
  except Exception as e:
   print(f"Card error: {e}")
   import traceback; traceback.print_exc()
   cp=None
  try:
   tg=f"🔥 <b>{it['ku_title']}</b>\n\n{it['ku_summary']}\n\n⏰ {it['time']} UTC | {it['source']}\n🔗 <a href='{it['link']}'>خوێندنەوەی تەواو</a>\n\n#ژیری_دەستکرد #AI"
   if cp and os.path.exists(cp):
    with open(cp,'rb') as ph: await bot.send_photo(chat_id=CH,photo=ph,caption=tg,parse_mode=ParseMode.HTML)
   else: await bot.send_message(chat_id=CH,text=tg,parse_mode=ParseMode.HTML)
   await asyncio.sleep(2)
  except Exception as e: print(f"TG error {e}")
  try:
   fb=f"🔥 {it['ku_title']}\n\n{it['ku_summary']}\n\n⏰ {it['time']} UTC | {it['source']}\n\n#ژیری_دەستکرد #AI"
   fb_post(fb,it['link'],cp)
   await asyncio.sleep(2)
  except: pass
  try:
   if cp and os.path.exists(cp): os.remove(cp)
  except: pass
 try:
  allh=sent.union(set([x['hash'] for x in trans]))
  with open("sent.txt","w",encoding="utf-8") as f: f.write("\n".join(list(allh)[-500:]))
 except: pass

if __name__=="__main__":
 import asyncio
 asyncio.run(main())
