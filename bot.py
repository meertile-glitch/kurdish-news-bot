import os,re,hashlib,requests,textwrap,random,asyncio
import feedparser
from datetime import datetime,timedelta,timezone
from telegram import Bot
from telegram.constants import ParseMode
from PIL import Image,ImageDraw,ImageFont

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

def prep_ku(t):
 try:
  import arabic_reshaper
  from bidi.algorithm import get_display
  return get_display(arabic_reshaper.reshape(t))
 except: return t

def card(title,summary,out="card.jpg"):
 W,H=1080,1080
 base=Image.open(TPL).convert('RGB').resize((W,H)) if os.path.exists(TPL) else Image.new('RGB',(W,H),(7,10,30))
 img=base.copy()
 draw=ImageDraw.Draw(img,'RGBA')
 try:
  fb=ImageFont.truetype("/usr/share/fonts/google-droid-sans-fonts/DroidKufi-Bold.ttf",42)
  fr=ImageFont.truetype("/usr/share/fonts/google-droid-sans-fonts/DroidKufi-Regular.ttf",26)
  fs=ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",20)
 except:
  fb=fr=fs=ImageFont.load_default()
 # logo
 x,y=45,40
 draw.ellipse([x,y,x+100,y+100],fill=(255,108,20))
 draw.text((x+22,y+18),"AI",fill="white",font=fb)
 draw.text((x+130,y+18),"AI NEWS",fill="white",font=fs)
 draw.text((x+130,y+44),"KURDISH",fill="white",font=fs)
 # card
 cw,ch=860,700
 cx,cy=(W-cw)//2,(H-ch)//2+35
 ov=Image.new('RGBA',(cw,ch),(30,35,85,220))
 m=Image.new('L',(cw,ch),0)
 ImageDraw.Draw(m).rounded_rectangle([0,0,cw,ch],radius=32,fill=255)
 ov.putalpha(m)
 img.paste(ov,(cx,cy),ov)
 draw=ImageDraw.Draw(img)
 for i in range(3):
  draw.rounded_rectangle([cx-i,cy-i,cx+cw+i,cy+ch+i],radius=32+i,outline=(120+i*10,85,255),width=1)
 # title
 tl=title[:130]
 wr=textwrap.wrap(tl,width=26)[:4]
 sy=cy+110
 for i,l in enumerate(wr):
  dl=prep_ku(l)
  try:
   tw=draw.textbbox((0,0),dl,font=fb)[2]
  except: tw=len(dl)*18
  draw.text((W//2-tw//2,sy+i*68),dl,fill="white",font=fb)
 # summary
 if summary:
  sm=summary[:130]
  sw=textwrap.wrap(sm,width=34)[:2]
  sy2=sy+len(wr)*68+35
  for j,l in enumerate(sw):
   dl=prep_ku(l)
   try:
    tw=draw.textbbox((0,0),dl,font=fr)[2]
   except: tw=len(dl)*12
   draw.text((W//2-tw//2,sy2+j*40),dl,fill=(210,220,255),font=fr)
 ly=cy+ch-130
 draw.line([cx+60,ly,cx+cw-60,ly],fill=(100,180,255,100),width=1)
 b="AI News Kurdish"
 try: tw=draw.textbbox((0,0),b,font=fs)[2]
 except: tw=len(b)*8
 draw.text((W//2-tw//2,ly+35),b,fill=(130,190,255),font=fs)
 draw.text((35,H-45),"ai.news.krd",fill=(100,180,255),font=fs)
 img.save(out,quality=92)
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
 coll=[]
 seen=set()
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
  except: cp=None
  try:
   tg=f"🔥 <b>{it['ku_title']}</b>\n\n{it['ku_summary']}\n\n⏰ {it['time']} UTC | {it['source']}\n🔗 <a href='{it['link']}'>خوێندنەوەی تەواو</a>\n\n#ژیری_دەستکرد #AI"
   if cp and os.path.exists(cp):
    with open(cp,'rb') as ph: await bot.send_photo(chat_id=CH,photo=ph,caption=tg,parse_mode=ParseMode.HTML)
   else: await bot.send_message(chat_id=CH,text=tg,parse_mode=ParseMode.HTML)
   await asyncio.sleep(2)
  except: pass
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
 asyncio.run(main())
