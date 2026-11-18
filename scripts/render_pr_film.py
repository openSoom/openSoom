"""Build the openSoom 45-second PR picture master, then mux the approved sound mix.

The 16:9 Firefly motion shots, genuine browser recordings and the two-application
CSE readbacks are distinct sources. Timings live in the edit list below.
"""
import argparse
import functools
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'deliverables/video/cinematic'
PR=PACKAGE/'pr'
FLY=PACKAGE/'firefly'
BIN=ROOT/'tmp/pr-film'
PUBLIC=ROOT/'deliverables/video/openSoom-pr-45s.mp4'
W,H,FPS=1920,1080,24
WHITE='#F4F6EF'; GREEN='#C0F2D0'; MID='#88C4AA'; INK='#0A2423'; MUTED='#C0CCC6'
EDIT=[('hood',0,5),('damper',5,10),('reading',10,13),('apps',13,21.5),
      ('ack',21.5,29),('studio',29,34),('targets',34,38.5),('brand',38.5,45)]


def read(p):return json.loads(Path(p).read_text())


@functools.lru_cache(maxsize=96)
def font(sz,face='regular'):
    path='/System/Library/Fonts/Avenir Next.ttc'
    if face=='mono':return ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',sz,index=0)
    return ImageFont.truetype(path,sz,index={'regular':7,'demi':2,'medium':5,'light':10,'bold':0,'heavy':8}[face])


def smooth(p):
    p=max(0,min(1,p));return p*p*(3-2*p)


def ramp(t,st=.0,d=.43):return smooth((t-st)/d)


def lettering(im,x,y,val,sz,color=WHITE,face='regular',tracking=0,anchor='lt'):
    d=ImageDraw.Draw(im);f=font(sz,face)
    if not tracking:
        d.text((round(x),round(y)),val,font=f,fill=color,anchor=anchor)
        return
    if anchor=='mt':x-=(f.getlength(val)+(len(val)-1)*tracking)/2
    for c in val:
        d.text((round(x),round(y)),c,font=f,fill=color,anchor='lt')
        x+=f.getlength(c)+tracking


@functools.lru_cache(maxsize=160)
def phrase(val,sz,face,color):
    bbox=font(sz,face).getbbox(val,anchor='lt')
    img=Image.new('RGBA',(max(1,bbox[2]+4),max(1,bbox[3]+4)))
    lettering(img,0,0,val,sz,color,face)
    return img


def keyed(im,x,y,val,sz,face,color,t,st=.0,travel=22):
    p=ramp(t,st,.48)
    if not p:return
    l=phrase(val,sz,face,color);a=l.getchannel('A')
    if p<1:a=a.point(lambda z:round(z*p))
    im.paste(l,(round(x),round(y+(1-p)*travel)),a)


def cropfill(im,w,h):
    return ImageOps.fit(im,(w,h),method=Image.Resampling.LANCZOS)


def curved(points,q):
    a,b,c,e=points;t=1-q
    return tuple(t*t*t*a[i]+3*t*t*q*b[i]+3*t*q*q*c[i]+q*q*q*e[i] for i in range(2))


def drawpath(d,p,col,w=4,portion=1):
    pts=[curved(p,i/90) for i in range(max(2,int(90*max(0,min(1,portion)))+1))]
    d.line(pts,fill=col,width=w)


def dots(d,cx,cy,r,col):
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=col)


def mark(im,size,x,y):
    logo=logo_at(size)
    im.paste(logo,(x,y),logo)


@functools.lru_cache(maxsize=10)
def logo_at(size):
    return Image.open(PR/'brand-mark.png').convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)


def frame_bg():
    x=np.linspace(0,1,W)[None,:];y=np.linspace(0,1,H)[:,None]
    field=np.exp(-((x-.73)/.50)**2-((y-.60)/.82)**2)
    return Image.fromarray(np.dstack([9+field*8,24+field*29,24+field*22]).astype('uint8'))


BG=frame_bg()
shade=Image.new('RGB',(W,H),'#031513')
x=np.linspace(0,1,W)[None,:]; y=np.linspace(0,1,H)[:,None]
MASK=Image.fromarray(np.clip(10+170*(1-x)**1.5+20*y*y,0,255).astype('uint8'))


class Frames:
    def __init__(self,path,duration,start=0,end=None,photo=False,area=None,size=(W,H)):
        self.size=size;w,h=size
        cmd=['ffmpeg','-nostdin','-loglevel','error','-threads','2']
        if photo:
            cmd+=['-loop','1','-framerate','24','-i',str(path)]
            vf=f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},zoompan=z='1+0.00045*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=24"
        else:
            cmd+=['-ss',str(start),'-i',str(path)]
            vf=(f'crop={area},' if area else '')+f'scale={w}:{h}:flags=lanczos,'
            vf+=(f'setpts={duration/(end-start):.8f}*(PTS-STARTPTS),' if end else '')+'fps=24,tpad=stop_mode=clone:stop_duration=1'
        self.p=subprocess.Popen(cmd+['-an','-vf',vf,'-t',str(duration),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    def get(self):
        data=self.p.stdout.read(self.size[0]*self.size[1]*3)
        if len(data)!=self.size[0]*self.size[1]*3: raise RuntimeError('Source ended before the required cut')
        return Image.frombytes('RGB',self.size,data)
    def close(self):
        self.p.stdout.close()
        if self.p.poll() is None:self.p.terminate()
        self.p.wait()


def lens(im):
    return Image.composite(shade,im,MASK)


def edge_text(im,t,label):
    mark(im,45,81,59)
    lettering(im,143,65,'openSoom',29,WHITE,'demi')
    lettering(im,84,996,label,20,'#DAE5DB','mono',1)


def branch_graph(im,t):
    d=ImageDraw.Draw(im)
    # One native observation reaches one standard service layer and two separate AEs.
    p0=[(156,577),(355,577),(485,577),(720,577)]
    p1=[(734,577),(1025,577),(966,380),(1241,380)]
    p2=[(734,577),(1025,577),(966,767),(1241,767)]
    for p in (p0,p1,p2):drawpath(d,p,'#31574C',3)
    drawpath(d,p0,GREEN,5,ramp(t,.25,1.2))
    for i,p in enumerate([p1,p2]):
        drawpath(d,p,MID if i else GREEN,5,ramp(t,1.35+i*.28,1))
        if t>2.1+i*.3:
            z=(t/3.7-i*.14)%1;px,py=curved(p,z);dots(d,px,py,6,GREEN)
    for xx,yy,r in [(156,577,12),(727,577,18),(1241,380,10),(1241,767,10)]:
        dots(d,xx,yy,r+7,'#35584D');dots(d,xx,yy,r,GREEN)
    lettering(im,84,626,'Device reading',33,WHITE,'medium');lettering(im,585,644,'oneM2M CSE',36,GREEN,'demi')
    keyed(im,1265,338,'Operations',61,'demi',WHITE,t,.80)
    keyed(im,1267,417,'Checks the response',30,'regular',MUTED,t,1.5)
    keyed(im,1265,713,'Maintenance',61,'demi',WHITE,t,1.30)
    keyed(im,1267,794,'Opens an inspection order',30,'regular',MUTED,t,2.0)


def size_for(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))


class Shot:
    def __init__(self,name,length,strict):
        self.name=name;self.length=length;self.source=None;self.note=None
        if name in ('hood','damper','studio'):
            k={'hood':'kitchen','damper':'plant','studio':'learning'}[name]
            clip=FLY/(k+'-motion.mp4')
            if strict and not clip.exists():raise RuntimeError('Final motion required: '+str(clip))
            self.note=clip if clip.is_file() else FLY/(k+'.png')
            self.source=Frames(self.note,length,0,min(size_for(clip),length) if clip.is_file() else None,not clip.is_file())
        if name in ('reading','ack','targets'):
            is_food=name!='targets'
            r=read(ROOT/'evidence/video/cinematic/pr-dashboard-recording.json')['runs'][0] if is_food else read(ROOT/'evidence/video/cinematic/dashboard-recordings.json')['runs'][1]
            self.note=(PR/'food-unresolved-session.webm') if is_food else (PACKAGE/'demo/learning-session.webm')
            if name=='reading':start=r['cues']['detail']-5.0; size=(1324,787); area='1300:772:70:14'
            elif name=='ack':start=r['cues']['result']+1.6;size=(1156,782);area='1156:782:170:14'
            else:start=r['cues']['result']+.45;size=(1095,695);area='1240:787:130:14'
            self.source=Frames(self.note,length,start,start+length,False,area,size)
    def frame(self,t):
        n=self.name;raw=self.source.get() if self.source else None
        im=lens(raw) if n in ('hood','damper','studio') else BG.copy()
        dr=ImageDraw.Draw(im)
        if n=='hood':
            edge_text(im,t,'ILLUSTRATIVE FACILITY')
            if t<2.33:
                keyed(im,81,596,'The fan is',109,'regular',WHITE,t,.05)
                keyed(im,77,724,'running.',144,'demi',WHITE,t,.20)
            else:
                keyed(im,81,597,'Is the air',112,'regular',WHITE,t,2.33)
                keyed(im,78,724,'moving?',144,'demi',GREEN,t,2.42)
        elif n=='damper':
            edge_text(im,t,'COOKING LINE   /   SIMULATED TELEMETRY')
            keyed(im,84,352,'Measured airflow',49,'medium',WHITE,t,.03)
            keyed(im,73,437,'360',190,'demi',WHITE,t,.12)
            keyed(im,83,686,'of 900 m³/h required by this profile',43,'regular',WHITE,t,.4)
            dr.rounded_rectangle((86,803,804,813),radius=5,fill='#75958A')
            z=86+718*.4*ramp(t,.5,1.15)
            dr.rounded_rectangle((86,802,z+1,814),radius=5,fill=GREEN)
        elif n=='reading':
            # Original live browser image enters as a clean cut; evidence stays fully readable.
            im=Image.new('RGB',(W,H),'#E9EEE6')
            dr=ImageDraw.Draw(im);dr.rectangle((578,128,1905,918),fill='#ABC2B3')
            im.paste(raw,(580,130))
            keyed(im,80,344,'One',115,'regular',INK,t,.02)
            keyed(im,77,469,'reading.',112,'demi',INK,t,.12)
            lettering(im,83,980,'ACTUAL APP   /   VIRTUAL EQUIPMENT',21,'#486356','mono',1)
        elif n=='apps':
            lettering(im,83,63,'oneM2M',31,GREEN,'demi')
            keyed(im,80,167,'Two independent applications.',80,'demi',WHITE,t)
            branch_graph(im,t)
            lettering(im,83,985,'RECONSTRUCTED FROM THE SEPARATE MULTI-APPLICATION RUN',20,MUTED,'mono',.7)
        elif n=='ack':
            dr.rectangle((727,144,1888,931),fill='#81A692');im.paste(raw,(730,147))
            lettering(im,84,68,'Cooking line',31,GREEN,'demi')
            keyed(im,80,273,'Command',67,'regular',WHITE,t,.0)
            keyed(im,80,356,'acknowledged.',62,'demi',WHITE,t,.14)
            if t>2.1:
                keyed(im,80,557,'Airflow still low.',60,'demi','#F4B27E',t,2.1)
                keyed(im,83,655,'360 / 900 m³/h',43,'regular',WHITE,t,2.4)
            lettering(im,83,981,'ACTUAL DASHBOARD RECORDING   /   SIMULATED RESPONSE',20,MUTED,'mono',.65)
        elif n=='studio':
            edge_text(im,t,'ILLUSTRATIVE LEARNING SPACE')
            keyed(im,80,599,'A different',102,'regular',WHITE,t,0)
            keyed(im,78,724,'room.',142,'demi',GREEN,t,.14)
        elif n=='targets':
            im=Image.new('RGB',(W,H),'#E9EEE6');dr=ImageDraw.Draw(im)
            dr.rectangle((741,199,1842,900),fill='#ADC2B4');im.paste(raw,(744,202))
            lettering(im,82,70,'Learning studio',32,INK,'demi')
            keyed(im,78,297,'Its own',82,'regular',INK,t,0)
            keyed(im,78,405,'target.',101,'demi',INK,t,.10)
            keyed(im,82,624,'200 / 500 m³/h',51,'demi','#3B6755',t,.30)
            lettering(im,84,980,'ACTUAL APP   /   SIMULATED TELEMETRY',21,'#486356','mono',.8)
        elif n=='brand':
            # Four parallel currents carry the logo reveal into the quiet end card.
            for j in range(6):
                py=150+j*131;phase=t*.34+j*.19
                points=[(x,py+math.sin(x/330+phase)*47+math.sin(x/550-phase)*43) for x in range(0,W+1,14)]
                dr.line(points,fill='#1B3F37',width=2)
            if t<1.48:
                keyed(im,82,385,'oneM2M connects',86,'regular',WHITE,t,.0)
                keyed(im,82,500,'the devices.',109,'demi',GREEN,t,.12)
            else:
                mark(im,136,539,406)
                keyed(im,705,382,'openSoom',132,'demi',WHITE,t,1.48)
                keyed(im,585,631,'github.com/openSoom/openSoom',44,'medium',GREEN,t,1.77)
        return im
    def close(self):
        if self.source:self.source.close()


def preflight():
    r=read(ROOT/'evidence/video/cinematic/pr-dashboard-recording.json')['runs'][0]
    assert r['facility']=='food-a' and r['commands'][0]['ack'] and r['commands'][0]['observed_result']=='unresolved'
    assert r['core']['observations']['airflow']['value']==360 and r['core']['target_airflow']==900
    r=read(ROOT/'evidence/video/cinematic/dashboard-recordings.json')['runs'][1]
    assert r['facility']=='learning-b' and r['core']['observations']['airflow']['value']==200 and r['core']['target_airflow']==500
    d=read(ROOT/'evidence/runtime/multiapp/no_recovery/result.json')
    a=d['applications'];assert a['operations']['pid']!=a['maintenance']['pid']
    assert a['operations']['ae_origin']!=a['maintenance']['ae_origin']
    assert d['same_source_event']['source_observation_ri']
    work=d['independent_CSE_readback']['maintenance_work_order']['body']['m2m:cin']
    assert json.loads(work['con'])['status']=='inspection_required'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--final-picture',action='store_true',help='Require all three original Firefly motion clips.')
    p.add_argument('--mix',type=Path,help='Mux an approved 45s pre-mixed audio master with the picture.')
    p.add_argument('--only',nargs='+',help='Render only these named edit segments.')
    p.add_argument('--mux-only',action='store_true')
    args=p.parse_args();BIN.mkdir(parents=True,exist_ok=True);preflight()
    for name,a,b in EDIT:
        if args.mux_only or args.only and name not in args.only:continue
        shot=Shot(name,b-a,args.final_picture)
        print('Picture',name,'←',shot.note.name if shot.note else 'original motion design',flush=True)
        enc=subprocess.Popen(['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080',
                              '-r','24','-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-threads','4',
                              '-pix_fmt','yuv420p','-g','48',str(BIN/(name+'.mp4'))],stdin=subprocess.PIPE)
        try:
            for i in range(round((b-a)*FPS)):
                enc.stdin.write(shot.frame(i/FPS).tobytes())
        finally:
            enc.stdin.close();shot.close()
            if enc.wait():raise RuntimeError('Picture encode failed')
    if any(not (BIN/(name+'.mp4')).is_file() for name,_,_ in EDIT):return
    playlist=BIN/'order.txt';playlist.write_text(''.join("file '"+name+".mp4'\n" for name,_,_ in EDIT))
    output=PUBLIC if args.mix else BIN/'openSoom-pr-picture.mp4'
    mux=['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(playlist)]
    if args.mix:
        if abs(size_for(args.mix)-45)>.05:raise ValueError('Approved audio mix must span 45 seconds.')
        captions=PR/'captions.en.srt'
        mux+=['-i',str(args.mix),'-i',str(captions),'-map','0:v','-map','1:a','-map','2:s',
              '-c:a','aac','-b:a','192k','-metadata:s:a:0','language=eng','-c:s','mov_text',
              '-metadata:s:s:0','language=eng','-metadata:s:s:0','handler_name=English captions','-disposition:s:0','0',
              '-metadata','title=openSoom | The fan is running','-t','45.000']
    mux+=['-c:v','copy','-movflags','+faststart',str(output)]
    subprocess.run(mux,check=True);print(output,flush=True)


if __name__=='__main__':main()
