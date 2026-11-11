"""Mutation tests for audit verdicts; no provider calls or saved answers."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.playground.models import Scene, SimulateRequest, SceneSimulateRequest
from core.playground.engine import simulate
from core.playground.ensemble import simulate_scene
from audit_playground_live import CASES, check, provider_blocked, main


class LiveCheckTests(unittest.TestCase):
    def test_live_audit_stops_calls_and_marks_remaining_cases_not_run(self):
        with TemporaryDirectory() as tmp, patch('audit_playground_live.httpx.Client') as client:
            response = client.return_value.__enter__.return_value.post.return_value
            response.status_code = 200
            response.json.return_value = dict(status='failed',reason='Model rate limit reached; wait.',report_id='test')
            output = Path(tmp)/'report.json'
            with patch.object(sys,'argv',['audit','--live','--output',str(output)]), redirect_stdout(io.StringIO()):
                self.assertEqual(main(),1)
            client.return_value.__enter__.return_value.post.assert_called_once()
            rows = json.loads(output.read_text())
            self.assertEqual(len(rows),len(CASES))
            self.assertEqual(rows[0]['failure_kind'],'provider_blocked')
            self.assertTrue(all(row['status']=='not_run' for row in rows[1:]))

    def test_provider_failures_are_not_interpretation_failures(self):
        for status in [429,502,503,504]:
            self.assertTrue(provider_blocked(None,status))
        self.assertTrue(provider_blocked(dict(status='failed',reason='Model rate limit reached; wait.'),200))
        self.assertTrue(provider_blocked(dict(status='failed',reason='Model provider rejected the request (HTTP 413)'),200))
        self.assertFalse(provider_blocked(dict(status='review',reason='Model provider'),200))
        self.assertFalse(provider_blocked(dict(status='unsupported',reason='Drag'),200))
        self.assertFalse(provider_blocked(dict(status='failed',reason='Tool-call budget exhausted.'),200))

    def fixture(self, multi=False):
        scene = Scene.model_validate(dict(schema_version='1', id='check', revision=3,
            gravity=10, surfaces=[dict(kind='ground', id='ground', y=0)],
            particles=([
                dict(id='P', position=dict(x=0,y=50), velocity=dict(x=2,y=0), launch_set=True),
                dict(id='Q', position=dict(x=8,y=50), velocity=dict(x=-2,y=0), launch_set=True, launch_time=1),
            ] if multi else [dict(id='P', position=dict(x=0,y=20), velocity=dict(x=5,y=0), launch_set=True, launch_time=2)])))
        ensemble = simulate_scene(SceneSimulateRequest(scene=scene,max_time=4)) if multi else None
        track = ensemble.tracks[0] if multi else simulate(SimulateRequest(scene=scene,particle_id='P',max_time=5))
        return dict(status='review',scene=scene.model_dump(mode='json'),simulation=track.model_dump(mode='json'),
            ensemble=ensemble.model_dump(mode='json') if multi else None,max_time=4 if multi else 5)

    def case(self, multi=False):
        return next(c for c in CASES if c['id']==('two_particles' if multi else 'delayed_launch'))

    def test_real_engine_fixtures_pass_including_later_particle_still_airborne(self):
        for multi in [False,True]:
            check(self.case(multi),self.fixture(multi))

    def test_wrong_source_values_cannot_pass_with_right_answer(self):
        baseline=self.fixture()
        for field,value in [('launch_time',0),('position',dict(x=1,y=20)),('velocity',dict(x=6,y=0))]:
            response=deepcopy(baseline)
            response['scene']['particles'][0][field]=value
            with self.assertRaises(AssertionError): check(self.case(),response)

    def test_incomplete_stale_or_mismatched_tracks_fail(self):
        for mutation in ['missing','duplicate','stale','empty','selected','schedule','different']:
            response=self.fixture(True)
            if mutation=='missing': response['ensemble']=None
            if mutation=='duplicate': response['ensemble']['tracks'][1]=deepcopy(response['ensemble']['tracks'][0])
            if mutation=='stale': response['ensemble']['tracks'][1]['revision']+=1
            if mutation=='empty': response['ensemble']['tracks'][1]['samples']=[]
            if mutation=='selected': response['simulation']['particle_id']='R'
            if mutation=='schedule': response['ensemble']['tracks'][1]['launch_time']=0
            if mutation=='different': response['simulation']['samples'][-1]['position']['y']=9
            with self.assertRaises(AssertionError): check(self.case(True),response)

    def test_declined_request_cannot_leak_an_ensemble(self):
        response=dict(status='unsupported',scene=None,simulation=None,ensemble=self.fixture(True)['ensemble'])
        case=next(c for c in CASES if c['id']=='drag')
        with self.assertRaises(AssertionError): check(case,response)


if __name__=='__main__':
    unittest.main(verbosity=2)
