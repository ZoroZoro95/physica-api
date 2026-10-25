"""HTTP generation contract with scripted model calls, not live AI acceptance."""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from core.playground.main import app
from core.playground import generation
from regress_playground_agent import call, scripted
from regress_playground_builder import recipe


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.addCleanup(self.api.close)
        temp = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(generation, 'REPORT_ROOT', Path(temp)))
        self.enterContext(patch.dict(os.environ, {'PLAYGROUND_AI_ENABLED': '1',
            'GROQ_API_KEY': 'private-test-key', 'PLAYGROUND_MODEL': 'test-model'}))
        self.provider = self.enterContext(patch.object(generation, 'Groq'))

    def generate(self, message):
        with patch.object(generation, 'model_completion', return_value=scripted(message)):
            return self.api.post('/v1/generate', json={'question': 'Test question'})

    def test_review_has_matching_geometry_and_original_horizon(self):
        response = self.generate(call('build_and_simulate', recipe()))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'review')
        self.assertEqual(body['simulation']['contact']['face'], 'tread:21')
        self.assertEqual(body['scene']['revision'], body['simulation']['revision'])
        self.assertEqual(body['meshes'][0]['id'], body['scene']['surfaces'][0]['id'])
        self.assertNotIn('operations', body)
        self.assertNotIn('private-test-key', response.text)
        report = json.loads((generation.REPORT_ROOT/body['report_id']/'report.json').read_text())
        self.assertEqual(report['simulation'], body['simulation'])
        self.assertEqual(report['operations'][-1]['request']['max_time'], 5)

    def test_declines_have_no_scene_and_do_not_replace_anything(self):
        for status in ['needs_clarification', 'unsupported']:
            response = self.generate(call('finish_scene', {'status': status,
                'reason': 'Missing speed' if status == 'needs_clarification' else 'Drag not supported', 'assumptions': []}))
            body = response.json()
            self.assertEqual(body['status'], status)
            self.assertIsNone(body['scene'])
            self.assertIsNone(body['simulation'])
            self.assertEqual(body['meshes'], [])

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {'PLAYGROUND_AI_ENABLED': ''}):
            self.assertEqual(self.api.post('/v1/generate', json={'question': 'Test'}).status_code, 503)
        self.provider.assert_not_called()

    def test_missing_credentials_and_busy_are_explicit(self):
        with patch.dict(os.environ, {'GROQ_API_KEY': ''}):
            self.assertEqual(self.api.post('/v1/generate', json={'question': 'Test'}).status_code, 503)
        generation.generation_lock.acquire()
        try:
            self.assertEqual(self.api.post('/v1/generate', json={'question': 'Test'}).status_code, 429)
        finally:
            generation.generation_lock.release()
        self.provider.assert_not_called()

    def test_input_bounds_and_no_client_provider_overrides(self):
        for data in [{'question': '  '}, {'question': 'x'*12001},
                     {'question': 'Test', 'api_url': 'https://other.example'}]:
            self.assertEqual(self.api.post('/v1/generate', json=data).status_code, 422)
        self.provider.assert_not_called()

    def test_provider_error_is_sanitized_and_lock_is_released(self):
        def broken(*args):
            raise RuntimeError('private-test-key')
        with patch.object(generation, 'model_completion', return_value=broken):
            response = self.api.post('/v1/generate', json={'question': 'Test'})
        self.assertEqual(response.json()['status'], 'failed')
        self.assertNotIn('private-test-key', response.text)
        self.assertFalse(generation.generation_lock.locked())


if __name__ == '__main__':
    unittest.main(verbosity=2)
