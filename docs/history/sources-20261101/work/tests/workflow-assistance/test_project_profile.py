from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'packages/client-neutral-core/scripts'))
from project_profile import load_registry, resolve_profile
class ProjectProfileTests(unittest.TestCase):
 def test_work_lab_and_fixture_are_isolated_profiles(self):
  registry=load_registry(ROOT/'config/project-profiles.json')
  work=resolve_profile(registry,'work-lab'); fixture=resolve_profile(registry,'fixture-external')
  self.assertTrue(work['modules']['work-lab-observer']['observation_only'])
  self.assertNotEqual(work['project']['id'],fixture['project']['id'])
 def test_duplicate_profile_ids_fail_closed(self):
  registry=json.loads((ROOT/'config/project-profiles.json').read_text(encoding='utf-8'))
  registry['profiles'].append(registry['profiles'][0])
  with self.assertRaises(ValueError): load_registry_from_obj(registry)
 def test_archeaxis_is_independent_external_endpoint(self):
  registry=load_registry(ROOT/'config/project-profiles.json')
  arch=resolve_profile(registry,'archeaxis-knowledge-os')
  self.assertEqual(arch['project']['id'],'archeaxis-knowledge-os')
  self.assertEqual(arch['project']['root_policy'],'explicit_git_root')
  self.assertTrue(arch['project']['windows_native_first'])
  self.assertTrue(arch['modules']['archeaxis-core']['observation_only'])
  self.assertEqual(arch['ci']['workflow_name'],'CI')
  self.assertEqual(arch['ci']['stable_aggregate_job'],'a0-gates')
  self.assertEqual(arch['ci']['release_workflow'],'Release')
  # endpoint registration carries address + protocol metadata only, never content
  self.assertNotIn('command', json.dumps(arch['gates']))
  self.assertNotIn('risk_paths', arch)
 def test_archeaxis_registration_does_not_create_work_lab_dependency(self):
  registry=load_registry(ROOT/'config/project-profiles.json')
  work=resolve_profile(registry,'work-lab')
  # WORK-LAB has no runtime dependency on the external project
  self.assertNotIn('archeaxis', json.dumps(work.get('modules',{})))

def load_registry_from_obj(data):
 ids=[p.get('project',{}).get('id') for p in data['profiles']]
 if len(ids)!=len(set(ids)): raise ValueError('duplicate')
 return data
if __name__=='__main__': unittest.main()
