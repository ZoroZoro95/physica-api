"""Scripted interpretation tests; the host always runs real API physics."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app
from core.playground.agent import run_agent
from regress_playground_agent import call, scripted, commands


def recipe(speed=10, direction='right', continuing=True):
    batch = commands(speed, direction)
    batch['commands'][0]['surface']['count'] = 5
    return {**batch, 'gravity': 9.8, 'simulation': {'particle_id': 'P', 'max_time': 5,
        'continuing_staircases': ['steps'] if continuing else []},
        'assumptions': ['Point particle; coordinates measured from departure.']}


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def run_build(self, *calls, **kwargs):
        return run_agent('A physics question', scripted(*calls), self.api, atomic=True,
            max_rounds=3, max_calls=3, **kwargs)

    def test_one_call_executes_ordered_api_operations(self):
        for speed, direction, faces in [(10, 'right', ['tread:21']), (7, 'left', ['tread:10', 'riser:11'])]:
            result = self.run_build(call('build_and_simulate', recipe(speed, direction)))
            self.assertEqual(result['status'], 'review')
            self.assertEqual(result['tool_calls'], 1)
            self.assertIn(result['simulation']['contact']['face'], faces)
            self.assertEqual([o['route'] for o in result['operations']],
                ['/v1/scenes', '/v1/scenes/apply', '/v1/simulations/planned'])
            self.assertEqual(result['simulation']['revision'], result['scene']['revision'])

    def test_finite_scene_stays_finite_and_does_not_claim_contact(self):
        result = self.run_build(call('build_and_simulate', recipe(continuing=False)))
        self.assertEqual(result['scene']['surfaces'][0]['count'], 5)
        self.assertEqual(result['simulation']['status'], 'time_limit')
        self.assertIn('not a solved', result['reason'])

    def test_model_cannot_finish_review_without_engine(self):
        result = self.run_build(call('finish_scene', {'status': 'review',
            'reason': 'Made up answer', 'assumptions': []}),
            call('finish_scene', {'status': 'needs_clarification', 'reason': 'Missing speed', 'assumptions': []}))
        self.assertIn('error', result['trace'][0]['result'])
        self.assertIsNone(result['scene'])
        self.assertEqual(result['operations'], [])

    def test_invalid_recipe_retries_from_fresh_scene(self):
        invalid = recipe()
        invalid['simulation']['particle_id'] = 'missing'
        result = self.run_build(call('build_and_simulate', invalid),
            call('build_and_simulate', recipe(7, 'left')))
        self.assertEqual(result['status'], 'review')
        self.assertEqual(len(result['scene']['particles']), 1)
        self.assertIn(result['simulation']['contact']['face'], ['tread:10', 'riser:11'])

    def test_declines_without_api_access(self):
        for status in ['needs_clarification', 'unsupported']:
            result = self.run_build(call('finish_scene', {'status': status,
                'reason': 'Cannot simulate this input', 'assumptions': []}))
            self.assertEqual(result['operations'], [])
            self.assertIsNone(result['simulation'])

    def test_schema_does_not_offer_premature_review_or_manual_steps(self):
        def complete(messages, tools):
            self.assertEqual({t['function']['name'] for t in tools},
                {'finish_scene', 'build_and_simulate'})
            finish = next(t for t in tools if t['function']['name'] == 'finish_scene')
            self.assertNotIn('review', finish['function']['parameters']['properties']['status']['enum'])
            return call('finish_scene', {'status': 'unsupported', 'reason': 'Drag', 'assumptions': []})
        run_agent('Drag', complete, self.api, atomic=True)

    def test_low_level_tools_cannot_bypass_atomic_boundary(self):
        result = self.run_build(call('create_scene', {'gravity': 10}),
            call('finish_scene', {'status': 'unsupported', 'reason': 'Unsupported', 'assumptions': []}))
        self.assertEqual(result['operations'], [])
        self.assertIn('error', result['trace'][0]['result'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
