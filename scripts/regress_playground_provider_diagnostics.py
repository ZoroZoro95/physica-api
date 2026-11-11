"""Rejected call diagnostics expose schema paths, never raw provider content."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.playground.agent import tool_failure_diagnostic, tool_definitions


class DiagnosticTests(unittest.TestCase):
    def test_tool_schema_preserves_declarative_geometry_guidance(self):
        schema=tool_definitions({'build_and_simulate'})[0]['function']['parameters']
        commands=schema['properties']['commands']['items']['oneOf']
        particle=next(c for c in commands if c['properties']['op'].get('const')=='add_particle')
        launch=next(c for c in commands if c['properties']['op'].get('const')=='set_launch')
        self.assertIn('Do NOT calculate',particle['properties']['position']['description'])
        self.assertIn('Engine computes exact',particle['properties']['on_surface']['description'])
        self.assertIn('surface_normal',launch['properties']['direction']['description'])

    def test_missing_fields_and_sensitive_extra_key_are_sanitized(self):
        raw=json.dumps({'name':'build_and_simulate','arguments':{'secret-token':'private-value'}})
        result=tool_failure_diagnostic({'failed_generation':raw}, {'build_and_simulate'})
        self.assertFalse(result['arguments_valid'])
        self.assertTrue(any(e['path']=='gravity' for e in result['validation']))
        self.assertNotIn('secret-token',json.dumps(result))
        self.assertNotIn('private-value',json.dumps(result))

    def test_known_xml_envelope_validates_without_executing(self):
        args={'status':'unsupported','reason':'private-value','assumptions':[]}
        result=tool_failure_diagnostic({'failed_generation':f'<function=finish_scene>{json.dumps(args)}</function>'}, {'finish_scene'})
        self.assertTrue(result['arguments_valid'])
        self.assertNotIn('private-value',json.dumps(result))

    def test_unknown_tool_and_unrecognized_content_are_not_echoed(self):
        for raw in ['private-value',json.dumps({'name':'private-value','arguments':{}}),'x'*64001]:
            result=tool_failure_diagnostic({'failed_generation':raw}, {'finish_scene'})
            self.assertNotIn('private-value',json.dumps(result))
            self.assertNotIn('arguments_valid',result)


if __name__=='__main__':
    unittest.main(verbosity=2)
