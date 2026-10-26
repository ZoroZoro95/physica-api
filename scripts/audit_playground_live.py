"""Opt-in, bounded live interpretation audit; never part of offline unit tests."""
import argparse
import json
import math
from pathlib import Path
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx


CASES = [
    dict(id='ground', question='A point particle launches from level ground at 16 m/s, 30 degrees above the +x horizontal. Use g=10 m/s^2. Ignore drag. Simulate until its first return to ground and label its horizontal range.'),
    dict(id='cliff', question='A point particle starts at (7,33) metres and is launched horizontally LEFT at 15 m/s. Horizontal ground is at y=-12 m. Use g=10 m/s^2, no drag. Simulate until ground contact. Show labelled vertical drop and horizontal distance.'),
    dict(id='incline', question='A stationary smooth wedge has lower-left base at (0,0), horizontal base width 50 m, and its top slopes DOWN to the right at 30 degrees to the horizontal. A point particle is projected from the midpoint of the sloping top at 5 m/s perpendicular outward to the slope. It flies freely under g=10 m/s^2, no drag, until first contact. Show distance along the slope from launch to impact. It does not slide.'),
    dict(id='finite_stairs', question='A point particle launches horizontally right at 10 m/s from the top departure corner (0,0) of a staircase descending right. There are exactly 5 steps, each 1 m high and 1 m wide. No other surfaces. g=9.8 m/s^2. Simulate for 3 seconds. Do not extend this finite staircase.'),
    dict(id='missing_speed', question='A point particle is launched horizontally from 45 m above level ground. Use g=10 m/s^2. Build its trajectory until contact. The launch speed is not specified.'),
    dict(id='drag', question='A ball launches from ground at 20 m/s and 45 degrees. Use g=10 m/s^2 and INCLUDE linear air drag with drag acceleration equal to -0.2 times its velocity. Simulate until landing.'),
]


def check(case, response):
    id = case['id']
    if id in ('missing_speed','drag'):
        expected = 'needs_clarification' if id == 'missing_speed' else 'unsupported'
        assert response['status'] == expected, response.get('reason')
        assert response.get('scene') is None and response.get('simulation') is None
        return
    assert response['status'] == 'review', response.get('reason')
    s, sim = response['scene'], response['simulation']
    assert len(s['particles']) == 1, 'Expected one particle'
    assert s['id'] == sim['scene_id'] and s['revision'] == sim['revision']
    p = s['particles'][0]
    def close(a,b):
        assert math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-7), f'{a} != {b}'
    close(s['gravity'],9.8 if id == 'finite_stairs' else 10)
    if id == 'finite_stairs':
        stair = s['surfaces'][0]
        assert len(s['surfaces']) == 1 and stair['kind'] == 'staircase' and stair['count'] == 5
        close(stair['rise'],1); close(stair['run'],1)
        assert stair['direction'] == 'right'
        close(p['velocity']['x'],10); close(p['velocity']['y'],0)
        close(p['position']['x'],0); close(p['position']['y'],0)
        assert sim['status'] == 'time_limit' and sim['contact'] is None
        close(sim['samples'][-1]['t'],3)
        return
    hit=sim['contact']
    assert sim['status']=='contact' and hit
    specs = s.get('measurements') or []
    measurements=sim.get('measurements') or []
    def require_distance(axis,value):
        def compatible(m):
            if m['axis']==axis:
                return True
            # A straight line between equal-height points is also horizontal
            # range; do not require a particular API spelling of that geometry.
            if m['axis']=='direct' and axis in ('horizontal','vertical') and len(m['points'])==2:
                other='y' if axis=='horizontal' else 'x'
                return math.isclose(m['points'][0][other],m['points'][1][other],abs_tol=1e-7,rel_tol=0)
            return False
        matches=[m for m in measurements if m['kind']=='distance' and compatible(m) and m['status']=='ready' and math.isclose(m['value'],value,rel_tol=1e-7,abs_tol=1e-7)]
        assert matches, f'Missing engine-backed {axis} measurement {value}'
        matched_ids={m['id'] for m in matches}
        assert any(spec['id'] in matched_ids and any(spec[key].get('feature')=='contact' for key in ['start','end']) for spec in specs), 'Measurement used guessed fixed endpoints'
    if id=='ground':
        close(p['velocity']['x'],16*math.cos(math.pi/6)); close(p['velocity']['y'],8)
        close(hit['time'],1.6); close(hit['position']['y'],p['position']['y'])
        require_distance('horizontal',16*math.cos(math.pi/6)*1.6)
    elif id=='cliff':
        close(p['position']['x'],7); close(p['position']['y'],33)
        close(p['velocity']['x'],-15); close(p['velocity']['y'],0)
        close(hit['time'],3); close(hit['position']['x'],-38); close(hit['position']['y'],-12)
        require_distance('vertical',45); require_distance('horizontal',45)
    else:
        wedge=next(item for item in s['surfaces'] if item['kind']=='wedge')
        assert not wedge['rising']
        close(wedge['width'],50); close(wedge['height'],50*math.tan(math.pi/6))
        close(wedge['origin']['x'],0); close(wedge['origin']['y'],0)
        close(p['position']['x'],25); close(p['position']['y'],wedge['height']/2)
        close(p['velocity']['x'],2.5); close(p['velocity']['y'],5*math.cos(math.pi/6))
        t=2*5/(10*math.cos(math.pi/6))
        close(hit['time'],t)
        require_distance('direct',.5*10*math.sin(math.pi/6)*t*t)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Required: calls the locally configured model provider')
    parser.add_argument('--replay',type=Path,help='Recheck saved report IDs without contacting the provider')
    parser.add_argument('--api-url',default='http://127.0.0.1:8001')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--interval',type=float,default=65,help='Seconds between requests; no automatic retries')
    parser.add_argument('--case',choices=[c['id'] for c in CASES],action='append')
    args=parser.parse_args()
    if args.live == bool(args.replay): parser.error('Choose exactly one of --live or --replay')
    if args.replay:
        if args.output.resolve()==args.replay.resolve(): parser.error('Replay output must preserve the original report')
        results=[]
        cases={case['id']:case for case in CASES}
        root=Path(__file__).resolve().parents[1]/'questions/debug_reports/playground-agent'
        for original in json.loads(args.replay.read_text()):
            row=dict(case=original['case'],report_id=original.get('report_id'),original_status=original['status'])
            try:
                report_id=str(UUID(row['report_id']))
                report=json.loads((root/report_id/'report.json').read_text())
                case=cases[row['case']]
                assert report['question']==case['question'], 'Saved report question mismatch'
                check(case,report)
                row['status']='passed'
            except (AssertionError,ValueError,TypeError,KeyError,OSError) as exc:
                row.update(status='failed',error=str(exc))
            results.append(row)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results,indent=2))
        return int(any(row['status']!='passed' for row in results))
    u=urlparse(args.api_url)
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
        parser.error('Only local playground API URLs are allowed')
    if not 0<=args.interval<=120: parser.error('interval must be 0..120 seconds')
    cases=[c for c in CASES if not args.case or c['id'] in args.case]
    results=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=90,trust_env=False,follow_redirects=False) as client:
        for index, case in enumerate(cases):
            if index: time.sleep(args.interval)
            row=dict(case=case['id'],question=case['question'])
            try:
                r=client.post(args.api_url.rstrip('/')+'/v1/generate',json={'question':case['question']})
                row['http_status']=r.status_code
                r.raise_for_status()
                data=r.json()
                row.update(report_id=data.get('report_id'),generation_status=data.get('status'),reason=data.get('reason'))
                check(case,data)
                row['status']='passed'
            except (AssertionError,ValueError,httpx.HTTPError,KeyError,TypeError,StopIteration) as exc:
                row.update(status='failed',error=str(exc))
            results.append(row)
            args.output.write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps(row),flush=True)
    return int(any(row['status']!='passed' for row in results))


if __name__=='__main__':
    raise SystemExit(main())
