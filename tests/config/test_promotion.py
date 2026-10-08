import shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
class PromotionTests(unittest.TestCase):
 def test_promotion_requires_preceding_environment(self):
  source=Path(__file__).resolve().parents[3]/'boutique-gitops'
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'gitops';shutil.copytree(source,root)
   image='ghcr.io/subhankar12-spec/boutique-cart@sha256:'+'a'*64
   def promote(env,img=image):return subprocess.run([sys.executable,str(root/'scripts/promote.py'),'cart',env,img],capture_output=True,text=True).returncode
   self.assertNotEqual(promote('production'),0)
   self.assertNotEqual(promote('dev','ghcr.io/subhankar12-spec/boutique-cart:latest'),0)
   self.assertEqual(promote('dev'),0)
   self.assertEqual(promote('staging'),0)
   self.assertEqual(promote('production'),0)
if __name__=='__main__':unittest.main()
