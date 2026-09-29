"""Render the intro title block for Screen 7 (512x212, pixel aspect ~1:2 -> x stretch 2.0).
Output: title_block.npy (levels 0..3), preview PNG."""
from PIL import Image, ImageDraw, ImageFont
import numpy as np, sys, json
G='/usr/share/fonts/truetype/sand-box/google/EB Garamond/'
REG=G+'EBGaramond-VariableFont_wght.ttf'; ITA=G+'EBGaramond-Italic-VariableFont_wght.ttf'
S=8; XS=2.0
def font(path,size,wt):
    f=ImageFont.truetype(path, round(size*S)); f.set_variation_by_axes([wt]); return f
def render_runs(runs, xoff=0):
    """runs: list of (text, fontobj, dy_px_logical). Draw on a common baseline, return float coverage at S7 res."""
    W=sum(f.getlength(t) for t,f,_ in runs)+8*S; H=round(60*S)
    im=Image.new('L',(int(W),H),0); d=ImageDraw.Draw(im); x=4*S; base=40*S
    for t,f,dy in runs:
        d.text((x,base+dy*S),t,font=f,fill=255,anchor='ls'); x+=f.getlength(t)
    a=np.asarray(im)
    ys,xs=np.nonzero(a>0); a=a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    # pad so the downsample grid is aligned to S
    a=np.pad(a,((0,S),(xoff,S)))
    ph=(-a.shape[0])%S; pw=(-a.shape[1])%(S//2)
    a=np.pad(a,((0,ph),(0,pw)))
    im=Image.fromarray(a)
    w=round(im.width/S*XS); h=round(im.height/S)
    return np.asarray(im.resize((w,h),Image.BOX),np.float32)/255
def quant(a): return np.clip(np.round(a*3),0,3).astype(np.uint8)
def crop(q):
    ys,xs=np.nonzero(q); return q[ys.min():ys.max()+1, xs.min():xs.max()+1]
def best(runs):
    for o in range(S//2):
        q=crop(quant(render_runs(runs,o)))
        if q.shape[1]%2==0: return q
    return q
variant=sys.argv[1] if len(sys.argv)>1 else 'A'
T=float(sys.argv[2]) if len(sys.argv)>2 else 20.5
TS=float(sys.argv[3]) if len(sys.argv)>3 else 1.5
if variant=='A':   # all regular
    title=[('Latok presents ~Sketch~',font(REG,T,500),0)]
elif variant=='B':
    title=[('Latok presents ',font(REG,T,500),0),('~Sketch~',font(ITA,T*1.12,500),0)]
else:              # 'Sketch' italic; tildes enlarged as swash ornaments centred on the x-height
    fi=font(ITA,T*1.12,500); ft=font(ITA,T*1.12*TS,500)
    xb=fi.getbbox('x',anchor='ls'); tb=ft.getbbox('~',anchor='ls')
    dy=((xb[1]+xb[3])/2-(tb[1]+tb[3])/2)/S
    title=[('Latok presents ',font(REG,T,500),0),('~',ft,dy),('Sketch',fi,0),('~',ft,dy)]
SUBF=float(sys.argv[4]) if len(sys.argv)>4 else 0.56
sub=[('Vibecoded using Grokbot',font(REG,T*SUBF,500),0)]
t=best(title); s=best(sub)
GAP=10
th,tw=t.shape; sh,sw=s.shape
bh=th+GAP+sh; W=512
blk=np.zeros((bh,W),np.uint8)
tx=(W-tw)//2; sx=(W-sw)//2
blk[0:th,tx:tx+tw]=t; blk[th+GAP:,sx:sx+sw]=s
top=(212-bh)//2
np.save(f'title_block_{variant}.npy',blk)
json.dump(dict(top=top,h=bh,title=[th,tw,tx],sub=[sh,sw,sx]),open(f'title_block_{variant}.json','w'))
print(variant,'title',t.shape,'sub',s.shape,'block h',bh,'top',top,'x',tx,sx)
lv=np.array([0,90,175,255],np.uint8)
scr=np.zeros((212,512),np.uint8); scr[top:top+bh]=lv[blk]
Image.fromarray(scr).resize((1024,848),Image.NEAREST).save(f'title_preview_{variant}.png')
