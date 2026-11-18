"""Produce original English narration, timed captions and a low-level original score."""
import argparse
import html
import json
from pathlib import Path
import subprocess
import tempfile
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "deliverables/video/cinematic/demo"
SAMPLE_RATE = 48000
VOICE = "Samantha"


def spoken(line):
    for token, sound in (("oneM2M","one em two em"),("OpenSoom","Open Soom"),("openSoom","Open Soom"),
                         ("MQTT","em cue tee tee"),("HTTPS","H T T P S"),("TLS","T L S"),("Codex","Code ex")):
        line=line.replace(token,sound)
    return line


def read_mono(file,rate=1.):
    args=["ffmpeg","-nostdin","-v","error","-i",str(file),"-af",f"atempo={rate:.5f}","-ar",str(SAMPLE_RATE),"-ac","1","-f","f32le","-"]
    return np.frombuffer(subprocess.check_output(args),dtype="<f4")


def timestamp(sec):
    ms=round(sec*1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def split_caption(line):
    # A cue must be comfortably readable across two screen lines.
    if len(line)<84: return [line]
    words=line.split()
    target=len(words)/2
    choices=range(max(3,int(target)-5),min(len(words)-2,int(target)+6))
    split=min(choices,key=lambda n:abs(n-target)-(3 if words[n-1].endswith(('.',',','?')) else 0))
    return [' '.join(words[:split]),' '.join(words[split:])]

def write_captions(work,cues):
    # At speech rates above 20 characters/second, use concise subtitles and keep
    # numbers together. The unabridged spoken text remains in script.en.json.
    edits={
        'A Korean performance assessment covered three hundred and':'A Korean study assessed 301 schools',
        'one schools after their kitchens had received ventilation improvements.':'after ventilation upgrades in their kitchens.',
        'In that group, seventeen point nine percent still received':'In that group, 17.9% still received',
        'inspect the equipment with the command, acknowledgement and later measurements together.':'review the command, acknowledgement and later readings together.',
        'These two runs demonstrate how the':'Both runs followed the same procedure.',
        'same operating procedure produces different, traceable decisions.':'Each produced a different, traceable decision.',
        'We also tested a separate deployment with an operations':'A separate test ran two applications.',
        'application and a maintenance application running as independent processes.':'Operations and maintenance ran as independent processes.',
        'Operations checks the zone and requests a permitted action.':'Operations requests a permitted action for the zone.',
        'Maintenance uses the same event identifier to create a work order for inspection.':'Maintenance opens an inspection order for the same event.',
        'The two applications own different decisions.':'Each application owns a decision.',
        'The separate applications test includes an attempted command from maintenance.':'In the separate test, maintenance tries to issue a command.',
        'The demonstration runs locally. A deployment in a':'The demo runs locally.',
        'working facility would also need site authentication and commissioning.':'A working facility also needs authentication and commissioning.',
        'The local facility kept the same serving platform throughout this experiment.':'The local facility kept the same serving platform.',
        'A maintainer installs the local service and checks readiness.':'A maintainer installs and checks the service.',
        'A manager can then inspect the facility from the dashboard or through the Codex plugin.':'A manager can inspect the facility from the dashboard or Codex plugin.',
    }
    for cue in cues:
        cue['text']=edits.get(cue['text'],cue['text'])
    (work/'demo-cues.json').write_text(json.dumps(cues,indent=2))
    srt='\n\n'.join(f"{i}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{html.escape(c['text'])}" for i,c in enumerate(cues,1))+'\n'
    (MEDIA/'captions.en.srt').write_text(srt)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,default=ROOT/'tmp/demo-film')
    parser.add_argument('--refresh-captions',action='store_true',help='Retain existing narration and caption timings.')
    args=parser.parse_args(); work=args.work
    work.mkdir(parents=True,exist_ok=True)
    if args.refresh_captions:
        write_captions(work,json.loads((work/'demo-cues.json').read_text()))
        return
    shots=json.loads((MEDIA/'script.en.json').read_text())['shots']
    total=sum(s['seconds'] for s in shots)
    # Mix designed from scratch. The breath-like bed is intentionally quiet under speech.
    voice=np.zeros(total*SAMPLE_RATE,dtype=np.float32)
    cues=[]; offset=0
    with tempfile.TemporaryDirectory(dir=work) as temp:
        for shot in shots:
            files=[]
            for i,line in enumerate(shot['lines']):
                p=Path(temp)/f"{shot['id']}-{i}.aiff"
                subprocess.run(["say","-v",VOICE,"-r","166","-o",str(p),spoken(line)],check=True)
                files.append(p)
            raw=[read_mono(p) for p in files]
            if any(len(v)<SAMPLE_RATE*.4 for v in raw): raise RuntimeError("Voice synthesis produced an empty line.")
            duration=shot['seconds'];lead=.85 if shot['id'] in ('opening','close') else .52
            tail=1.05 if shot['id'] in ('opening','close') else .50
            gap=.32
            rate=sum(len(v) for v in raw)/SAMPLE_RATE/(duration-lead-tail-gap*(len(raw)-1))
            cursor=offset+lead
            for line,p in zip(shot['lines'],files):
                audio=read_mono(p,rate)
                fade=min(int(.009*SAMPLE_RATE),len(audio)//2)
                audio=audio.copy()
                audio[:fade]*=np.linspace(0,1,fade);audio[-fade:]*=np.linspace(1,0,fade)
                start=round(cursor*SAMPLE_RATE)
                voice[start:start+len(audio)]=audio
                parts=split_caption(line);length=len(audio)/SAMPLE_RATE
                sizes=[len(s.split()) for s in parts];t=cursor
                for part,n in zip(parts,sizes):
                    piece=length*n/sum(sizes)
                    cues.append(dict(shot=shot['id'],start=round(t,3),end=round(t+piece,3),text=part))
                    t+=piece
                cursor+=length+gap
            if cursor-gap > offset+duration+.05:raise ValueError("Narration boundary overrun")
            offset+=duration
    nonzero=abs(voice)>0.025
    if not nonzero.any():raise ValueError('Empty speech')
    voice*=0.139/np.sqrt(np.mean(voice[nonzero]**2))
    score=np.zeros_like(voice)
    # Sparse D-minor/add-nine voicings. Rounded envelope leaves air between attacks.
    for index,sec in enumerate(range(0,total,6)):
        dur=min(8,total-sec)
        t=np.arange(dur*SAMPLE_RATE)/SAMPLE_RATE
        chord=((50,57,64),(46,53,60),(53,60,67),(48,55,62))[index//2%4]
        env=np.minimum(1,t/1.3)*np.minimum(1,(dur-t)/2.0)
        frag=np.zeros_like(t)
        for j,midi in enumerate(chord):
            f=440*2**((midi-69)/12)
            frag+=np.sin(2*np.pi*f*t+j*1.65+.25*np.sin(t*.6))*.0032
            frag+=np.sin(2*np.pi*(f*2+.33)*t+1.1)*.0010
        if index%2==0:
            hit=np.maximum(t-.3,0)
            frag+=(t>.3)*.005*np.exp(-hit*.8)*np.sin(2*np.pi*440*2**((chord[-1]+12-69)/12)*hit)
        score[sec*SAMPLE_RATE:(sec+dur)*SAMPLE_RATE]+=(frag*env).astype('f')
    mixed=np.tanh(voice+score)*.97
    output=work/'demo-mix.wav'
    with wave.open(str(output),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(SAMPLE_RATE)
        wav.writeframes((mixed*32767).astype('<i2').tobytes())
    write_captions(work,cues)
    print(f"Wrote {total}s speech/score and {len(cues)} caption cues.")


if __name__=='__main__':main()
