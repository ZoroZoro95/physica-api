"""Absolute-clock scheduling with launch-relative analytical motion."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app
from regress_playground_ensemble import scene


class LaunchTimeTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def simulate(self, value, particle='P', horizon=5):
        response = self.api.post('/v1/simulations', json={
            'scene': value, 'particle_id': particle, 'max_time': horizon, 'samples': 101})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_schedule_is_immutable_and_survives_launch_edits(self):
        value = scene()
        response = self.api.post('/v1/scenes/schedule', json={
            'scene': value, 'particle_id': 'Q', 'launch_time': 1.25})
        self.assertEqual(response.status_code, 200, response.text)
        scheduled = response.json()
        self.assertEqual(scheduled['revision'], value['revision']+1)
        self.assertNotIn('launch_time', value['particles'][1])
        self.assertEqual(scheduled['particles'][1]['launch_time'], 1.25)
        updated = self.api.post('/v1/scenes/apply', json={'scene': scheduled, 'commands': [
            {'op': 'set_launch', 'particle_id': 'Q', 'speed': 7, 'direction': 'angle', 'angle_deg': 30}]}).json()
        self.assertEqual(updated['particles'][1]['launch_time'], 1.25)
        imported = self.api.post('/v1/scenes/validate', json=updated)
        self.assertEqual(imported.json()['particles'][1]['launch_time'], 1.25)

    def test_delayed_motion_is_time_translation_not_extra_gravity(self):
        for delay in [.25, 1.25, 50]:
            value = scene()
            original = self.simulate(value)
            value['particles'][0]['launch_time'] = delay
            delayed = self.simulate(value, horizon=delay+3)
            self.assertEqual(delayed['launch_time'], delay)
            self.assertAlmostEqual(delayed['contact']['time'], delay+1)
            self.assertEqual(delayed['contact']['position'], original['contact']['position'])
            for a, b in zip(original['samples'], delayed['samples']):
                self.assertAlmostEqual(b['t'], a['t']+delay)
                self.assertEqual(a['position'], b['position'])
                self.assertEqual(a['velocity'], b['velocity'])

    def test_waiting_particle_is_stationary_until_release(self):
        value = scene()
        value['particles'][0]['launch_time'] = 8
        track = self.simulate(value, horizon=3)
        self.assertEqual(track['status'], 'waiting')
        self.assertIsNone(track['contact'])
        self.assertEqual(track['samples'][-1]['t'], 3)
        for sample in track['samples']:
            self.assertEqual(sample['position'], {'x': 0, 'y': 5})
            self.assertEqual(sample['velocity'], {'x': 0, 'y': 0})

    def test_launch_exactly_at_horizon_has_initial_velocity_not_gravity(self):
        value = scene()
        value['particles'][0]['launch_time'] = 2
        track = self.simulate(value, horizon=2)
        self.assertEqual(track['status'], 'time_limit')
        self.assertEqual(len(track['samples']), 1)
        self.assertEqual(track['samples'][0], {
            't': 2, 'position': {'x': 0, 'y': 5}, 'velocity': {'x': 2, 'y': 0}})
        value['particles'][0]['position']['y'] = 0
        contact = self.simulate(value, horizon=2)
        self.assertEqual(contact['status'], 'contact')
        self.assertEqual(contact['contact']['time'], 2)

    def test_delayed_exact_contact_and_strictly_earlier_horizon(self):
        value = scene()
        value['particles'][0]['launch_time'] = 1.25
        self.assertEqual(self.simulate(value, horizon=2.25)['status'], 'contact')
        self.assertEqual(self.simulate(value, horizon=2.25-1e-7)['status'], 'time_limit')

    def test_ensemble_uses_absolute_time_and_pending_launch_extends_to_horizon(self):
        value = scene()
        value['particles'][1]['launch_time'] = 1
        result = self.api.post('/v1/simulations/scene', json={'scene': value, 'max_time': 5}).json()
        self.assertAlmostEqual(result['duration'], 3)
        self.assertAlmostEqual(result['tracks'][0]['contact']['time'], 1)
        self.assertAlmostEqual(result['tracks'][1]['contact']['time'], 3)
        self.assertEqual(result['tracks'][1]['samples'][0]['t'], 1)
        value['particles'][1]['launch_time'] = 9
        result = self.api.post('/v1/simulations/scene', json={'scene': value, 'max_time': 5}).json()
        self.assertEqual(result['duration'], 5)
        self.assertEqual(result['tracks'][1]['status'], 'waiting')

    def test_invalid_schedule_and_pending_invalid_scene_are_rejected(self):
        for delay in [-1, 301, 'NaN', 'Infinity']:
            self.assertEqual(self.api.post('/v1/scenes/schedule', json={
                'scene': scene(), 'particle_id': 'P', 'launch_time': delay}).status_code, 422)
        self.assertEqual(self.api.post('/v1/scenes/schedule', json={
            'scene': scene(), 'particle_id': 'missing', 'launch_time': 1}).status_code, 422)
        for mutation in ['inside', 'unset']:
            value = scene()
            value['particles'][0]['launch_time'] = 10
            if mutation == 'inside': value['particles'][0]['position']['y'] = -1
            else: value['particles'][0]['launch_set'] = False
            self.assertEqual(self.api.post('/v1/simulations', json={
                'scene': value, 'particle_id': 'P', 'max_time': 1}).status_code, 422)

    def test_continuing_stairs_expand_only_for_actual_flight_time(self):
        value = scene()
        value['surfaces'] = [{'kind': 'staircase', 'id': 'stairs', 'rise': 1, 'run': 1, 'count': 5}]
        value['particles'] = [{'id': 'P', 'position': {'x': 0, 'y': 0},
            'velocity': {'x': 10, 'y': 0}, 'launch_set': True, 'launch_time': 299}]
        response = self.api.post('/v1/simulations/planned', json={
            'scene': value, 'particle_id': 'P', 'max_time': 300, 'continuing_staircases': ['stairs']})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['scene']['surfaces'][0]['count'], 11)
        self.assertEqual(result['simulation']['samples'][0]['t'], 299)
        self.assertEqual(result['simulation']['samples'][-1]['t'], 300)


if __name__ == '__main__':
    unittest.main(verbosity=2)
