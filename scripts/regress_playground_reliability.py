"""Independent analytic scenarios and invariant checks through the public API.

Set PHYSICA_RELIABILITY_REPORT=/tmp/...json to export representative scenes for
the browser audit. No LLM, answer key, or curriculum manifest is used here.
"""
import itertools
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app
from audit_playground_live import check as check_live

EXAMPLES = {}
COUNTS = {}


def ref(feature):
    return dict(kind='object', target='P', feature=feature)


class Reliability(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def post(self, route, body):
        r = self.api.post('/v1/'+route, json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def make(self, surface, position, speed, angle, g, measurements=True):
        commands = [
            dict(op='add_surface', surface=surface),
            dict(op='add_particle', id='P', position=position),
            dict(op='set_launch', particle_id='P', speed=speed, direction='angle', angle_deg=angle),
        ]
        if measurements:
            for id, label, axis in [('height', 'Vertical distance', 'vertical'), ('range', 'Horizontal distance', 'horizontal')]:
                commands.append(dict(op='set_measurement', measurement=dict(kind='distance', id=id,
                    label=label, start=ref('launch'), end=ref('contact'), axis=axis, side=-1)))
        return self.post('scenes/apply', dict(scene={'gravity': g}, commands=commands))

    def check(self, family, scene, expected_time, expected_point, example=None):
        COUNTS[family] = COUNTS.get(family, 0) + 1
        horizon = expected_time+1
        result = self.post('simulations', dict(scene=scene, particle_id='P', max_time=horizon, samples=17))
        hit = result['contact']
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit['time'], expected_time, places=7)
        for axis in ['x', 'y']:
            self.assertAlmostEqual(hit['position'][axis], expected_point[axis], places=7)
        p = scene['particles'][0]
        for sample in result['samples']:
            t, v, q = sample['t'], sample['velocity'], sample['position']
            self.assertAlmostEqual(q['x'], p['position']['x']+p['velocity']['x']*t, places=7)
            self.assertAlmostEqual(q['y'], p['position']['y']+p['velocity']['y']*t-scene['gravity']*t*t/2, places=7)
            self.assertAlmostEqual(v['x'], p['velocity']['x'], places=7)
            self.assertAlmostEqual(v['y'], p['velocity']['y']-scene['gravity']*t, places=7)
            # Mechanical energy per unit mass is invariant under constant gravity.
            energy = (v['x']**2+v['y']**2)/2+scene['gravity']*q['y']
            initial = (p['velocity']['x']**2+p['velocity']['y']**2)/2+scene['gravity']*p['position']['y']
            self.assertAlmostEqual(energy, initial, places=7)
        coarse = self.post('simulations', dict(scene=scene, particle_id='P', max_time=horizon, samples=2))
        self.assertEqual(coarse['contact'], hit)
        self.assertEqual(coarse['measurements'], result['measurements'])
        boundary = self.post('simulations', dict(scene=scene, particle_id='P', max_time=expected_time, samples=2))
        self.assertIsNotNone(boundary['contact'], 'contact lost at the analytical time boundary')
        self.assertLessEqual(boundary['samples'][-1]['t'], expected_time)
        before = self.post('simulations', dict(scene=scene, particle_id='P', max_time=expected_time-1e-7, samples=2))
        self.assertIsNone(before['contact'], 'a genuinely later collision was pulled into the horizon')
        mesh = self.post('geometry', scene)['meshes']
        # The reported face must also be part of the actual rendered boundary.
        boundary = mesh[0].get('collision_faces')
        if boundary:
            face = next(f for f in boundary if f['face'] == hit['face'])
            a, b, q = face['from'], face['to'], hit['position']
            dx, dy = b['x']-a['x'], b['y']-a['y']
            self.assertLess(abs((q['x']-a['x'])*dy-(q['y']-a['y'])*dx)/math.hypot(dx, dy), 1e-7)
        if example:
            EXAMPLES[example] = dict(name=example, scene=scene, simulation=result, meshes=mesh)
        return result

    def test_level_ground_matrix(self):
        for u, theta, g, sign in itertools.product([8, 16], [15, 45, 75, 90], [9.8, 10], [1, -1]):
            with self.subTest(u=u, theta=theta, g=g, sign=sign):
                origin = dict(x=17, y=23)
                scene = self.make(dict(kind='ground', id='ground', y=23, x_min=-1000, x_max=1000),
                    origin, u, theta if sign == 1 else 180-theta, g)
                t = 2*u*math.sin(math.radians(theta))/g
                q = dict(x=17+sign*u*math.cos(math.radians(theta))*t, y=23)
                self.check('level_ground', scene, t, q,
                    'ground-'+str(sign) if (u, theta, g) == (16, 45, 10) else None)

    def test_cliff_matrix(self):
        for h, u, g, sign in itertools.product([.2, 45, 80], [0, 5, 15], [9.8, 10], [1, -1]):
            with self.subTest(h=h, u=u, g=g, sign=sign):
                scene = self.make(dict(kind='ground', id='ground', y=-12, x_min=-1000, x_max=1000),
                    dict(x=7, y=-12+h), u, 0 if sign == 1 else 180, g)
                t = math.sqrt(2*h/g)
                self.check('cliff', scene, t, dict(x=7+sign*u*t, y=-12),
                    'cliff-'+str(sign) if (h, u, g) == (45, 15, 10) else None)

    def test_incline_matrix(self):
        for u, alpha, g, rising in itertools.product([2, 3], [15, 30, 60], [9.8, 10], [True, False]):
            with self.subTest(u=u, alpha=alpha, g=g, rising=rising):
                width, slope = 25, math.radians(alpha if rising else -alpha)
                height = width*math.tan(abs(slope))
                start = dict(x=17+width/2, y=23+height/2)
                scene = self.make(dict(kind='wedge', id='wedge', origin=dict(x=17,y=23),
                    width=width, height=height, rising=rising), start, u, 90+math.degrees(slope), g)
                t = 2*u/(g*math.cos(slope))
                q = dict(x=start['x']-u*math.sin(slope)*t, y=start['y']+u*math.cos(slope)*t-g*t*t/2)
                result = self.check('incline', scene, t, q,
                    'incline-'+str(rising) if (u, alpha, g) == (3, 30, 10) else None)
                self.assertEqual(result['contact']['face'], 'top')

    def test_stairs_matrix_and_corners(self):
        for h, w, u, g in [(1,1,10,9.8), (1,1,10,10), (.4,1.2,7,10), (2,3,9,9.8)]:
            for direction, ox, oy in itertools.product(['left','right'], [0,17], [0,23]):
                with self.subTest(h=h,w=w,u=u,g=g,direction=direction,ox=ox,oy=oy):
                    sign = 1 if direction == 'right' else -1
                    scene = self.make(dict(kind='staircase',id='stairs',origin=dict(x=ox,y=oy),rise=h,run=w,count=40,direction=direction),
                        dict(x=ox,y=oy),u,0 if sign == 1 else 180,g,measurements=False)
                    n = math.ceil(2*h*u*u/(g*w*w)-1e-10)
                    t = math.sqrt(2*n*h/g)
                    result = self.check('stairs',scene,t,dict(x=ox+sign*u*t,y=oy-n*h),
                        f'stairs-{direction}-{g}' if (h,w,u,ox,oy) == (1,1,10,0,0) else None)
                    self.assertEqual(result['contact']['face'],f'tread:{n}')
                    if g == 10 and h == w == 1 and u == 10:
                        self.assertEqual(result['contact']['touching_faces'],[
                            dict(surface_id='stairs',face='tread:20'),dict(surface_id='stairs',face='riser:21')])

    def test_short_horizon_and_finite_ground_do_not_invent_contact(self):
        scene = self.make(dict(kind='ground',id='ground',x_min=-10,x_max=100),dict(x=0,y=45),10,0,10)
        for horizon, xmax in [(1,100),(10,5)]:
            scene['surfaces'][0]['x_max'] = xmax
            result = self.post('simulations',dict(scene=scene,particle_id='P',max_time=horizon))
            self.assertEqual(result['status'],'time_limit')
            self.assertIsNone(result['contact'])
            self.assertTrue(all(m['status']=='unavailable' and m['value'] is None for m in result['measurements']))

    def test_shared_contact_not_surface_order_dependent(self):
        scene = self.make(dict(kind='ground',id='B',x_min=-100,x_max=100),dict(x=0,y=45),10,0,10)
        scene['surfaces'].append(dict(kind='ground',id='A',x_min=-100,x_max=100,y=0))
        first = self.post('simulations',dict(scene=scene,particle_id='P'))['contact']
        scene['surfaces'].reverse()
        second = self.post('simulations',dict(scene=scene,particle_id='P'))['contact']
        self.assertEqual(first,second)
        self.assertEqual(first['surface_id'],'A')

    def test_live_checker_accepts_equivalent_range_but_not_invented_measurement(self):
        scene=self.make(dict(kind='ground',id='G',x_min=-100,x_max=100),dict(x=0,y=0),16,30,10)
        scene['measurements']=[scene['measurements'][1]]
        scene['measurements'][0]['axis']='direct'
        simulation=self.post('simulations',dict(scene=scene,particle_id='P'))
        response=dict(status='review',scene=scene,simulation=simulation)
        check_live(dict(id='ground'),response)
        simulation['measurements'][0]['value']=123
        with self.assertRaises(AssertionError):
            check_live(dict(id='ground'),response)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Reliability))
    print('Analytic scenario counts:', json.dumps(COUNTS,sort_keys=True))
    if result.wasSuccessful() and os.getenv('PHYSICA_RELIABILITY_REPORT'):
        path = Path(os.environ['PHYSICA_RELIABILITY_REPORT'])
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(counts=COUNTS,examples=list(EXAMPLES.values())),indent=2)+'\n')
        print('Browser fixtures:',path)
    sys.exit(not result.wasSuccessful())
