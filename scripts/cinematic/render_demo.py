"""Edit the five-minute presentation film from its browser rushes and trace records.

Run demo_audio.py first. All identifier overlays below are read from the public
records at render time. Use --frames for a contact sheet before rendering.
"""
import argparse
import bisect
import functools
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "deliverables/video/cinematic/demo"
FLY = MEDIA.parent / "firefly"
WORK = ROOT / "tmp/demo-film"
EV = ROOT / "evidence/video/cinematic"
W,H,FPS = 1920,1080,24
PAPER = "#F1F0E9"
INK = "#0A2423"
AIR = "#C6F3CE"
MINT = "#80CAAD"
AMBER = "#F3B176"
PALE = "#C4CEC9"
RULE = "#33524C"
IVORY = "#FAF9F2"
GRAY = "#50635C"


def js(path): return json.loads(path.read_text())


@functools.lru_cache(maxsize=128)
def font(size,style="medium"):
    if style=="mono":
        return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc",size)
    return ImageFont.truetype("/System/Library/Fonts/Avenir Next.ttc",size,
                              index={"medium":5,"bold":0,"demi":2,"regular":7,"heavy":8}[style])


def txt(image,x,y,value,size,fill=IVORY,style="medium"):
    ImageDraw.Draw(image).text((round(x),round(y)),str(value),font=font(size,style),fill=fill,anchor="lt")


def line(image,coords,fill=RULE,width=2):
    ImageDraw.Draw(image).line(coords,fill=fill,width=width)


def rect(image,box,fill,outline=None,width=1):
    ImageDraw.Draw(image).rectangle(box,fill=fill,outline=outline,width=width)


def reflow(line,max_width,size):
    words=line.split();lines=['']
    for word in words:
        candidate=(lines[-1]+' '+word).strip()
        if font(size).getlength(candidate)>max_width and lines[-1]: lines.append(word)
        else:lines[-1]=candidate
    return lines


def mark(image,x,y,scale=.8,light=True):
    col=AIR if light else INK
    dr=ImageDraw.Draw(image)
    # Stacked airflow motif from the product wordmark.
    for i,(a,b) in enumerate([(0,33),(8,44),(0,29)]):
        yy=y+i*8*scale
        dr.rounded_rectangle((x+a*scale,yy,x+b*scale,yy+3.5*scale),radius=1.5*scale,fill=col)


def header(image,section,num,kind,light=False):
    fg=INK if light else IVORY;muted=GRAY if light else PALE
    mark(image,68,51,.85,not light);txt(image,119,44,"openSoom",32,fg,"demi")
    txt(image,298,51,section.upper(),20,muted,"mono")
    label=f"{kind.upper()}   /   {num:02d}"
    txt(image,W-68-font(18,"mono").getlength(label),52,label,18,muted,"mono")
    line(image,(68,100,W-68,100),"#B7C5BD" if light else RULE,1)


def sub_title(image,kicker,title,subtitle="",light=False):
    main=INK if light else IVORY;sub=GRAY if light else PALE
    txt(image,78,155,kicker.upper(),22,GRAY if light else MINT,"mono")
    txt(image,75,208,title,82,main,"demi")
    if subtitle:txt(image,80,326,subtitle,31,sub,"regular")


@functools.lru_cache(maxsize=256)
def caption_overlay(text):
    im=Image.new("RGB",(W,114),"#0C1C1B")
    rect(im,(69,22,73,87),MINT)
    lines=reflow(text,1718,35)
    yy=36 if len(lines)==1 else 16
    for i,row in enumerate(lines):txt(im,98,yy+i*45,row,35,IVORY)
    return im


def ease(x):return min(1,max(0,x))**2*(3-2*min(1,max(0,x)))


class Source:
    def __init__(self,file,size,start=0,end=None,duration=None,crop=None,photo=False):
        self.size=size
        w,h=size
        args=["ffmpeg","-nostdin","-loglevel","error","-threads","2"]
        if photo:
            args+=["-loop","1","-framerate",str(FPS),"-i",str(file)]
            filt=f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},zoompan=z='1+0.00010*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={FPS}"
        else:
            args+=["-ss",str(start),"-i",str(file)]
            filt=(f"crop={crop}," if crop else "")+f"scale={w}:{h}:flags=bilinear"
            if end and duration: filt+=f",setpts={duration/(end-start):.8f}*(PTS-STARTPTS)"
            filt+=f",fps={FPS},tpad=stop_mode=clone:stop_duration=2"
        args+=["-an","-vf",filt,"-t",str(duration),"-pix_fmt","rgb24","-f","rawvideo","-"]
        self.p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    def next(self):
        raw=self.p.stdout.read(self.size[0]*self.size[1]*3)
        if len(raw)!=self.size[0]*self.size[1]*3:raise ValueError("Source ended unexpectedly.")
        return Image.frombytes("RGB",self.size,raw)
    def close(self):
        self.p.stdout.close()
        if self.p.poll() is None:self.p.terminate()
        self.p.wait()


def grad(size):
    w,h=size
    a=np.linspace(225,22,w,dtype=np.uint8);a=np.tile(a,(h,1))
    return Image.fromarray(a)


def node(d,x,y,title,detail,light=True):
    main=INK if light else IVORY
    rect(d,(x,y,x+484,y+159),"#FFFFFF" if light else "#19342E")
    txt(d,x+26,y+30,title,38,main,"demi")
    txt(d,x+26,y+100,detail,23,GRAY if light else MINT,"mono")


def media_image(name):
    with Image.open(FLY/(name+'.png')) as src:
        return ImageOps.fit(src.convert("RGB"),(W,966),centering=(.50,.5))


class Sequence:
    def __init__(self,shot,num,data,preview=False):
        self.s=shot;self.num=num;self.id=shot['id'];self.secs=shot['seconds']
        self.data=data; self.preview=preview;self.media=None;self.bounds=None
        self.static=Image.new("RGB",(W,966),INK);self.chips=[]
        self.layers=[];self.overlay=None;self.photo=None;self.source_spec=None
        self.inset=None;self.tail=None
        if self.id in ('food','operate','learning','unresolved'):
            self.live()
        elif self.id in ('opening','close'): self.hero()
        else:self.editorial()

    def layer(self,start,box,fn):
        x,y,w,h=box
        im=Image.new("RGBA",(w,h));fn(im)
        self.layers.append((start,x,y,im))

    def hero(self):
        opening=self.id=='opening'
        self.photo=media_image('kitchen' if opening else 'plant')
        motion=FLY/('kitchen-motion.mp4' if opening else 'plant-motion.mp4')
        if motion.is_file() and opening:
            motion_duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(motion)]))
            self.source_spec=(motion,(W,966),0,motion_duration,min(5.0,self.secs),None,False)
        else:self.source_spec=(FLY/('kitchen.png' if opening else 'plant.png'),(W,966),0,None,self.secs,None,True)
        self.alpha=grad((W,966));self.dark=Image.new('RGB',(W,966),'#051816')
        self.overlay=Image.new('RGBA',(W,966));header(self.overlay,self.s['section'],self.num,'Illustrative facility')
        def title(im):
            txt(im,0,3,'VENTILATION OPERATIONS' if opening else 'OPEN-SOURCE AIR OPERATIONS',23,AIR,'mono')
            if opening:
                txt(im,0,73,'The fan is running.',104,IVORY,'demi')
                txt(im,0,210,'Did the zone recover?',88,IVORY,'regular')
            else:
                txt(im,0,69,'openSoom',138,IVORY,'demi')
                txt(im,3,255,'github.com/openSoom/openSoom',39,AIR,'medium')
        self.layer(.18,(78,302,1500,378),title)

    def live(self):
        food=self.id in ('food','operate')
        before=self.id in ('food','learning')
        run=self.data['runs']['food' if food else 'learning'];q=run['cues']
        start=max(0,q['facility']-1.4) if before else q['action']-.8
        end=q['action']-.8 if before else q['end']-5.0
        self.bounds=(477,159,1373,773)
        self.source_spec=(MEDIA/('food-session.webm' if food else 'learning-session.webm'),
                          (1373,773),start,end,self.secs,'1440:810:0:0',False)
        im=self.static;header(im,self.s['section'],self.num,'Recorded dashboard')
        txt(im,70,165,'FOOD PRODUCTION' if food else 'LEARNING SPACE',21,MINT,'mono')
        words={'food':['Cooking','line.'],'operate':['Verify the','outcome.'],'learning':['Learning','studio.'],'unresolved':['Still below','target.']}[self.id]
        for i,v in enumerate(words):txt(im,66,229+86*i,v,70,IVORY,'demi')
        line(im,(70,437,403,437),RULE)
        if self.id=='operate':
            txt(im,71,454,'FINAL OUTCOME',20,MINT,'mono')
        num={'food':'360','operate':'1,035','learning':'200','unresolved':'200'}[self.id]
        txt(im,68,489,num,89,AIR if self.id=='operate' else AMBER,'demi')
        txt(im,72,607,'m³/h observed',29,PALE)
        txt(im,72,674,'Profile target',24,PALE)
        txt(im,72,720,'900 m³/h' if food else '500 m³/h',47,IVORY,'demi')
        txt(im,70,860,'VIRTUAL EQUIPMENT',18,MINT,'mono')
        txt(im,70,899,run['runId'],17,PALE,'mono')
        rect(im,(472,154,1855,937),'#66867D')
        if self.id=='learning':
            self.inset=media_image('learning')
            self.inset=Image.composite(Image.new('RGB',(W,966),'#06201D'),self.inset,grad((W,966)))
            header(self.inset,'Second facility',self.num,'Firefly illustration')
            txt(self.inset,81,388,'The learning studio.',95,IVORY,'demi')
            txt(self.inset,86,540,'A different supplier. A different airflow target.',41,AIR)

    def editorial(self):
        id=self.id
        light=id in ['context','protocol','twoapps','outage','adopt']
        im=self.static=Image.new("RGB",(W,966),PAPER if light else INK)
        h={'context':'Source reporting','protocol':'Secure protocol capture','twoapps':'CSE execution record',
           'receipts':'CSE readback','rights':'Access control record','agent':'Archived hosted-model run',
           'outage':'Recorded test reconstruction','adopt':'Installation guide'}[id]
        header(im,self.s['section'],self.num,h,light)
        if id=='context':
            txt(im,79,164,'AFTER INSTALLATION',22,GRAY,'mono')
            txt(im,65,231,'17.9%',170,INK,'demi')
            txt(im,81,459,'rated inadequate',54,INK,'regular')
            txt(im,80,567,'301 upgraded school kitchens',38,GRAY)
            line(im,(82,739,807,739),'#B4C2B7',2)
            txt(im,81,779,'2025 performance assessment',27,INK)
            txt(im,81,830,'Reported by Yonhap, 11 October 2026',23,GRAY)
            for i in range(301):
                col=i%22;row=i//22;x=1014+col*35;y=222+row*42
                ImageDraw.Draw(im).ellipse((x,y,x+18,y+18),fill='#B7C9BF' if i>=54 else '#AF5B2D')
            txt(im,1015,848,'Each dot represents one assessed school.',23,GRAY)
        elif id=='protocol':
            sub_title(im,'Recorded oneM2M transaction','One observation. Two protocols.','A device publishes. An application retrieves the same resource.',True)
            for x,title,detail in [(80,'Device adapter','MQTT / TLS 1.3'),(718,'ACME CSE','CONTENT INSTANCE'),(1352,'Management app','HTTPS / TLS 1.3')]:
                node(im,x,485,title,detail)
            line(im,(564,565,718,565),'#93ADA0',3);line(im,(1202,565,1352,565),'#93ADA0',3)
            txt(im,82,743,'CREATE  /  2001',26,GRAY,'mono');txt(im,1353,743,'RETRIEVE  /  2000',26,GRAY,'mono')
            txt(im,722,742,self.data['ri'],27,INK,'mono')
        elif id=='twoapps':
            sub_title(im,'Independent subscriptions','One event reaches two apps.','The device publishes a single abnormal cooking-line observation.',True)
            node(im,78,523,'Virtual device','PUBLISH OBSERVATION')
            node(im,691,523,'oneM2M platform','CSE NOTIFICATIONS')
            node(im,1362,399,'Operations','RETRIEVE / REQUEST')
            node(im,1362,654,'Maintenance','RETRIEVE / INSPECT')
            for coords in ((563,601,691,601),(1176,601,1260,601),(1260,475,1260,730),(1260,475,1362,475),(1260,730,1362,730)):
                line(im,coords,'#668B7B',3)
            txt(im,80,848,'Source resource  '+self.data['same']['source_observation_ri'],26,GRAY,'mono')
        elif id=='receipts':
            sub_title(im,'Separate readbacks','Two records for the same event.')
            infos=(('OPERATIONS APP','Command outcome','Unresolved after ACK',self.data['report_ri']),
                   ('MAINTENANCE APP','Inspection work order','Inspection required',self.data['order_ri']))
            for i,(label,title,val,rid) in enumerate(infos):
                x=79+891*i
                def draw(p,label=label,title=title,val=val,rid=rid):
                    rect(p,(0,0,850,324),'#183832')
                    txt(p,30,39,label,22,MINT,'mono');txt(p,28,103,title,51,IVORY,'demi')
                    txt(p,30,200,val,35,AMBER);txt(p,30,269,'CSE RESOURCE  '+rid,20,PALE,'mono')
                self.layer(.4+i*.7,(x,410,852,325),draw)
            line(im,(79,805,1820,805),RULE)
            txt(im,80,852,'EVENT  '+self.data['same']['event_id'],24,PALE,'mono')
        elif id=='rights':
            sub_title(im,'Role-based access','Who can write a command?')
            entries=[('Maintenance AE','Create equipment command','4103  DENIED'),
                     ('Operations AE','Write maintenance work order','4103  DENIED'),
                     ('Observer AE','Read another facility','4103  DENIED')]
            for i,(actor,action,result) in enumerate(entries):
                y=374+i*139
                def draw(p,actor=actor,action=action,result=result):
                    line(p,(0,0,1756,0),RULE)
                    txt(p,0,35,actor,42,IVORY,'demi');txt(p,548,39,action,32,PALE);txt(p,1320,39,result,30,AMBER,'mono')
                self.layer(.3+i*1.25,(79,y,1760,105),draw)
            txt(im,79,852,'Scoped local test identities  /  oneM2M access-control policies',25,PALE)
        elif id=='agent':
            sub_title(im,'Model-selected tools','The model checks twice.')
            names=['Discover','Read group','Read evidence','Request action','Verify result','Verify result']
            details=['Facility resources','Current observations','Incident and limits','Set damper to 100%','Awaiting observations','Recovery verified']
            for i,(title,detail) in enumerate(zip(names,details)):
                x=80+(i%3)*589;y=383+(i//3)*187
                def draw(p,i=i,title=title,detail=detail):
                    rect(p,(0,0,548,155),'#193832' if i<5 else '#D0E9D4')
                    clr=IVORY if i<5 else INK
                    txt(p,21,25,f'0{i+1}',20,MINT if i<5 else GRAY,'mono')
                    txt(p,71,20,title,38,clr,'demi');txt(p,71,94,detail,25,PALE if i<5 else GRAY)
                self.layer(.25+i*.85,(x,y,550,157),draw)
            txt(im,80,851,self.data['model']+'  /  '+self.data['agent_id']+'  /  6 recorded calls',23,PALE,'mono')
        elif id=='outage':
            sub_title(im,'Separate local distributed experiment','During a central outage','Two facility CSEs and one central CSE ran as separate local processes.',True)
            for i,(name,status) in enumerate([('Central CSE','Interrupted'),('Food facility','Local control continued'),('Returned intent','Expired request rejected')]):
                y=420+i*126
                line(im,(80,y,1820,y),'#B5C6B9',2);txt(im,81,y+28,name,35,INK,'demi');txt(im,547,y+33,status,30,GRAY)
            txt(im,1145,479,'14.635 s',100,INK,'demi');txt(im,1151,622,'central interruption',30,GRAY)
            txt(im,80,852,'Local control stayed with the original facility CSE.',25,GRAY)
        elif id=='adopt':
            sub_title(im,'Installing the local fixture','A second site starts with a profile.','The account-free demo runs on the verified macOS arm64 environment.',True)
            rect(im,(80,423,1115,789),'#15352F')
            txt(im,115,462,'LOCAL QUICKSTART',21,MINT,'mono')
            for i,v in enumerate(['uv sync --locked --python 3.12','uv run --no-sync python '+chr(92),'  scripts/cse_bootstrap.py secure','uv run --no-sync opensoom start --secure','uv run --no-sync opensoom doctor']):
                txt(im,116,525+i*43,v,26,IVORY,'mono')
            txt(im,1202,458,'Facility profile',43,INK,'demi');txt(im,1204,528,'Zones, targets, allowed actions',28,GRAY)
            txt(im,1202,635,'Vendor adapter',43,INK,'demi');txt(im,1204,705,'Units, formats, device reports',28,GRAY)
            txt(im,82,852,'README   /   docs/extending.md   /   profiles/',23,GRAY,'mono')

    def open(self):
        if self.source_spec:self.media=Source(*self.source_spec)
        if self.id=='opening' and self.source_spec[0].suffix=='.mp4':
            self.tail=Source(FLY/'kitchen.png',(W,966),0,None,self.secs-self.source_spec[4],None,True)

    def frame(self,t):
        im=self.static.copy()
        if self.media and (self.id not in ('opening','close') or t<self.source_spec[4]-.0001):
            m=self.media.next()
        else:m=self.tail.next() if self.tail else self.photo
        if self.id in ('opening','close'):
            if self.source_spec[0].suffix=='.mp4' and t>=self.source_spec[4]-.65 and t<self.source_spec[4]:
                m=Image.blend(m,self.photo,ease((t-(self.source_spec[4]-.65))/.65))
            im=Image.composite(self.dark,m,self.alpha)
            im.paste(self.overlay,(0,0),self.overlay)
        elif self.bounds and m:
            im.paste(m,self.bounds[:2])
        for start,x,y,layer in self.layers:
            p=ease((t-start)/.52)
            if p==0:continue
            if p<1:
                alpha=layer.getchannel('A').point(lambda a:round(a*p))
                im.paste(layer,(x,round(y+(1-p)*14)),alpha)
            else:im.paste(layer,(x,y),layer)
        dr=ImageDraw.Draw(im)
        if self.id=='context':
            # Highlight the assessed subset as one connected group of dots.
            reached=int(54*ease((t-2.2)/4))
            for i in range(reached,54):
                x=1014+(i%22)*35;y=222+(i//22)*42;dr.ellipse((x,y,x+18,y+18),fill='#B7C9BF')
        if self.id=='learning' and t<3.65:
            if t<3:im=self.inset.copy()
            else:im=Image.blend(self.inset,im,ease((t-3)/.65))
        if self.id=='protocol':
            for xa,xb in [(570,710),(1211,1345)]:
                z=(t/2.6)%1;x=xa+(xb-xa)*z
                dr.ellipse((x-5,559,x+5,569),fill='#287E65')
        if self.id=='twoapps':
            for y in (475,730):
                x=1262+95*((t/2.1)%1)
                dr.ellipse((x-5,y-5,x+5,y+5),fill='#248063')
            if t>=8:
                rect(im,(77,823,1816,917),PAPER)
                if t<16:
                    txt(im,80,842,'01   Both AEs retrieved  '+self.data['same']['source_observation_ri'],26,INK,'mono')
                elif t<23:
                    txt(im,80,842,'02   Operations linked a device ACK to its command.',26,INK,'mono')
                else:
                    txt(im,80,842,'03   Maintenance recorded an independent inspection work order.',26,INK,'mono')
        if self.id=='receipts' and t>11:
            rect(im,(78,814,1850,939),INK)
            txt(im,79,831,'Source observation  '+self.data['same']['source_observation_ri'],25,PALE,'mono')
            txt(im,79,881,'Both CSE resource readbacks returned 2000.',24,MINT)
        if self.id=='outage':
            # Convey the elapsed observation window without inventing a time of handover.
            x=1150;end=1815;y=710
            rect(im,(x,y,end,y+12),'#CBD6CE')
            frac=min(1,max(0,(t-1.5)/14.635))
            if frac>0:rect(im,(x,y,x+(end-x)*frac,y+12),'#567C69')
        return im

    def close(self):
        if self.media:self.media.close()
        if self.tail:self.tail.close()


def load_sources():
    independent=js(ROOT/'evidence/runtime/multiapp/no_recovery/result.json')
    back=independent['independent_CSE_readback']
    report=back['operations_report']['body']['m2m:cin'];order=back['maintenance_work_order']['body']['m2m:cin']
    assert json.loads(report['con'])['status']=='unresolved_after_ack'
    assert json.loads(order['con'])['status']=='inspection_required'
    assert all(independent['access_checks'][k]['rsc']==4103 for k in ['maintenance_control_denied','operations_cannot_write_work_order'])
    original=js(ROOT/'evidence/runtime/cse-mqtt-tls-smoke.json')['checks']
    ri=original['native_mqtt_create']['body']['m2m:cin']['ri']
    assert original['https_same_resource']['body']['m2m:cin']['ri']==ri
    browser=js(EV/'dashboard-recordings.json')['runs'];agent=js(ROOT/'evidence/agent/release-live-recovery.json')
    assert [x['name'] for x in agent['tool_calls']]==['discover','read_group','read_evidence','request_action','verify_result','verify_result']
    return dict(same=independent['same_source_event'],report_ri=report['ri'],order_ri=order['ri'],ri=ri,
                runs={r['name']:r for r in browser},agent_id=agent['id'],model=agent['model'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='*',help='Render named shot IDs and retain previously rendered shots.')
    parser.add_argument('--frames',action='store_true',help='Output contact-sheet review frames only.')
    args=parser.parse_args()
    work=WORK/'shots';work.mkdir(parents=True,exist_ok=True)
    shots=js(MEDIA/'script.en.json')['shots'];data=load_sources()
    cues=js(WORK/'demo-cues.json'); starts=[c['start'] for c in cues]
    length=sum(s['seconds'] for s in shots); offset=0
    for n,s in enumerate(shots,1):
        if args.only and s['id'] not in args.only:offset+=s['seconds'];continue
        seq=Sequence(s,n,data)
        if args.frames:
            if seq.source_spec and seq.bounds:
                src=seq.source_spec
                seq.media=Source(src[0],src[1],src[2]+2,None,1,src[5])
            canvas=seq.frame(min(s['seconds']-1,7));seq.close()
            canvas.thumbnail((768,388));canvas.save(work/(s['id']+'.jpg'));offset+=s['seconds'];continue
        print(f"Editing {n:02} {s['id']} …",flush=True)
        seq.open()
        enc=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
            '-s','1920x1080','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','21',
            '-threads','4','-pix_fmt','yuv420p','-g','48',str(work/(s['id']+'.mp4'))],stdin=subprocess.PIPE)
        frame=Image.new('RGB',(W,H),'#0C1C1B')
        try:
            for i in range(FPS*s['seconds']):
                t=i/FPS;global_time=offset+t
                frame.paste(seq.frame(t),(0,0))
                ci=bisect.bisect_right(starts,global_time)-1
                caption=cues[ci]['text'] if ci>=0 and global_time<cues[ci]['end'] else ''
                frame.paste(caption_overlay(caption),(0,966))
                line(frame,(0,1077,W,1077),RULE,3);line(frame,(0,1077,round(W*global_time/length),1077),MINT,3)
                enc.stdin.write(frame.tobytes())
        finally:
            enc.stdin.close();seq.close()
            if enc.wait():raise RuntimeError("Encoder failed.")
        offset+=s['seconds']
    if args.frames:return
    if any(not (work/(s['id']+'.mp4')).exists() for s in shots):return
    lines=''.join("file '"+s['id']+".mp4'\n" for s in shots)
    (work/'order.txt').write_text(lines)
    out=ROOT/'deliverables/video/openSoom-demo-5min.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(work/'order.txt'),'-i',str(WORK/'demo-mix.wav'),
        '-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','160k','-movflags','+faststart',str(out)],check=True)
    print(out,flush=True)


if __name__=='__main__':main()
