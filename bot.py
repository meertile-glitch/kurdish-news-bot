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
TPL="template_base.jpg"

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
 """Create the beautiful tech background like the image - neural sphere + circuit + bokeh"""
 img = Image.new('RGB',(W,H),(5,8,25))
 draw = ImageDraw.Draw(img,'RGBA')
 # Gradient dark background
 for y in range(H):
  r = int(5 + y*0.02)
  g = int(8 + y*0.015)
  b = int(25 + y*0.03)
  draw.line([(0,y),(W,y)],fill=(r,g,b))
 # Bokeh lights
 for _ in range(80):
  x = random.randint(0,W)
  y = random.randint(0,H)
  s = random.randint(3,25)
  alpha = random.randint(10,60)
  c = random.choice([(80,60,255),(60,100,255),(120,80,255),(60,180,255)])
  draw.ellipse([x-s,y-s,x+s,y+s],fill=(c[0],c[1],c[2],alpha))
 # Circuit patterns - left side
 for _ in range(25):
  x = random.randint(0,W//3)
  y = random.randint(0,H)
  draw.rectangle([x,y,x+random.randint(20,80),y+2],fill=(40,60,120,80))
  draw.rectangle([x,y,x+2,y+random.randint(20,80)],fill=(40,60,120,80))
 # Neural network sphere - top right like in image
 cx_sphere = int(W*0.82)
 cy_sphere = int(H*0.32)
 radius = 260
 points = []
 for _ in range(120):
  # Random points on sphere
  theta = random.uniform(0, 2*math.pi)
  phi = random.uniform(0, math.pi)
  # Only show front hemisphere + some back
  if random.random() > 0.3:
   r = radius * (0.8 + random.random()*0.2)
   x = cx_sphere + r * math.sin(phi) * math.cos(theta)
   y = cy_sphere + r * math.sin(phi) * math.sin(theta) * 0.7
   # Perspective
   z = r * math.cos(phi)
   if z > -radius*0.5:
    points.append((x,y,z))
 # Draw connections
 for i,(x1,y1,z1) in enumerate(points):
  for j in range(i+1, len(points)):
   x2,y2,z2 = points[j]
   dist = math.sqrt((x1-x2)**2 + (y1-y2)**2)
   if dist < 90 and z1 > -50 and z2 > -50:
    alpha = int(100 - dist)
    if alpha > 20:
     draw.line([(x1,y1),(x2,y2)],fill=(100,120,255,alpha),width=1)
 # Draw points glowing
 for x,y,z in points:
  if z > -50:
   s = 3 if z > 50 else 2
   glow = int(150 + z*0.3)
   glow = max(50, min(255, glow))
   draw.ellipse([x-s,y-s,x+s,y+s],fill=(glow,glow,255,200))
   # Outer glow
   draw.ellipse([x-s*2,y-s*2,x+s*2,y+s*2],fill=(80,80,255,40))
 # Circuit floor - bottom
 for _ in range(40):
  x = random.randint(0,W)
  y = random.randint(int(H*0.75),H)
  draw.rectangle([x,y,x+random.randint(30,120),y+1],fill=(30,50,100,60))
  if random.random() > 0.7:
   draw.rectangle([x,y,x+1,y+random.randint(10,30)],fill=(30,50,100,60))
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
  for d in ["/usr/share/fonts/truetype/noto","/usr/share/fonts/opentype/noto","/usr/share/fonts/truetype/dejavu","/usr/share/fonts/google-droid-sans-fonts","/usr/share/fonts","./","./fonts"]:
   for n in names:
    p=os.path.join(d,n)
    if os.path.exists(p):
     return p
  return None

 en_bold = find_font(["DejaVuSans-Bold.ttf","DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
 en_reg = find_font(["DejaVuSans.ttf"]) or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
 ku_bold = find_font(["NotoNaskhArabic-Bold.ttf","NotoKufiArabic-Bold.ttf","NotoNaskhArabic-Regular.ttf"]) or en_bold
 ku_reg = find_font(["NotoNaskhArabic-Regular.ttf","NotoKufiArabic-Regular.ttf"]) or en_reg

 def load(p,size):
  try:
   if LAYOUT:
    return ImageFont.truetype(p,size,layout_engine=LAYOUT)
   else:
    return ImageFont.truetype(p,size)
  except:
   return ImageFont.load_default()

 fb_en = load(en_bold,44)
 fs_en = load(en_reg,20)
 fb_ku = load(ku_bold,44) if ku_bold else fb_en
 fr_ku = load(ku_reg,26) if ku_reg else fs_en

 # Logo - top left like image
 x,y=45,40
 draw.ellipse([x,y,x+100,y+100],fill=(255,108,20))
 draw.text((x+28,y+22),"AI",fill="white",font=fb_en)
 draw.text((x+130,y+18),"AI NEWS",fill="white",font=fs_en)
 draw.text((x+130,y+44),"KURDISH",fill="white",font=fs_en)

 # Glass card - center like image with neon border
 cw,ch=860,700
 cx,cy=(W-cw)//2,(H-ch)//2+35
 # Glass effect
 glass = Image.new('RGBA',(cw,ch),(20,25,60,110))
 mask = Image.new('L',(cw,ch),0)
 ImageDraw.Draw(mask).rounded_rectangle([0,0,cw,ch],radius=32,fill=255)
 glass.putalpha(mask)
 # Blur background behind glass
 bg_crop = img.crop((cx,cy,cx+cw,cy+ch)).filter(ImageFilter.GaussianBlur(2)) if 'ImageFilter' in dir(Image) else img.crop((cx,cy,cx+cw,cy+ch))
 try:
  from PIL import ImageFilter
  bg_crop = img.crop((cx,cy,cx+cw,cy+ch)).filter(ImageFilter.GaussianBlur(3))
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

 # Title - white like "Coming Soon"
 tl=title[:130].strip()
 wr=textwrap.wrap(tl,width=26)[:4]
 sy=cy+110
 for i,l in enumerate(wr):
  if not l.strip(): continue
  try:
   bbox=draw.textbbox((0,0),l,font=fb_ku)
   tw=bbox[2]-bbox[0]
  except: tw=len(l)*18
  draw.text((W//2-tw//2+2,sy+i*68+2),l,fill=(0,0,0,180),font=fb_ku)
  draw.text((W//2-tw//2,sy+i*68),l,fill="white",font=fb_ku)

 if summary:
  sm=summary[:130].strip()
  sw=textwrap.wrap(sm,width=34)[:2]
  sy2=sy+len(wr)*68+35
  for j,l in enumerate(sw):
   if not l.strip(): continue
   try:
    bbox=draw.textbbox((0,0),l,font=fr_ku)
    tw=bbox[2]-bbox[0]
   except: tw=len(l)*12
   draw.text((W//2-tw//2+1,sy2+j*40+1),l,fill=(0,0,0,130),font=fr_ku)
   draw.text((W//2-tw//2,sy2+j*40),l,fill=(210,220,255),font=fr_ku)

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
   kt=to_ku(it['title'],it['lang']); ks=to_ku(it['summary'],it['lang']) if it['summary'] else ""
   trans.append({**it,"ku_title":kt[:140],"ku_summary":ks[:140]})
   await asyncio.sleep(1)
  except:
   trans.append({**it,"ku_title":it['title'],"ku_summary":it['summary'][:140]})
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
