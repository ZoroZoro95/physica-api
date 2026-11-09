"""Analytical meeting checks, independent of animation sample density."""
from pathlib import Path
import copy
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app


def particle(id, x, y, vx, vy, launch=0):
    return dict(id=id, position=dict(x=x, y=y), velocity=dict(x=vx, y=vy),
                launch_set=True, launch_time=launch)


class EncounterTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)
        self.scene = dict(schema_version='1', id='encounters', revision=0,
            gravity=10, surfaces=[], annotations=[], particles=[
                particle('P', 0, 20, 2, 0), particle('Q', 4, 20, -2, 0)])

    def run_scene(self, horizon=2, samples=2):
        response = self.api.post('/v1/simulations/scene', json=dict(
            scene=self.scene, max_time=horizon, samples=samples))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_meeting_without_sample_at_event_and_no_response(self):
        original = copy.deepcopy(self.scene)
        for samples in [2, 11, 121, 1001]:
            result = self.run_scene(samples=samples)
            self.assertEqual(result['encounters'], [dict(particle_ids=['P', 'Q'],
                kind='meeting', time=1, end_time=1, position=dict(x=2, y=15))])
            self.assertEqual(result['interaction'], 'independent')
            self.assertEqual(result['tracks'][0]['samples'][-1]['velocity']['x'], 2)
        self.assertEqual(self.scene, original)

    def test_delayed_launch_uses_flight_age(self):
        self.scene['particles'] = [particle('P', 0, 50, 2, 0),
            particle('Q', 6, 45, -2, -10, 1)]
        event = self.run_scene(3)['encounters'][0]
        self.assertEqual(event['time'], 2)
        self.assertEqual(event['position'], dict(x=4, y=30))
        for track in self.run_scene(3)['tracks']:
            exact = next(s for s in track['samples'] if s['t'] == event['time'])
            self.assertEqual(exact['position'], event['position'])

    def test_path_crossing_at_different_times_is_not_meeting(self):
        self.scene['particles'][1]['position']['y'] += 1
        self.assertEqual(self.run_scene()['encounters'], [])

    def test_parallel_separated_and_coincident(self):
        self.scene['particles'][1]['velocity']['x'] = 2
        self.assertEqual(self.run_scene()['encounters'], [])
        self.scene['particles'][1]['position']['x'] = 0
        event = self.run_scene()['encounters'][0]
        self.assertEqual((event['kind'], event['time'], event['end_time']), ('coincident', 0, 2))

    def test_initial_meeting_then_separation(self):
        self.scene['particles'][1]['position']['x'] = 0
        event = self.run_scene()['encounters'][0]
        self.assertEqual((event['kind'], event['time'], event['end_time']), ('meeting', 0, 0))

    def test_horizon_and_first_contact_boundaries(self):
        self.assertEqual(self.run_scene(1-1e-7)['encounters'], [])
        self.assertEqual(self.run_scene(1)['encounters'][0]['time'], 1)
        self.scene['surfaces'] = [dict(kind='ground', id='ground', y=15)]
        self.assertEqual(self.run_scene()['encounters'][0]['time'], 1)
        self.scene['surfaces'][0]['y'] = 16
        self.assertEqual(self.run_scene()['encounters'], [])

    def test_waiting_body_is_not_a_free_flight_encounter(self):
        self.scene['particles'][1] = particle('Q', 2, 15, 0, 0, 3)
        self.assertEqual(self.run_scene()['encounters'], [])

    def test_no_overlap_in_flight_intervals(self):
        self.scene['surfaces'] = [dict(kind='ground', id='ground', y=0)]
        self.scene['particles'][1]['launch_time'] = 3
        self.assertEqual(self.run_scene(5)['encounters'], [])

    def test_translation_mirror_order_and_vertical_meeting(self):
        self.scene['particles'] = [particle('Z', 9, 50, 0, 3), particle('A', 9, 54, 0, -1)]
        for offset in [0, 10000, -10000]:
            for p in self.scene['particles']:
                p['position']['x'] = offset-9
            event = self.run_scene()['encounters'][0]
            self.assertEqual(event['particle_ids'], ['A', 'Z'])
            self.assertEqual(event['time'], 1)
            self.assertEqual(event['position'], dict(x=offset-9, y=48))

    def test_small_relative_speed_not_treated_as_zero(self):
        self.scene['particles'] = [particle('P', 0, 20, 1e-8, 0),
            particle('Q', 1e-6, 20, 0, 0)]
        event = self.run_scene(101)['encounters'][0]
        self.assertAlmostEqual(event['time'], 100)
        self.assertEqual(event['kind'], 'meeting')

    def test_three_particles_pair_events_stable_order(self):
        self.scene['particles'].append(particle('R', 2, 20, 0, 0))
        events = self.run_scene()['encounters']
        self.assertEqual([e['particle_ids'] for e in events], [['P', 'Q'], ['P', 'R'], ['Q', 'R']])
        self.assertTrue(all(e['time'] == 1 for e in events))

    def test_constructed_meetings_across_varied_launches(self):
        rng = random.Random(718)
        for _ in range(100):
            gravity = rng.uniform(0.1, 30)
            target_time = rng.uniform(3, 20)
            target = (rng.uniform(-100, 100), rng.uniform(-100, 100))
            particles = []
            for id in ['P', 'Q']:
                launch = rng.uniform(0, target_time-0.1)
                age = target_time-launch
                vx, vy = rng.uniform(-30, 30), rng.uniform(-30, 30)
                particles.append(particle(id, target[0]-vx*age,
                    target[1]-vy*age+gravity*age*age/2, vx, vy, launch))
            self.scene.update(gravity=gravity, particles=particles)
            event = self.run_scene(target_time+1)['encounters'][0]
            self.assertAlmostEqual(event['time'], target_time, places=8)
            self.assertAlmostEqual(event['position']['x'], target[0], places=7)
            self.assertAlmostEqual(event['position']['y'], target[1], places=7)


if __name__ == '__main__':
    unittest.main(verbosity=2)
