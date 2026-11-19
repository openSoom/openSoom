"""Render the evaluation film from retained operator video and the archived cloud workbench replay."""
import json
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw
from render_work_order import digest, duration, font, run, srt_clock

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'evidence/video/role-handoff'
CLOUD = ROOT / 'evidence/runtime/option-c/technician-handoff.json'
VIDEO = ROOT / 'deliverables/video'
WIDTH, HEIGHT, FPS = 1280, 720, 24
CHAPTERS = [
    (0, 'operator-question', 'A ventilation command went through. Can the operator clear the air-quality alert?'),
    (6.5, 'operator-readings', 'Fine particles stay at 60, above the zone limit of 45. Carbon dioxide falls within its limit.'),
    (14.25, 'operator-decision', 'Both targets must be met together. The operator keeps the alert open for the next shift.'),
    (21, 'maintenance-incident', 'In a separate incident, the damper acknowledged a full-opening command. Airflow reached only 40 percent of its target.'),
    (30, 'independent-reading', 'The bridge queries the independent shaft sensor through the MEC service. It reports only 35 percent open.'),
    (38.5, 'maintenance-decision', 'With that reading, the maintenance app updates the same work order. Check actuator travel and position feedback first.'),
    (47.75, 'field-handoff', 'The technician schedules the check. Through oneM2M, operations sees the update. The incident stays open.'),
]
END = 56
OP_BG = '#142e31'
CLOUD_BG = '#172b40'
INK = '#152d37'
CREAM = '#f1f2e9'
DIM = '#adc4c0'
LIME = '#c9e590'
ICE = '#a5d9eb'
AMBER = '#ffcb85'
TYPE = lru_cache(maxsize=None)(font)


def label(draw, x, y, string, size=23, color=CREAM, bold=False, anchor='la'):
    draw.text((x,y), str(string), font=TYPE(size,bold), fill=color, anchor=anchor)


def wrap(draw, text, width, size):
    lines=['']
    for word in text.split():
        add=(lines[-1]+' '+word).strip()
        if lines[-1] and draw.textlength(add,font=TYPE(size))>width:
            lines.append(word)
        else:
            lines[-1]=add
    return lines


def lines(draw, x, y, text, size, step, **kwargs):
    for i,line in enumerate(text.split('\n')):
        label(draw,x,y+i*step,line,size,**kwargs)


def place(im, img, xy, limit):
    w,h=img.size
    ratio=min(limit[0]/w,limit[1]/h)
    box=(int(w*ratio),int(h*ratio))
    scaled=img.resize(box,Image.Resampling.LANCZOS)
    x,y=xy
    im.paste(scaled,(x+(limit[0]-box[0])//2, y+(limit[1]-box[1])//2))


def base(index, when, rid, source):
    cloud=index>=3
    bg=CLOUD_BG if cloud else OP_BG
    accent=ICE if cloud else LIME
    im=Image.new('RGB',(WIDTH,HEIGHT),bg)
    d=ImageDraw.Draw(im)
    label(d,48,22,'openSoom',29,CREAM,True)
    label(d,210,29,'FIELD OPERATIONS',15,DIM,True)
    label(d,1232,31,'VIRTUAL EQUIPMENT   /   REAL SOFTWARE',16,DIM,True,'ra')
    d.line((48,70,1232,70),fill='#46616a',width=1)
    d.rounded_rectangle((48,96,60,110),radius=3,fill=accent)
    case='CASE B   /   SEPARATE CLOUD LOW-AIRFLOW INCIDENT' if cloud else 'CASE A   /   LOCAL AIR-QUALITY INCIDENT'
    label(d,70,92,case,19,accent,True)
    label(d,1232,93,source,18,DIM,False,'ra')
    d.line((48,555,1232,555),fill='#526771',width=1)
    label(d,50,566,rid,18,DIM)
    d.rectangle((0,609,1280,720),fill='#0a1d24')
    cap=wrap(d,CHAPTERS[index][2],1144,24)
    assert len(cap)<=2,cap
    for i,l in enumerate(cap):
        label(d,640,658+(i-(len(cap)-1)/2)*30,l,24,'#f6f8ef',anchor='mm')
    d.rectangle((0,716,int(1280*when/END),720),fill=accent)
    return im,d


def render_frame(index, when, source_frame, images, operator, cloud):
    order=cloud['technician_http']['reviewed_order']
    entry=cloud['technician_http']['entry']
    ids = [
        ('Local run  '+operator['run_id']+'     /     command  '+operator['command_id'],'Recorded local oneM2M console'),
        ('Local run  '+operator['run_id']+'     /     original reading  '+operator['latest']['cin_ri'],'Recorded local oneM2M console'),
        ('Local incident  '+operator['incident']['id']+'     /     persisted state  '+operator['incident']['status'],'Recorded local oneM2M console'),
        ('Cloud run  '+cloud['run_id']+'     /     work order  '+order['work_order_id'],'Workbench replay · archived cloud response'),
        ('oneM2M sensor response  '+cloud['native_cse_path']['response']['ri']+'     /     '+order['sample']['sensor_id'],'Archived cloud sensor response'),
        ('Same work order  '+order['work_order_id']+'     /     revision 4  '+order['resource_id'],'Workbench replay · archived cloud response'),
        ('Scheduled entry  '+entry['resource_id']+'     /     same work order  '+order['work_order_id'],'Workbench replay · archived cloud response'),
    ]
    im,d=base(index,when,*ids[index])
    if index<3:
        titles=['Can we clear\nthe alert?', 'Particles stay\nabove target', 'Keep the\nalert open']
        lines(d,48,169,titles[index],41,50,color=CREAM,bold=True)
        if index==0:
            lines(d,49,315,'After ventilation,\ncompare both readings.',24,34,color=DIM)
        elif index==1:
            label(d,49,310,'PM2.5   µg/m³',18,LIME,True)
            label(d,48,350,'60',78,AMBER,True)
            label(d,152,402,'limit 45',25,CREAM)
        else:
            lines(d,49,316,'First time in range',20,29,color=DIM)
            label(d,48,358,'Not reached',32,AMBER,True)
            label(d,48,426,'Status in the incident log',19,DIM)
            label(d,48,460,operator['incident']['status'].upper(),27,CREAM,True)
        # Scroll position of the actual recording is fixed. Preserve the
        # original application pixels, including its run selector and limits.
        screen=source_frame.crop((250,141,1246,580))
        place(im,screen,(337,151),(895,395))
    elif index in (3,5):
        if index==3:
            lines(d,48,162,'Low airflow\nafter a full\nopening request',38,46,bold=True)
            label(d,48,342,'360 / 900',47,AMBER,True)
            label(d,48,412,'m³/h · actual / target',22,DIM)
            label(d,48,478,'Work order  /  revision 3',20,ICE)
            shot=images['revision-3']
        else:
            lines(d,48,162,'Choose the\nfirst inspection',42,50,bold=True)
            lines(d,48,317,'Same work order',22,31,color=DIM)
            label(d,48,358,'Revision 3 → 4',31,ICE,True)
            label(d,48,436,'Maintenance app',21,CREAM)
            shot=images['revision-4']
        place(im,shot,(399,132),(835,409))
    elif index==4:
        label(d,48,154,'How far did the shaft actually move?',47,CREAM,True)
        for yy,name,num,color in [(270,'Commanded opening',100,ICE),(370,'Independent shaft position',35,AMBER)]:
            label(d,50,yy,name,22,CREAM)
            d.rounded_rectangle((386,yy+4,1054,yy+31),12,fill='#354b5a')
            progress = min(1.0, (when-CHAPTERS[index][0]+0.05)/0.65)
            d.rounded_rectangle((386,yy+4,386+int(668*num/100*progress),yy+31),12,fill=color)
            label(d,1214,yy-9,f'{num}%',42,color,True,'ra')
        label(d,50,489,'ETSI MEC 046   /   GET /queries/sensor_data   /   HTTP 200',21,DIM)
    else:
        label(d,48,160,'oneM2M shares the inspection status',44,CREAM,True)
        d.rounded_rectangle((48,235,1231,380),radius=12,fill='#ffffff')
        place(im,images['scheduled'],(73,245),(1126,123))
        d.line((50,401,1227,401),fill='#506571')
        label(d,50,430,'OPERATIONS',18,ICE,True)
        label(d,50,470,'Incident still open',33,CREAM,True)
        label(d,680,430,'MAINTENANCE',18,ICE,True)
        label(d,680,470,'Inspection scheduled',33,CREAM,True)
    return im


def verify_inputs(operator,cloud):
    assert digest(SOURCE/'operator-source.mp4')==operator['source_clip_sha256']
    assert operator['incident']['status']=='open' and operator['first_target_at'] is None
    assert operator['command_status']=='unresolved'
    assert (operator['latest']['pm25'],operator['latest']['co2'],operator['profile_targets']['pm25'])==(60,720,45)
    order=cloud['technician_http']['reviewed_order']
    initial=cloud['before_service_admission']['orders'][0]
    assert initial['work_order_id']==order['work_order_id'] and (initial['revision'],order['revision'])==(3,4)
    assert (order['requested_pct'],order['airflow'],order['configured_target_m3_h'],order['sample']['value'])==(100,360,900,35)
    assert order['priority']=='inspect_actuator_feedback' and order['mode']=='mec046'
    assert order['provider_receipt']['lookup_status']==200 and order['provider_receipt']['lookup_path']=='/queries/sensor_data'
    entry=cloud['technician_http']['entry']
    assert entry['work_order_ri']==order['resource_id'] and entry['action']=='scheduled'
    assert cloud['operator_after_field_entry']['incident_status']=='open' and cloud['operator_after_field_entry']['projected_disposition']['resource_id']==entry['resource_id']


def render():
    operator=json.loads((SOURCE/'operator-incident.json').read_text())
    cloud=json.loads(CLOUD.read_text())
    verify_inputs(operator,cloud)
    images={key:Image.open(SOURCE/(key+'.png')).convert('RGB') for key in ['revision-3','revision-4','scheduled']}
    frame_bytes=WIDTH*HEIGHT*3
    input_args=['ffmpeg','-v','error','-i',str(SOURCE/'operator-source.mp4'),'-f','rawvideo','-pix_fmt','rgb24','-']
    with tempfile.TemporaryDirectory(prefix='opensoom-role-film-') as tmpdir:
        tmp=Path(tmpdir)
        vo=[]; cues=[];stamps=[]
        for i,(start,key,line) in enumerate(CHAPTERS):
            end=CHAPTERS[i+1][0] if i+1<len(CHAPTERS) else END
            voice=tmp/f'{i}.aiff'
            run('/usr/bin/say','-v','Samantha','-r','163','-o',voice,line.replace('oneM2M', 'one em two em'))
            seconds=duration(voice)
            if seconds>end-start-.30: raise ValueError(f'{key} voice {seconds:.2f} exceeds scene length {end-start:.2f}')
            vo.append(voice)
            cues.append(f'{i+1}\n{srt_clock(start)} --> {srt_clock(end)}\n{line}\n')
            stamps.append({'scene':key,'start':start,'end':end,'narration_seconds':round(seconds,3)})
        srt=VIDEO/'openSoom-air-quality.en.srt'
        srt.write_text('\n'.join(cues))
        silent=tmp/'picture.mp4'
        encoder=['ffmpeg','-y','-v','error','-f','rawvideo','-s','1280x720','-pix_fmt','rgb24','-r',str(FPS),'-i','-','-an','-vf','format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','18',str(silent)]
        with subprocess.Popen(input_args,stdout=subprocess.PIPE) as src, subprocess.Popen(encoder,stdin=subprocess.PIPE) as dest:
            idx=0; source_frame=None; eof=False
            for f in range(END*FPS):
                when=f/FPS
                if idx+1<len(CHAPTERS) and when>=CHAPTERS[idx+1][0]: idx+=1
                if idx<3 and not eof:
                    pixels=src.stdout.read(frame_bytes)
                    if pixels: source_frame=Image.frombytes('RGB',(WIDTH,HEIGHT),pixels)
                    else: eof=True
                dest.stdin.write(render_frame(idx,when,source_frame,images,operator,cloud).tobytes())
            dest.stdin.close()
            if dest.wait() or src.wait(): raise RuntimeError('Source read or picture encode failed')
        # Delay each spoken line to its scene. An explicit silent bed keeps
        # the MP4 length fixed even when the last utterance ends earlier.
        movie=VIDEO/'openSoom-air-quality-720p.mp4'
        delays=[f'[{i+1}:a]aresample=48000,adelay={int((s+.16)*1000)}:all=1[a{i}]' for i,(s,_,_) in enumerate(CHAPTERS)]
        mix=''.join(f'[a{i}]' for i in range(len(vo)))+f'amix=inputs={len(vo)}:normalize=0,apad[audio]'
        run('ffmpeg','-y','-v','error','-i',silent,*[av for f in vo for av in ('-i',f)],'-i',srt,'-filter_complex',';'.join([*delays,mix]),'-map','0:v','-map','[audio]','-map',f'{len(vo)+1}:s','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-c:s','mov_text','-metadata:s:a:0','language=eng','-metadata:s:s:0','language=eng','-movflags','+faststart','-t',str(END),movie)
        run('ffmpeg','-v','error','-i',movie,'-map','0:v','-map','0:a','-f','null','-')
        files=[SOURCE/p for p in ('operator-source.mp4','operator-incident.json','revision-3.png','revision-4.png','scheduled.png')]+[CLOUD,ROOT/'src/opensoom/technician_web/workbench.js',ROOT/'src/opensoom/technician_web/index.html',ROOT/'src/opensoom/technician_web/workbench.css']
        result={'title':'Keep the alert open. Choose the first inspection.','public_film':movie.name,'sha256':digest(movie),'captions_sha256':digest(srt),'seconds':duration(movie),'resolution':[WIDTH,HEIGHT],'fps':FPS,'method':'Actual operator console capture from a local ACME trial. Case B is a different recorded cloud maintenance incident; the shipped workbench renders the archived response locally. All equipment readings are virtual. Native MEC 046 GET supplied the recorded 35%. No new cloud execution or human field inspection was filmed. English narration, burned captions and selectable subtitles.','operator_run':operator['run_id'],'operator_incident':operator['incident']['id'],'cloud_run':cloud['run_id'],'cloud_work_order':cloud['technician_http']['reviewed_order']['work_order_id'],'scenes':stamps,'source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in files},'tools':['scripts/cinematic/retain_role_source.py','scripts/cinematic/capture_role_workbench.cjs','scripts/cinematic/render_role_handoff.py']}
        (ROOT/'evidence/video/air-quality-film.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'seconds':result['seconds'],'sha256':result['sha256']}))

if __name__=='__main__':
    render()
