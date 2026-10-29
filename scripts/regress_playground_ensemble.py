"""Independent analytical checks for simultaneous, non-interacting flights."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app


def scene():
    return {'schema_version': '1', 'id': 'ensemble-test', 'revision': 3, 'gravity': 10,
        'surfaces': [{'kind': 'ground', 'id': 'ground', 'y': 0}],
        'particles': [
            {'id': 'P', 'position': {'x': 0, 'y': 5}, 'velocity': {'x': 2, 'y': 0}, 'launch_set': True},
            {'id': 'Q', 'position': {'x': 10, 'y': 20}, 'velocity': {'x': -3, 'y': 0}, 'launch_set': True}],
        'annotations': [], 'measurements': []}


class EnsembleTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def run_scene(self, value, **kwargs):
        response = self.api.post('/v1/simulations/scene', json={'scene': value, 'max_time': 4, **kwargs})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_two_independent_contact_times_and_single_particle_parity(self):
        for count in [2, 121, 501]:
            value = scene()
            result = self.run_scene(value, samples=count)
            self.assertEqual(result['interaction'], 'independent')
            self.assertAlmostEqual(result['duration'], 2)
            self.assertEqual(result['revision'], 3)
            for track, expected_time in zip(result['tracks'], [1, 2]):
                self.assertAlmostEqual(track['contact']['time'], expected_time)
                solo = self.api.post('/v1/simulations', json={'scene': value,
                    'particle_id': track['particle_id'], 'max_time': 4, 'samples': count}).json()
                self.assertEqual(track, solo)
                p = next(p for p in value['particles'] if p['id'] == track['particle_id'])
                for sample in track['samples']:
                    t = sample['t']
                    self.assertAlmostEqual(sample['position']['x'], p['position']['x'] + p['velocity']['x']*t)
                    self.assertAlmostEqual(sample['position']['y'], p['position']['y'] - 5*t*t)
                    self.assertAlmostEqual(sample['velocity']['y'], -10*t)

    def test_finite_horizon_keeps_one_contact_and_one_flying(self):
        result = self.run_scene(scene(), max_time=1.5)
        self.assertEqual(result['duration'], 1.5)
        self.assertEqual([t['status'] for t in result['tracks']], ['contact', 'time_limit'])
        self.assertAlmostEqual(result['tracks'][1]['samples'][-1]['position']['y'], 8.75)

    def test_order_and_translation_do_not_change_physics(self):
        value = scene()
        original = self.run_scene(value)
        value['particles'].reverse()
        for p in value['particles']:
            p['position']['x'] = -p['position']['x'] + 13
            p['position']['y'] += 7
            p['velocity']['x'] *= -1
        value['surfaces'][0]['y'] += 7
        reflected = self.run_scene(value)
        for track in reflected['tracks']:
            baseline = next(t for t in original['tracks'] if t['particle_id'] == track['particle_id'])
            self.assertAlmostEqual(track['contact']['time'], baseline['contact']['time'])
            self.assertAlmostEqual(track['contact']['position']['x'], 13-baseline['contact']['position']['x'])
            self.assertAlmostEqual(track['contact']['position']['y'], 7)

    def test_contact_measurement_can_reference_both_particles(self):
        value = scene()
        value['measurements'] = [{'kind': 'distance', 'id': 'separation', 'label': 'Impact separation',
            'start': {'kind': 'object', 'target': 'P', 'feature': 'contact'},
            'end': {'kind': 'object', 'target': 'Q', 'feature': 'contact'}}]
        for track in self.run_scene(value)['tracks']:
            self.assertAlmostEqual(track['measurements'][0]['value'], 2)
        for track in self.run_scene(value, max_time=1.5)['tracks']:
            self.assertEqual(track['measurements'][0]['status'], 'unavailable')

    def test_invalid_particle_rejects_whole_request(self):
        for mutation in ['unset', 'inside', 'empty']:
            value = scene()
            if mutation == 'unset': value['particles'][1]['launch_set'] = False
            if mutation == 'inside': value['particles'][1]['position']['y'] = -1
            if mutation == 'empty': value['particles'] = []
            response = self.api.post('/v1/simulations/scene', json={'scene': value})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn('tracks', response.json())

    def test_crossing_paths_do_not_invent_collision_response(self):
        value = scene()
        value['surfaces'] = []
        for p, x, vx in zip(value['particles'], [0, 4], [2, -2]):
            p['position'] = {'x': x, 'y': 20}
            p['velocity'] = {'x': vx, 'y': 0}
        result = self.run_scene(value, max_time=2, samples=3)
        a, b = result['tracks']
        self.assertEqual(a['samples'][1]['position'], b['samples'][1]['position'])
        self.assertEqual(a['samples'][-1]['velocity']['x'], 2)
        self.assertEqual(b['samples'][-1]['velocity']['x'], -2)
        self.assertIsNone(a['contact'])

    def test_limits_and_immediate_contact(self):
        value = scene()
        for p in value['particles']: p['position']['y'] = 0
        result = self.run_scene(value)
        self.assertEqual(result['duration'], 0)
        self.assertTrue(all(len(t['samples']) == 1 for t in result['tracks']))
        for bad in [{'max_time': 301}, {'samples': 1002}, {'samples': 1}, {'max_time': 0}]:
            self.assertEqual(self.api.post('/v1/simulations/scene', json={'scene': scene(), **bad}).status_code, 422)


if __name__ == '__main__':
    unittest.main(verbosity=2)
