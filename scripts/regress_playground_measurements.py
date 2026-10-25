"""Measurement contracts use actual geometry and contacts, never model answers."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app
from core.playground.agent import run_agent
from regress_playground_agent import call, scripted


def anchor(target, feature, **kw):
    return dict(kind='object', target=target, feature=feature, **kw)


def distance(id, a, b, axis='direct'):
    return dict(kind='distance', id=id, label=id, start=a, end=b, axis=axis)


class Measurements(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def scene(self, specs=None):
        initial = self.api.post('/v1/scenes', json={'gravity': 10}).json()
        commands = [
            {'op': 'add_surface', 'surface': {'kind': 'ground', 'id': 'G', 'x_min': -100, 'x_max': 100}},
            {'op': 'add_particle', 'id': 'P', 'position': {'x': 0, 'y': 45}},
            {'op': 'set_launch', 'particle_id': 'P', 'speed': 10, 'direction': 'angle', 'angle_deg': 0},
        ]
        commands += [{'op': 'set_measurement', 'measurement': s} for s in specs or []]
        response = self.api.post('/v1/scenes/apply', json={'scene': initial, 'commands': commands})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def simulate(self, scene, max_time=10):
        result = self.api.post('/v1/simulations', json={'scene': scene, 'particle_id': 'P', 'max_time': max_time})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_cliff_distance_and_height(self):
        a, b = anchor('P', 'launch'), anchor('P', 'contact')
        scene = self.scene([distance('height', a, b, 'vertical'), distance('range', a, b, 'horizontal'), distance('chord', a, b)])
        result = self.simulate(scene)
        self.assertEqual([m['value'] for m in result['measurements'][:2]], [45, 30])
        self.assertAlmostEqual(result['measurements'][2]['value'], (45**2+30**2)**0.5)
        self.assertEqual(self.api.post('/v1/scenes/validate', json=scene).json(), scene)

    def test_missing_contact_is_unavailable_not_zero(self):
        scene = self.scene([distance('height', anchor('P', 'launch'), anchor('P', 'contact'), 'vertical')])
        m = self.simulate(scene, .2)['measurements'][0]
        self.assertEqual(m['status'], 'unavailable')
        self.assertIsNone(m['value'])
        self.assertEqual(m['points'], [])

    def test_reference_changes_follow_scene_not_old_values(self):
        scene = self.scene([distance('height', anchor('P', 'launch'), anchor('P', 'contact'), 'vertical')])
        scene['particles'][0]['position']['y'] = 80
        self.assertEqual(self.simulate(scene)['measurements'][0]['value'], 80)

    def test_other_particle_contact_not_substituted(self):
        scene = self.scene()
        scene['particles'].append(dict(id='Q', position={'x': 0, 'y': 1}, velocity={'x': 0, 'y': 0}, launch_set=True))
        scene['measurements'] = [distance('Q_drop', anchor('Q', 'launch'), anchor('Q', 'contact'))]
        self.assertEqual(self.simulate(scene)['measurements'][0]['status'], 'unavailable')

    def test_zero_distance_valid_and_zero_ray_unavailable(self):
        p = dict(kind='point', point={'x': 1, 'y': 2})
        scene = self.scene([distance('zero', p, p), dict(kind='angle', id='bad_angle', label='Angle', start=p, vertex=p, end=p)])
        result = self.simulate(scene)['measurements']
        self.assertEqual(result[0]['value'], 0)
        self.assertEqual(result[1]['status'], 'unavailable')

    def test_wedge_dimensions_and_mirrored_angles(self):
        for rising in [True, False]:
            scene = self.scene()
            scene['surfaces'].append(dict(kind='wedge', id='W', origin={'x': 3, 'y': 2}, width=4, height=3, rising=rising))
            low, high = ('top_start', 'top_end') if rising else ('top_end', 'top_start')
            base = 'base_end' if rising else 'base_start'
            scene['measurements'] = [distance('height', anchor('W', base), anchor('W', high), 'vertical'),
                distance('length', anchor('W', low), anchor('W', high)),
                dict(kind='angle', id='slope', label='Slope', start=anchor('W', base), vertex=anchor('W', low), end=anchor('W', high))]
            values = [m['value'] for m in self.simulate(scene)['measurements']]
            self.assertEqual(values[:2], [3, 5])
            self.assertAlmostEqual(values[2], 36.86989764584402)

    def test_invalid_references_rejected(self):
        scene = self.scene()
        for a in [anchor('missing', 'launch'), anchor('P', 'top_start'), anchor('G', 'contact'), anchor('P', 'launch', step=2)]:
            scene['measurements'] = [distance('x', a, anchor('P', 'launch'))]
            self.assertEqual(self.api.post('/v1/scenes/validate', json=scene).status_code, 422)

    def test_duplicate_and_untrusted_calculated_value_rejected(self):
        scene = self.scene()
        m = distance('x', anchor('P', 'launch'), anchor('P', 'contact'))
        for specs in [[m, m], [{**m, 'value': 123}], [m]*25]:
            scene['measurements'] = specs
            self.assertEqual(self.api.post('/v1/scenes/validate', json=scene).status_code, 422)

    def test_replace_remove_and_empty_disable_defaults(self):
        a, b = anchor('P', 'launch'), anchor('P', 'contact')
        scene = self.scene([distance('x', a, b)])
        for visible in [True, False]:
            scene = self.api.post('/v1/scenes/apply', json={'scene': scene, 'commands': [
                {'op': 'set_measurement', 'measurement': distance('x', a, b, 'vertical'), 'visible': visible}]}).json()
            self.assertEqual(len(scene['measurements']), int(visible))
        self.assertEqual(self.simulate(scene)['measurements'], [])

    def test_defaults_without_contact_and_long_surface_id(self):
        scene = self.scene()
        scene['surfaces'] = [dict(kind='staircase', id='S'*64, rise=2, run=3, count=30)]
        result = self.simulate(scene, .1)['measurements']
        self.assertEqual([m['value'] for m in result[:2]], [2, 3])
        self.assertEqual(result[2]['status'], 'unavailable')
        scene['measurements'] = []
        self.assertEqual(self.simulate(scene)['measurements'], [])

    def test_atomic_ai_recipe_measures_via_engine(self):
        scene = self.scene()
        commands = [
            {'op': 'add_surface', 'surface': scene['surfaces'][0]},
            {'op': 'add_particle', 'id': 'P', 'position': {'x': 0, 'y': 45}},
            {'op': 'set_launch', 'particle_id': 'P', 'speed': 10, 'direction': 'angle', 'angle_deg': 0},
            {'op': 'set_measurement', 'measurement': distance('Height', anchor('P', 'launch'), anchor('P', 'contact'), 'vertical')},
        ]
        recipe = dict(gravity=10, commands=commands, simulation={'particle_id': 'P', 'max_time': 5}, assumptions=[])
        result = run_agent('A horizontal launch from a cliff', scripted(call('build_and_simulate', recipe)), self.api, atomic=True)
        self.assertEqual(result['status'], 'review')
        self.assertEqual(result['simulation']['measurements'][0]['value'], 45)


if __name__ == '__main__':
    unittest.main()
