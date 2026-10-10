import os,shutil,subprocess,unittest
from pathlib import Path
import yaml

@unittest.skipUnless(shutil.which('helm'), 'helm required for rendered manifest checks')
class ManifestTests(unittest.TestCase):
 def test_homelab_environment_overrides_preserve_dependency_endpoints(self):
  root=Path(__file__).resolve().parents[3]/'boutique-gitops'
  for env in ['dev','staging','production']:
   with self.subTest(env=env):
    docs=list(yaml.safe_load_all(subprocess.check_output(['python3',str(root/'scripts/render.py'),env,'--profile','local'],text=True)))
    deployment=next(d for d in docs if d['kind']=='Deployment' and d['metadata']['name']=='frontend')
    values={e['name']:e.get('value') for e in deployment['spec']['template']['spec']['containers'][0]['env']}
    self.assertEqual(values['CATALOGUE_URL'],'http://catalogue:8081')
    self.assertEqual(values['CART_URL'],'http://cart:8082')
    self.assertEqual(values['ORDERS_URL'],'http://orders:8083')
    self.assertEqual(values['PUBLIC_ORIGIN'],'http://localhost:8080')
    self.assertEqual(values['COOKIE_SECURE'],'false')
    self.assertEqual(deployment['metadata']['namespace'],'boutique-'+env)

 def test_laptop_profile_preserves_registry_selection_and_avoids_jenkins_port(self):
  root=Path(__file__).resolve().parents[3]/'boutique-gitops'
  docs=list(yaml.safe_load_all(subprocess.check_output(['python3',str(root/'scripts/render.py'),'dev','--profile','laptop'],text=True)))
  for resource in docs:
   if resource.get('kind')=='Deployment':
    service=resource['metadata']['name']
    container=resource['spec']['template']['spec']['containers'][0]
    self.assertTrue(container['image'].startswith('ghcr.io/subhankar12-spec/boutique-'+service))
    if service=='frontend':
     env={e['name']:e.get('value') for e in container['env']}
     self.assertEqual(env['PUBLIC_ORIGIN'],'http://localhost:8088')
  self.assertEqual({d['metadata']['name'] for d in docs if d.get('kind')=='StatefulSet'},{'postgres','redis'})
  app=next(d for d in yaml.safe_load_all((root/'applications/dev-laptop.yaml').read_text()) if d['kind']=='Application')
  self.assertNotIn('automated',app['spec']['syncPolicy'])
  self.assertEqual(app['spec']['source']['helm']['valueFiles'],['values.yaml','releases.yaml','../../laptop-profiles/dev/values.yaml'])

 def test_laptop_profile_cannot_be_used_for_production(self):
  root=Path(__file__).resolve().parents[3]/'boutique-gitops'
  result=subprocess.run(['python3',str(root/'scripts/render.py'),'production','--profile','laptop'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
