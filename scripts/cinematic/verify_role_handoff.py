"""Check frame identity, caption tracks and intelligible audio in the distributed film."""
import json
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageChops, ImageStat
from render_work_order import digest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'evidence/video/role-handoff'
PUBLIC=ROOT/'deliverables/video'


def decoded(path,seconds):
    frame=subprocess.check_output(['ffmpeg','-v','error','-ss',str(seconds),'-i',str(path),
            '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    return Image.frombytes('RGB',(1280,720),frame)


def compare(canvas,original,rect):
    x,y,w,h=rect
    ratio=min(w/original.width,h/original.height)
    size=(int(original.width*ratio),int(original.height*ratio))
    left=x+(w-size[0])//2
    top=y+(h-size[1])//2
    observed=canvas.crop((left,top,left+size[0],top+size[1]))
    reference=original.resize(size,Image.Resampling.LANCZOS)
    return round(sum(ImageStat.Stat(ImageChops.difference(observed,reference)).mean)/3,3)


def verify():
    manifest=json.loads((ROOT/'evidence/video/air-quality-film.json').read_text())
    film=PUBLIC/manifest['public_film']
    assert digest(film)==manifest['sha256']
    for path,sha in manifest['source_sha256'].items():
        assert digest(ROOT/path)==sha, path
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(film)]))['streams']
    video,audio,subtitles=streams
    assert (video['width'],video['height'],video['nb_frames'],video['codec_name'])==(1280,720,'1344','h264')
    assert (audio['codec_name'],subtitles['codec_name'])==('aac','mov_text')
    assert all(float(s['duration'])==56 for s in streams)
    assert all(s['tags']['language']=='eng' for s in (audio,subtitles))
    audio_cues=[]
    for s in manifest['scenes']:
        loud=subprocess.run(['ffmpeg','-v','info','-ss',str(s['start']),'-to',str(s['end']),'-i',str(film),'-map','0:a','-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True).stderr
        mean=float(re.search(r'mean_volume: ([-\d.]+) dB',loud).group(1))
        assert -31<mean<-7,(s['scene'],mean)
        audio_cues.append(mean)
    sub=subprocess.check_output(['ffmpeg','-v','error','-i',str(film),'-map','0:s','-f','srt','-']).decode().strip()
    assert sub==(PUBLIC/'openSoom-air-quality.en.srt').read_text().strip()
    source_frame=decoded(SOURCE/'operator-source.mp4',11.4).crop((250,141,1246,580))
    matches={'actual_operator_panel':compare(decoded(film,16),source_frame,(337,151,895,395))}
    for ts,name in [(24,'revision-3'),(42,'revision-4')]:
        original=Image.open(SOURCE/(name+'.png')).convert('RGB')
        matches[name]=compare(decoded(film,ts),original,(399,132,835,409))
    matches['scheduled']=compare(decoded(film,52),Image.open(SOURCE/'scheduled.png').convert('RGB'),(73,245,1126,123))
    assert max(matches.values())<3.5,matches
    print(json.dumps({'status':'passed','decoded_pixel_mean_absolute_errors_0_to_255':matches,'caption_audio_mean_dB_per_scene':audio_cues,'subtitle_track_matches_srt':True},indent=2))


if __name__=='__main__':
    verify()
