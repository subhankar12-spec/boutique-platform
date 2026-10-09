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
