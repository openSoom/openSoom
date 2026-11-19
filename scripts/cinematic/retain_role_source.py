"""Keep one recorded operator trial and its archived incident for the two-case film."""
import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from render_work_order import digest, run

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evidence/video/role-handoff'


def retain(capture, database):
    trial = json.loads((capture / 'capture.json').read_text())['cases']['air_quality_persistent']
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        def get(kind, key):
            return json.loads(connection.execute('select data from records where kind=? and key=?', (kind, key)).fetchone()[0])
        command = get('commands', trial['command'])
        incident = get('incident_history', command['incident_id'])
    assert command['run_id'] == trial['run_id'] and incident['status']=='open'
    outcome = command['air_quality_outcome']
    assert outcome['latest']['pm25']==60 and outcome['latest']['co2']==720
    # Retain acquisition order in a small distributable source clip.
    frames=trial['frames']
    assert all(a['seconds'] < b['seconds'] for a,b in zip(frames,frames[1:]))
    output=OUT/'operator-source.mp4'
    OUT.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory(prefix='opensoom-operator-film-') as tmp:
        sequence=Path(tmp)/'sequence.txt'
        pieces=[]
        for ix,frame in enumerate(frames):
            duration=frames[ix+1]['seconds']-frame['seconds'] if ix+1<len(frames) else .4
            if ix==0: duration+=frame['seconds']
            source=(capture/frame['file']).resolve()
            assert source.parent==capture.resolve() and "'" not in str(source)
            pieces.extend([f"file '{source}'",f'duration {duration:.4f}'])
        pieces.append(f"file '{source}'")
        sequence.write_text('\n'.join(pieces)+'\n')
        run('ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',sequence,'-vf','fps=24,format=yuv420p','-c:v','libx264','-crf','16','-preset','medium','-an','-movflags','+faststart',output)
    evidence={'method':'Original ordinary Chrome screenshots in acquisition order; variable capture times resampled to 24 fps. Command and incident independently extracted from the persisted operations store of the same local ACME trial at run closure.',
              'scope':'Virtual equipment. UI frames are an actual local operator recording.',
              'run_id':trial['run_id'],'command_id':trial['command'],'zone_id':command['zone_id'],'incident':{k:incident[k] for k in ('id','status','reason','updated_at','latest_rqi','archived_at')},
              'command_status':command['status'],'ack_at':command['ack_at'],'ack_cin_ri':command['ack_source']['cin_ri'],'profile_targets':outcome['targets'],
              'baseline':outcome['baseline'],'latest':outcome['latest'],'first_target_at':outcome['first_target_at'],
              'browser_frames':len(frames), 'source_clip_sha256':digest(output)}
    (OUT/'operator-incident.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path);parser.add_argument('database',type=Path)
    args=parser.parse_args()
    retain(args.capture,args.database)
