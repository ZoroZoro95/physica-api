"""Extent planning tests against real routes; no LLM or answer keys involved."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def scene(self, speed=10, rise=1, run=1, direction='right', origin=None):
        origin = origin or {'x': 0, 'y': 0}
        created = self.api.post('/v1/scenes', json={'gravity': 9.8}).json()
        response = self.api.post('/v1/scenes/apply', json={'scene': created, 'commands': [
            {'op': 'add_surface', 'surface': {'id': 'stairs', 'kind': 'staircase',
                'origin': origin, 'rise': rise, 'run': run, 'count': 5, 'direction': direction}},
            {'op': 'add_particle', 'id': 'marble', 'position': origin},
            {'op': 'set_launch', 'particle_id': 'marble', 'speed': speed,
                'direction': 'angle', 'angle_deg': 0 if direction == 'right' else 180}]})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def plan(self, scene, **kwargs):
        return self.api.post('/v1/simulations/planned', json={'scene': scene,
            'particle_id': 'marble', 'max_time': 5, 'continuing_staircases': ['stairs'], **kwargs})

    def test_expands_only_count_and_revision_with_varied_inputs(self):
        for speed, rise, run, direction in [(10, 1, 1, 'right'), (7, 1, 1, 'left'),
                (11, 0.8, 1.3, 'right'), (6, 1.2, 0.9, 'left')]:
            with self.subTest(speed=speed, direction=direction):
                scene = self.scene(speed, rise, run, direction, {'x': 13, 'y': 27})
                response = self.plan(scene)
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                planned = result['scene']
                self.assertGreater(planned['surfaces'][0]['count'], 5)
                self.assertEqual(planned['revision'], scene['revision'] + 1)
                normalized = {**planned, 'revision': scene['revision'],
                    'surfaces': [{**planned['surfaces'][0], 'count': 5}]}
                self.assertEqual(normalized, scene)
                # A horizontal tread is reached when x(t) lies on that tread.
                n = math.ceil(2 * speed**2 * rise / (9.8 * run**2) - 1e-10)
                contact = result['simulation']['contact']
                self.assertIn(contact['face'], [f'tread:{n}', f'riser:{n+1}'])
                self.assertAlmostEqual(contact['time'], math.sqrt(2 * n * rise / 9.8))

    def test_finite_stairs_not_changed_without_permission(self):
        scene = self.scene()
        result = self.plan(scene, continuing_staircases=[]).json()
        self.assertEqual(result['scene'], scene)
        self.assertEqual(result['extent_changes'], [])
        self.assertEqual(result['simulation']['status'], 'time_limit')

    def test_short_horizon_does_not_invent_contact(self):
        scene = self.scene()
        result = self.plan(scene, max_time=0.1).json()
        self.assertEqual(result['scene'], scene)
        self.assertIsNone(result['simulation']['contact'])

    def test_invalid_ids_and_limits_fail_without_truncation(self):
        scene = self.scene()
        for kwargs in [{'continuing_staircases': ['missing']},
                       {'continuing_staircases': ['marble']},
                       {'continuing_staircases': ['stairs', 'stairs']}, {'max_time': 300}]:
            response = self.plan(scene, **kwargs)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(scene['surfaces'][0]['count'], 5)

    def test_replanning_same_horizon_is_idempotent(self):
        first = self.plan(self.scene()).json()
        second = self.plan(first['scene']).json()
        self.assertEqual(first['scene'], second['scene'])
        self.assertEqual(second['extent_changes'], [])
        self.assertEqual(first['simulation'], second['simulation'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
