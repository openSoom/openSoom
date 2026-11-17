#!/usr/bin/env python3
"""Render the openSoom evidence-led English film. No network or hosted media services.

Requires Python/Pillow and ffmpeg/ffprobe. macOS `say` supplies optional narration;
fonts are read from the system and are never copied into the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables/video"
EVIDENCE = ROOT / "evidence/video"
W, H, FPS = 1920, 1080, 24
CREAM = "#F4F5ED"
INK = "#193D35"
GREEN = "#B8D6A4"
MUTED = "#567261"
AMBER = "#E2B76B"
WHITE = "#FCFDF7"
SCENES = [
    (12, "The operating gap", "In a food-production facility, a fan can report running while exhaust remains below the configured target. Open Soom connects that difference to an actionable, traceable response."),
    (12, "A shared operating path", "Device adapters publish a common observation contract to a real one M two M platform. Discovery, subscriptions, group queries, and access policies support one shared operating path."),
    (12, "See the facility respond", "The dashboard keeps every zone visible. This recorded interactive demo starts with a cooking-line fault, sends a permitted damper command, and then displays the observed recovery."),
    (14, "AI with an evidence trail", "The same tools are available through a Codex plugin and a standalone model runner. Here, real model-generated calls discover equipment, inspect evidence, request action, and verify the result."),
    (14, "Close the verification loop", "A command is only the beginning. The device must acknowledge it. Two fresh later observations must meet the facility profile before open Soom records a verified recovery."),
    (13, "Keep unresolved outcomes visible", "When the damper opens but airflow does not recover, the incident stays unresolved. An acknowledgement never becomes a success claim. The evidence remains available for follow-up."),
    (13, "Reusable beyond one facility", "Food production is one reference profile. A learning facility and a second vendor format use the same core, with their own targets, units, and permitted controls."),
    (10, "Open-source adoption", "Open source means easier adoption. Replay the local demo, use Codex workflows, and inspect the evidence."),
    (8, "Room to breathe", "Open Soom. Real software. Virtual equipment. Open-source air operations. Explore the code."),
]


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def probe(path):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))


FONT_PATH = next((p for p in [Path("/System/Library/Fonts/Avenir Next.ttc"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")] if p.exists()), None)
if not FONT_PATH:
    raise SystemExit("Avenir Next or DejaVu Sans is required. Install a system font; no font file is redistributed.")


def font(size, weight="regular"):
    index = {"regular": 7, "medium": 5, "bold": 0, "demi": 2}.get(weight, 7) if FONT_PATH.suffix == ".ttc" else 0
    return ImageFont.truetype(str(FONT_PATH), size, index=index)


def text(draw, xy, value, size=32, color=INK, weight="regular", spacing=10):
    draw.multiline_text(xy, str(value), font=font(size, weight), fill=color, spacing=spacing)


def wrap(draw, value, width, size=32, weight="regular"):
    lines, line = [], ""
    for word in value.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font(size, weight)) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    return "\n".join(lines + [line])


def box(draw, bounds, fill=WHITE, outline=None, radius=26, width=2):
    draw.rounded_rectangle(bounds, radius, fill=fill, outline=outline, width=width)


def arrow(draw, x1, y1, x2, y2, color=MUTED, width=4):
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2-y1, x2-x1)
    pts = [(x2, y2)] + [(x2-15*math.cos(angle+delta), y2-15*math.sin(angle+delta)) for delta in (-.5,.5)]
    draw.polygon(pts, fill=color)


def logo(draw, x, y, s=1, light=False):
    color = GREEN if light else INK
    for dy, end in ((0,50),(14,65),(28,42)):
        draw.line((x,y+dy*s,x+end*s,y+dy*s), fill=color, width=max(2,int(5*s)))
        draw.arc((x+(end-13)*s,y+(dy-14)*s,x+(end+12)*s,y+(dy+10)*s), 210, 410, fill=color, width=max(2,int(5*s)))


def base(i, dark=False):
    im = Image.new("RGB", (W,H), INK if dark else CREAM)
    d = ImageDraw.Draw(im)
    fg = WHITE if dark else INK
    for n in range(3):
        d.arc((1230-n*145,-390-n*15,2180+n*110,520+n*145), 72, 250, fill="#264A40" if dark else "#E6EBD9", width=2)
    logo(d,100,69,.65,dark)
    text(d,(160,42),"openSoom",42,fg,"bold")
    text(d,(100,125),f"{i+1:02d} / {len(SCENES):02d}   ·   {SCENES[i][1].upper()}",23,GREEN if dark else MUTED,"medium")
    text(d,(1445,57),"oneM2M HACKATHON 2026",22,GREEN if dark else MUTED,"medium")
    return im,d,fg


def footer(d, narration, note, dark=False):
    # Main caption text is at least 34 px and remains inside a 96 px safe margin.
    text(d,(100,888),note,24,GREEN if dark else MUTED)
    d.rectangle((0,950,W,H),fill="#102D27")
    caption=wrap(d,narration,1720,34)
    if caption.count("\n")>1:
        caption=wrap(d,narration,1760,32)
    if caption.count("\n")>1:
        raise ValueError("Narration caption exceeds two safe lines")
    text(d,(100,970),caption,34 if d.textbbox((0,0),caption,font=font(34))[2]<1770 else 32,WHITE,spacing=8)


def pasted(im,path,bounds,crop=None):
    src=Image.open(path).convert("RGB")
    if crop: src=src.crop(crop)
    x,y,w,h=bounds
    src=ImageOps.contain(src,(w,h),Image.Resampling.LANCZOS)
    im.paste(src,(x+(w-src.width)//2,y+(h-src.height)//2))


def facility_diagram(d,ox,oy,scale=1,labels=("COOK","WASH","PACK")):
    def p(x,y):return (ox+(x-y)*.8*scale,oy+(x+y)*.38*scale)
    for j,(x,y,w,h) in enumerate([(0,0,190,140),(190,0,190,140),(0,140,380,140)]):
        pts=[p(x,y),p(x+w,y),p(x+w,y+h),p(x,y+h)]
        shadow=[(a,b+12*scale) for a,b in pts]
        d.polygon(shadow,fill="#BACCAF")
        d.polygon(pts,fill="#E3EDDB",outline="#9DB48B",width=2)
        cx,cy=p(x+w/2,y+h/2)
        f=font(int(19*scale),"demi")
        length=d.textlength(labels[j],font=f)
        d.text((cx-length/2,cy-13),labels[j],font=f,fill=INK)


def build_frames():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"frames").mkdir(exist_ok=True)
    frames=[]
    for i,(_,title,narration) in enumerate(SCENES):
        dark=i in (0,3,5,8)
        im,d,fg=base(i,dark)
        note="Actual software execution · simulated physical equipment and measurements"
        if i==0:
            text(d,(100,220),"A running fan.",88,WHITE,"bold")
            text(d,(100,325),"An unresolved\nproblem.",88,GREEN,"bold",5)
            text(d,(104,580),"Food-production reference profile",32,"#BDCEBF","medium")
            text(d,(104,638),"Cooking line · partly closed damper",28,"#BDCEBF")
            box(d,(1100,215,1815,805),"#284D40","#3D6150")
            text(d,(1145,260),"FAN REPORT",24,GREEN,"medium")
            text(d,(1145,305),"RUNNING",54,WHITE,"bold")
            d.line((1145,405,1770,405),fill="#57705A",width=2)
            text(d,(1145,445),"OBSERVED EXHAUST",24,GREEN,"medium")
            text(d,(1145,490),"360",112,AMBER,"bold")
            text(d,(1430,565),"m³/h",35,WHITE)
            text(d,(1145,665),"Configured target: 900 m³/h",30,WHITE)
            text(d,(1145,719),"Simulated profile, not a universal standard",23,"#CAD6C3")
            note="Recorded model run: agent-379720ef883c · virtual cooking-line observations"
        elif i==1:
            text(d,(100,215),"One shared way to operate.",83,INK,"bold")
            text(d,(104,325),"Common meaning. Facility-specific decisions.",36,MUTED)
            nodes=[(110,"DEVICE ADAPTERS","Vendor A + Vendor B","Units · identity · timestamps"),(545,"oneM2M CSE","Actual ACME runtime","Discovery · subscriptions · group"),(980,"openSoom SERVICE","Policy + incident state","Permissions · ACK · verification"),(1415,"AGENT + OPERATOR","Codex / API / dashboard","One shared tool contract")]
            for n,(x,kicker,title,detail) in enumerate(nodes):
                box(d,(x,460,x+390,750),WHITE,"#D6DFCA")
                text(d,(x+28,494),kicker,23,MUTED,"demi")
                text(d,(x+28,555),wrap(d,title,330,34,"bold"),34,INK,"bold")
                text(d,(x+28,659),wrap(d,detail,330,24),24,MUTED)
                if n<3: arrow(d,x+393,600,x+432,600)
            text(d,(110,795),"Native oneM2M group queries and access control are executed in the CSE.",29,MUTED)
        elif i==2:
            text(d,(100,200),"Every zone. Every step.",80,INK,"bold")
            box(d,(96,325,1380,857),WHITE,"#D4DECA")
            pasted(im,OUT/"assets/food-fault-dashboard.jpg",(110,339,1256,504),(245,390,1445,995))
            text(d,(1430,350),"COOKING LINE",23,MUTED,"demi")
            text(d,(1430,407),"360",98,"#98713A","bold")
            text(d,(1430,523),"m³/h observed",32,MUTED)
            text(d,(1430,608),"1 open incident",35,INK,"demi")
            text(d,(1430,668),"0 verified recoveries",29,MUTED)
            text(d,(1430,741),"Recorded UI capture",24,MUTED)
            note="Interactive UI demo: demo-eea1329dfb · actual service state, virtual readings"
        elif i==3:
            text(d,(100,215),"AI acts through\nthe same tools.",79,WHITE,"bold",5)
            text(d,(105,450),"Recorded live API run",32,GREEN,"demi")
            text(d,(105,510),"Model: gpt-5-mini",29,WHITE)
            text(d,(105,560),"Run: agent-379720ef883c",27,"#BDCEBF")
            text(d,(105,668),"Codex CLI plugin + MCP\ntransport verified separately.",31,GREEN,spacing=12)
            box(d,(900,205,1815,825),"#284D40","#4D6C54")
            calls=[("discover","18:40:28","Accessible resources"),("read_group","18:40:29","Native CSE fan-out"),("read_evidence","18:40:31","Fresh profile evidence"),("request_action","18:40:34","Scoped damper request"),("verify_result","18:40:36","ACK received · pending"),("verify_result","18:40:38","Later result · verified")]
            for n,(name,t,detail) in enumerate(calls):
                y=245+n*91
                text(d,(940,y),f"{n+1:02d}",25,GREEN,"medium")
                text(d,(1000,y-3),name,31,WHITE,"demi")
                text(d,(1600,y),t,24,GREEN)
                text(d,(1000,y+36),detail,23,"#BDCEBF")
            note="Actual model-generated calls · shared MCP/service path · no Codex model-turn claim"
        elif i==4:
            text(d,(100,215),"A command is not a result.",82,INK,"bold")
            text(d,(105,330),"ACK confirms receipt. Later observations establish recovery.",35,MUTED)
            items=[("01","COMMAND","18:40:34.728","Set damper to 100%"),("02","DEVICE ACK","18:40:35.969","Separate device response"),("03","2 FRESH SAMPLES","After acknowledgement","Profile conditions checked"),("04","VERIFIED","18:40:38.061","Incident recovered")]
            for n,(num,label,t,detail) in enumerate(items):
                x=110+n*440
                d.ellipse((x,465,x+65,530),fill=INK if n<3 else "#638657")
                text(d,(x+16,473),num,27,WHITE,"demi")
                if n<3: arrow(d,x+82,497,x+410,497,"#93AF81",5)
                text(d,(x,570),label,27,INK,"bold")
                text(d,(x,620),t,26,MUTED)
                text(d,(x,676),wrap(d,detail,390,26),26,MUTED)
            box(d,(110,762,1805,854),"#DFEBD5")
            text(d,(150,783),"Virtual airflow: 360 to 1,035 m³/h",41,INK,"demi")
            text(d,(1060,798),"This profile's target: 900 m³/h",29,MUTED)
            note="Same recorded model run · command cmd-607d6d77947b · two-sample recovery policy"
        elif i==5:
            text(d,(100,215),"Acknowledged.",89,WHITE,"bold")
            text(d,(100,325),"Still unresolved.",89,AMBER,"bold")
            text(d,(106,502),"A second real-model run keeps\nthe failed outcome visible.",34,"#BDCEBF",spacing=15)
            text(d,(106,665),"Run: agent-479f866b7e84",27,GREEN)
            text(d,(106,715),"Command: cmd-838cfc0f207e",25,"#BDCEBF")
            box(d,(1120,215,1810,825),"#284D40","#5D6D4E")
            rows=[("Device ACK","received"),("Damper reported","100%"),("Airflow observed","360 m³/h"),("Configured target","900 m³/h")]
            for n,(a,b) in enumerate(rows):
                y=255+n*100
                text(d,(1165,y),a,27,"#BDCEBF")
                text(d,(1165,y+35),b,41,WHITE,"demi")
            box(d,(1160,705,1768,785),"#715631")
            text(d,(1205,724),"OUTCOME: UNRESOLVED",31,"#FFE2A8","bold")
            note="Actual hosted-model negative test · fresh post-ACK observations remain deficient"
        elif i==6:
            text(d,(100,210),"Built for more than one facility.",78,INK,"bold")
            for x,title,sub,adapter,labels in [(110,"Food production","Cooking · washing · packing","Vendor A: m³/h + boolean",("COOK","WASH","PACK")),(1010,"Learning spaces","Studio · meeting · lounge","Vendor B: L/s + RUN / STOP",("STUDIO","MEET","LOUNGE"))]:
                box(d,(x,360,x+790,775),WHITE,"#D6DFCA")
                text(d,(x+35,390),title,41,INK,"bold")
                text(d,(x+35,448),sub,27,MUTED)
                facility_diagram(d,x+360,515,.72,labels)
                text(d,(x+35,718),adapter,25,MUTED,"medium")
            text(d,(260,818),"Same core + tools     /     Separate profiles, targets and adapter mappings",34,INK,"demi")
            note="Two implemented facility profiles and wire-format adapters · diagrams are illustrative"
        elif i==7:
            text(d,(100,215),"Open source. Open evidence.",83,INK,"bold")
            text(d,(105,335),"Adoption is part of the product.",38,MUTED)
            cards=[("01","SET UP","Guided Codex workflows\nLocal runtime diagnostics"),("02","REPLAY","Account-free virtual demo\nBounded live-model mode"),("03","EXTEND","Profiles + device adapters\nShared contracts and tools")]
            for n,(num,title,body) in enumerate(cards):
                x=110+n*580
                box(d,(x,465,x+540,765),WHITE,"#D6DFCA")
                text(d,(x+34,500),num,27,MUTED,"medium")
                text(d,(x+34,560),title,41,INK,"bold")
                text(d,(x+34,645),body,29,MUTED,spacing=12)
            text(d,(112,814),"Apache-2.0 source   ·   CC BY 4.0 original non-code materials",31,INK,"demi")
            note="Codex CLI / MCP host checks are distinct from standalone live-model execution"
        else:
            logo(d,760,270,1.6,True)
            text(d,(895,232),"openSoom",100,WHITE,"bold")
            text(d,(333,448),"Know what changed. Know what worked.",61,GREEN,"demi")
            text(d,(485,580),"Open-source air operations, built on oneM2M.",36,"#BDCEBF")
            box(d,(493,697,1430,792),"#335745","#6F8A66")
            text(d,(550,718),"github.com/openSoom/openSoom",42,WHITE,"demi")
            note="Real oneM2M software. Virtual physical devices. No certified ventilation or health claim."
        footer(d,narration,note,dark)
        p=OUT/"frames"/f"scene-{i+1:02d}.png"
        im.save(p,optimize=True)
        frames.append(p)
        if i==2:
            recovered=im.copy();rd=ImageDraw.Draw(recovered)
            pasted(recovered,OUT/"assets/food-recovered-dashboard.jpg",(110,339,1256,504),(245,390,1445,995))
            rd.rectangle((1410,340,1820,850),fill=CREAM)
            text(rd,(1430,350),"COOKING LINE",23,MUTED,"demi")
            text(rd,(1430,407),"1,035",90,"#517943","bold")
            text(rd,(1430,523),"m³/h observed",32,MUTED)
            text(rd,(1430,608),"0 open incidents",33,INK,"demi")
            text(rd,(1430,668),"1 verified recovery",29,MUTED)
            text(rd,(1430,741),"Later UI capture",24,MUTED)
            recovered.save(OUT/"frames/scene-03-recovered.png",optimize=True)
    return frames


def stamp(t):
    return f"{int(t//3600):02d}:{int(t%3600//60):02d}:{int(t%60):02d},000"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frames-only",action="store_true")
    parser.add_argument("--no-voice",action="store_true")
    parser.add_argument("--voice",default="Samantha")
    args=parser.parse_args()
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    frames=build_frames()
    storyboard=[]; elapsed=0; srt=[]
    for i,(duration,title,narration) in enumerate(SCENES):
        storyboard.append({"scene":i+1,"start":elapsed,"duration":duration,"title":title,"narration":narration,"frame":str(frames[i].relative_to(ROOT))})
        srt.append(f"{i+1}\n{stamp(elapsed)} --> {stamp(elapsed+duration)}\n{textwrap.fill(narration,95)}\n")
        elapsed+=duration
    (OUT/"storyboard.json").write_text(json.dumps({"duration_seconds":elapsed,"language":"en","scenes":storyboard},indent=2)+"\n")
    (OUT/"captions.en.srt").write_text("\n".join(srt))
    (OUT/"narration.en.txt").write_text("\n\n".join(s[2] for s in SCENES)+"\n")
    if args.frames_only:
        print("Rendered nine reviewable 1920x1080 scene frames",flush=True);return
    voice=not args.no_voice and bool(shutil.which("say"))
    audio_checks=[]
    with tempfile.TemporaryDirectory(prefix="opensoom-video-") as temp:
        tmp=Path(temp); clips=[]
        for i,((duration,_,narration),frame) in enumerate(zip(SCENES,frames)):
            audio=tmp/f"voice-{i}.aiff"
            if voice:
                textpath=tmp/f"voice-{i}.txt";textpath.write_text(narration)
                run(["say","-v",args.voice,"-r","162","-f",textpath,"-o",audio])
                actual=float(probe(audio)["format"].get("duration",0))
                if actual<=0:raise RuntimeError("Speech audio is empty. The host speech service needs permission; --no-voice produces a captioned silent alternative.")
                if actual>duration-.2:raise RuntimeError(f"Scene {i+1} narration {actual}s exceeds slot {duration}s")
                audio_checks.append({"scene":i+1,"voice_seconds":actual,"slot_seconds":duration})
            clip=tmp/f"clip-{i}.mp4"
            command=["ffmpeg","-hide_banner","-loglevel","error","-y"]
            if i==2:
                sequence=tmp/"ui-captures.txt"
                sequence.write_text(f"file '{frame}'\nduration 6\nfile '{OUT/'frames/scene-03-recovered.png'}'\nduration 6\nfile '{OUT/'frames/scene-03-recovered.png'}'\n")
                command += ["-f","concat","-safe","0","-i",sequence]
            else:
                command += ["-loop","1","-framerate",str(FPS),"-i",frame]
            if voice:command += ["-i",audio]
            else:command += ["-f","lavfi","-i","anullsrc=r=48000:cl=stereo"]
            # Keep evidence readable: subtle whole-frame drift, no altered values or fabricated motion.
            vf=f"fps={FPS},scale=1950:1098,crop=1920:1080:x='15+8*sin(t/7)':y='9+4*sin(t/9)',fade=t=in:st=0:d=0.35,fade=t=out:st={duration-.35}:d=0.35,format=yuv420p"
            af=f"adelay=250|250,apad,atrim=duration={duration},afade=t=out:st={duration-.2}:d=0.2,loudnorm=I=-16:TP=-1.5:LRA=11"
            command += ["-vf",vf,"-af",af,"-t",str(duration),"-r",str(FPS),"-c:v","libx264","-preset","veryfast","-crf","21","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-ar","48000","-ac","2","-movflags","+faststart",clip]
            run(command);clips.append(clip)
            print(f"Encoded scene {i+1}/{len(SCENES)}",flush=True)
        concat=tmp/"concat.txt";concat.write_text("\n".join(f"file '{p}'" for p in clips)+"\n")
        final=OUT/"openSoom-demo-en.mp4"
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",concat,"-c","copy","-movflags","+faststart","-metadata","title=openSoom — From observation to verified outcome","-metadata","comment=Real oneM2M software execution; simulated physical devices. English evidence-led demonstration.",final])
    metadata=probe(final)
    metadata.get("format", {})["filename"] = "deliverables/video/openSoom-demo-en.mp4"
    (EVIDENCE/"ffprobe.json").write_text(json.dumps(metadata,indent=2)+"\n")
    manifest={"file":str(final.relative_to(ROOT)),"sha256":hashlib.sha256(final.read_bytes()).hexdigest(),"bytes":final.stat().st_size,"nominal_duration":elapsed,"actual_duration":metadata["format"]["duration"],"font":str(FONT_PATH),"font_redistributed":False,"narration":{"engine":"macOS say" if voice else "none","voice":args.voice if voice else None,"rate_wpm":162 if voice else None,"checks":audio_checks},"frames":[{"path":str(p.relative_to(ROOT)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in frames]}
    (EVIDENCE/"render-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"Created {final}: {final.stat().st_size/1e6:.1f} MB",flush=True)


if __name__=="__main__":main()
