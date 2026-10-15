"""Independent stair examples through real request validation; no answer keys."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app

client = TestClient(app)
checks = 0


def post(path, body, status=200):
    global checks
    response = client.post('/v1/'+path, json=body)
    assert response.status_code == status, response.text
    checks += 1
    return response.json()


def scene(rise=1, run=1, speed=10, gravity=9.8, direction='right', origin=None, count=40, position=None, angle=None):
    origin = origin or {'x': 0, 'y': 0}
    return post('scenes/apply', {'scene': {'gravity': gravity}, 'commands': [
        {'op': 'add_surface', 'surface': {'kind': 'staircase', 'id': 'steps',
            'origin': origin, 'rise': rise, 'run': run, 'count': count, 'direction': direction}},
        {'op': 'add_particle', 'id': 'marble', 'position': position or origin},
        {'op': 'set_launch', 'particle_id': 'marble', 'direction': 'angle',
            'speed': speed, 'angle_deg': angle if angle is not None else (0 if direction == 'right' else 180)},
    ]})


def simulate(s, **kwargs):
    return post('simulations', {'scene': s, 'particle_id': 'marble', **kwargs})


for rise, run, speed, gravity in [(1, 1, 10, 9.8), (0.4, 1.2, 7, 10), (2, 3, 9, 9.8), (1, 1, 1, 10), (1, 1, 10, 10)]:
    for direction in ['right', 'left']:
        for origin in [{'x': 0, 'y': 0}, {'x': 17, 'y': 23}]:
            s = scene(rise, run, speed, gravity, direction, origin)
            hit = simulate(s)['contact']
            # For horizontal launch, first n with sqrt(2*n*h/g)*u <= n*w.
            n = math.ceil(2*rise*speed**2/(gravity*run**2)-1e-10)
            t = math.sqrt(2*n*rise/gravity)
            sign = 1 if direction == 'right' else -1
            assert math.isclose(hit['time'], t, abs_tol=1e-8), hit
            assert math.isclose(hit['position']['x'], origin['x']+sign*speed*t, abs_tol=1e-8)
            assert math.isclose(hit['position']['y'], origin['y']-n*rise, abs_tol=1e-8)
            # At an exact corner either adjoining face is geometrically valid.
            assert hit['face'] in (f'tread:{n}', f'riser:{n+1}'), hit
            assert simulate(s, samples=2)['contact'] == simulate(s, samples=1001)['contact']
            mesh = post('geometry', s)['meshes'][0]
            assert mesh['kind'] == 'staircase'
            xy = {(v[0], v[1]) for v in mesh['vertices']}
            for f in mesh['collision_faces']:
                assert (f['from']['x'], f['from']['y']) in xy
                assert (f['to']['x'], f['to']['y']) in xy
            assert all(0 <= v < len(mesh['vertices']) for face in mesh['triangles'] for v in face)

hit = simulate(scene(position={'x': .5, 'y': -.5}, speed=5, angle=180))['contact']
assert hit['face'] == 'riser:1' and math.isclose(hit['time'], .1)
assert simulate(scene(count=3))['status'] == 'time_limit'
assert simulate(scene(position={'x': .5, 'y': -1}, speed=0))['contact']['time'] == 0
assert simulate(scene(position={'x': .5, 'y': -1}, speed=5, angle=90))['contact']['time'] > 0
for position in [{'x': .5, 'y': -2}, {'x': 1, 'y': -4}]:
    post('simulations', {'scene': scene(position=position), 'particle_id': 'marble'}, 422)
for count in [0, 129, 1.5]:
    post('scenes/validate', {'surfaces': [{'kind': 'staircase', 'id': 's', 'rise': 1, 'run': 1, 'count': count}]}, 422)
post('scenes/validate', {'surfaces': [{'kind': 'staircase', 'id': 's', 'rise': 1000, 'run': 1, 'count': 128}]}, 422)
post('scenes/apply', {'scene': scene(), 'commands': [{'op': 'add_particle', 'id': 'other',
    'on_surface': {'surface_id': 'steps', 'fraction': .5}}]}, 422)
print(f'PASS staircase API: {checks} requests; varied dimensions, origins, mirrored stairs, corners and geometry')
