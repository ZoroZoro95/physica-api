"""Scripted model responses against real API routes, NOT a live LLM evaluation."""
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
from core.playground.agent import ToolSession, run_agent, tool_definitions
from core.playground.main import app


def call(name, arguments):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'test-call', 'type': 'function', 'function': {'name': name,
         'arguments': arguments if isinstance(arguments, str) else json.dumps(arguments)}}]}


def scripted(*messages):
    responses = iter(messages)
    return lambda _messages, _tools: next(responses)


def commands(speed=10, direction='right', origin=None, label='P'):
    origin = origin or {'x': 0, 'y': 0}
    return {'commands': [
        {'op': 'add_surface', 'surface': {'kind': 'staircase', 'id': 'steps',
            'origin': origin, 'rise': 1, 'run': 1, 'count': 40, 'direction': direction}},
        {'op': 'add_particle', 'id': label, 'position': origin},
        {'op': 'set_launch', 'particle_id': label, 'speed': speed, 'direction': 'angle',
            'angle_deg': 0 if direction == 'right' else 180},
    ]}


FINISH = {'status': 'review', 'reason': 'Inspect the scene against the question.',
          'assumptions': ['40 steps shown; coordinate origin at departure; no rolling dynamics.']}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)

    def run_steps(self, *steps, **kwargs):
        return run_agent('Test question', scripted(*steps), self.api, **kwargs)

    def test_changed_scene_inputs_drive_engine_output(self):
        for speed, direction, origin, label in [(10, 'right', {'x': 0, 'y': 0}, 'P'),
                (7, 'left', {'x': 13, 'y': 27}, 'marble')]:
            result = self.run_steps(call('create_scene', {'gravity': 9.8}),
                call('apply_commands', commands(speed, direction, origin, label)),
                call('simulate_scene', {'particle_id': label, 'max_time': 10}),
                call('finish_scene', FINISH))
            self.assertEqual(result['status'], 'review')
            self.assertEqual(result['scene']['particles'][0]['id'], label)
            hit = result['simulation']['contact']
            n = math.ceil(2*speed**2/9.8-1e-10)
            self.assertIn(hit['face'], (f'tread:{n}', f'riser:{n+1}'))
            self.assertAlmostEqual(hit['time'], math.sqrt(2*n/9.8))
            self.assertAlmostEqual(hit['position']['y'], origin['y']-n)

    def test_finish_requires_simulation(self):
        result = self.run_steps(call('finish_scene', FINISH), max_rounds=1)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['scene'])
        self.assertIn('Simulate', result['trace'][0]['result']['error'])

    def test_missing_and_unsupported_do_not_export_scene(self):
        for status in ('needs_clarification', 'unsupported'):
            result = self.run_steps(call('finish_scene', {**FINISH, 'status': status}))
            self.assertEqual(result['status'], status)
            self.assertIsNone(result['scene'])

    def test_no_arbitrary_tool_or_code_operation(self):
        result = self.run_steps(call('execute', {'code': 'print(1)'}),
            call('create_scene', {'gravity': 10}),
            call('apply_commands', {'commands': [{'op': 'execute', 'code': 'print(1)'}]}), max_rounds=3)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Unknown tool', result['trace'][0]['result']['error'])
        self.assertIn('error', result['trace'][2]['result'])

    def test_failed_batch_is_atomic_and_requires_resimulation(self):
        session = ToolSession(self.api)
        session.execute('create_scene', '{"gravity":9.8}')
        session.execute('apply_commands', json.dumps(commands()))
        session.execute('simulate_scene', '{"particle_id":"P","max_time":10}')
        before = session.scene.model_dump()
        with self.assertRaises(ValueError):
            session.execute('apply_commands', json.dumps({'commands': [
                {'op': 'set_launch', 'particle_id': 'P', 'speed': 5, 'direction': 'angle', 'angle_deg': 0},
                {'op': 'set_launch', 'particle_id': 'missing', 'speed': 1, 'direction': 'angle', 'angle_deg': 0},
            ]}))
        self.assertEqual(session.scene.model_dump(), before)
        self.assertIsNone(session.simulation)
        with self.assertRaises(ValueError):
            session.execute('finish_scene', json.dumps(FINISH))

    def test_mutation_invalidates_simulation(self):
        result = self.run_steps(call('create_scene', {'gravity': 9.8}),
            call('apply_commands', commands()), call('simulate_scene', {'particle_id': 'P', 'max_time': 10}),
            call('apply_commands', {'commands': [{'op': 'set_launch', 'particle_id': 'P',
                'speed': 3, 'direction': 'angle', 'angle_deg': 0}]}),
            call('finish_scene', FINISH), max_rounds=5)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['simulation'])

    def test_model_cannot_replace_host_scene(self):
        result = self.run_steps(call('create_scene', {'gravity': 10}),
            call('apply_commands', {**commands(), 'scene': {}}), max_rounds=2)
        self.assertIn('error', result['trace'][-1]['result'])
        self.assertIsNone(result['scene'])

    def test_multiple_particles_rejected(self):
        batch = commands()
        batch['commands'].append({'op': 'add_particle', 'id': 'Q', 'position': {'x': 1, 'y': 2}})
        result = self.run_steps(call('create_scene', {'gravity': 10}), call('apply_commands', batch), max_rounds=2)
        self.assertIn('one particle', result['trace'][-1]['result']['error'])

    def test_time_limit_not_relabelled_contact(self):
        result = self.run_steps(call('create_scene', {'gravity': 9.8}),
            call('apply_commands', commands()), call('simulate_scene', {'particle_id': 'P', 'max_time': .1}),
            call('finish_scene', FINISH))
        self.assertEqual(result['simulation']['status'], 'time_limit')
        self.assertIsNone(result['simulation']['contact'])

    def test_malformed_calls_and_plain_text_cannot_pass(self):
        for response in [None, {'content': 'Answer is 21'},
                         {'tool_calls': [{'id': 'x', 'function': {'name': 'x', 'arguments': {}}}]}]:
            result = self.run_steps(response)
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['scene'])

    def test_invalid_json_recovers_without_unbounded_retry(self):
        result = self.run_steps(call('create_scene', 'not json'),
            call('finish_scene', {**FINISH, 'status': 'needs_clarification'}))
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertIn('error', result['trace'][0]['result'])

    def test_tool_budget(self):
        result = self.run_steps(call('create_scene', {'gravity': 10}), call('finish_scene', FINISH), max_calls=1)
        self.assertEqual(result['tool_calls'], 1)
        self.assertEqual(result['status'], 'failed')

    def test_provider_failure_does_not_leak_exception(self):
        def broken(*_):
            raise RuntimeError('secret-value')
        result = run_agent('Question', broken, self.api)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('secret-value', json.dumps(result))

    def test_api_failure_is_separate(self):
        def broken(_request):
            raise httpx.ConnectError('unavailable')
        with httpx.Client(base_url='http://localhost', transport=httpx.MockTransport(broken)) as api:
            result = run_agent('Question', scripted(call('create_scene', {'gravity': 10})), api)
        self.assertIn('Playground API request failed', result['reason'])

    def test_schema_is_serializable_and_uses_api_commands(self):
        tools = tool_definitions()
        raw = json.dumps(tools, allow_nan=False)
        self.assertNotIn('$ref', raw)
        self.assertIn('staircase', raw)
        self.assertIn('set_launch', raw)
        self.assertEqual(len(tools), 4)

    def test_stale_api_revision_cannot_finish(self):
        real = self.api
        class StaleAPI:
            def post(self, path, **kwargs):
                response = real.post(path, **kwargs)
                if path.endswith('/simulations'):
                    data = response.json()
                    data['revision'] += 1
                    return httpx.Response(200, json=data, request=response.request)
                return response
        result = run_agent('Question', scripted(call('create_scene', {'gravity': 9.8}),
            call('apply_commands', commands()), call('simulate_scene', {'particle_id': 'P', 'max_time': 10}),
            call('finish_scene', FINISH)), StaleAPI(), max_rounds=4)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['scene'])
        self.assertIn('stale', result['trace'][2]['result']['error'])

    def test_reset_and_invalid_mutation_discard_prior_result(self):
        for name, raw in [('create_scene', '{"gravity":-1}'), ('apply_commands', 'not-json')]:
            session = ToolSession(self.api)
            session.execute('create_scene', '{"gravity":9.8}')
            session.execute('apply_commands', json.dumps(commands()))
            session.execute('simulate_scene', '{"particle_id":"P","max_time":10}')
            with self.assertRaises(ValueError):
                session.execute(name, raw)
            self.assertIsNone(session.simulation)

    def test_final_decision_is_terminal(self):
        session = ToolSession(self.api)
        session.execute('finish_scene', json.dumps({**FINISH, 'status': 'unsupported'}))
        with self.assertRaises(ValueError):
            session.execute('create_scene', '{"gravity":10}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
