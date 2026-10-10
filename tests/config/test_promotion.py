"""Exercise immutable promotion and Git-history rollback without signing infrastructure."""
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import yaml

GITOPS = Path(__file__).resolve().parents[3] / 'boutique-gitops'
sys.path.insert(0, str(GITOPS / 'scripts'))
from promote import promote
from rollback import rollback
from release_config import ReleaseError, selected_image
from helm_release import selected_chart

SERVICE = 'cart'
COMMIT = 'a' * 40
IMAGE = 'ghcr.io/subhankar12-spec/boutique-cart@sha256:' + 'b' * 64
NEXT_IMAGE = 'ghcr.io/subhankar12-spec/boutique-cart@sha256:' + 'c' * 64

class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(GITOPS / 'environments', self.root / 'environments')
        self.package = self.root / 'published-chart.tgz'
        self.package.write_bytes(self.chart())

    def chart(self, version='0.1.0-' + COMMIT, name='boutique-cart', unsafe=False):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            content = yaml.safe_dump({'apiVersion': 'v2', 'name': name, 'version': version}).encode()
            member = tarfile.TarInfo(name + '/Chart.yaml'); member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
            if unsafe:
                member = tarfile.TarInfo(name + '/../escape'); member.size = 1
                archive.addfile(member, io.BytesIO(b'x'))
        return data.getvalue()

    def dev(self, image=IMAGE):
        return promote(self.root, SERVICE, 'dev', image, self.package, COMMIT)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in (self.root / 'environments').rglob('*') if p.is_file()}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self):
        self.git('add', 'environments'); self.git('commit', '-m', 'Release selection')
        sha = self.git('rev-parse', 'HEAD'); self.git('update-ref', 'refs/remotes/origin/main', sha)
        return sha

    def test_dev_selects_published_digest_and_source_version(self):
        self.dev()
        self.assertEqual(selected_image(self.root, SERVICE, 'dev'), IMAGE)
        self.assertEqual(selected_chart(self.root, SERVICE, 'dev')['version'], '0.1.0-' + COMMIT)

    def test_promotion_preserves_exact_image_and_chart_bytes_across_environments(self):
        self.dev()
        dev_chart = selected_chart(self.root, SERVICE, 'dev')
        promote(self.root, SERVICE, 'staging')
        promote(self.root, SERVICE, 'production')
        for target in ('staging', 'production'):
            self.assertEqual(selected_image(self.root, SERVICE, target), IMAGE)
            self.assertEqual(selected_chart(self.root, SERVICE, target), dev_chart)
            package = self.root / f'environments/{target}/charts/boutique-cart-0.1.0-{COMMIT}.tgz'
            self.assertEqual(package.read_bytes(), self.package.read_bytes())

    def test_promotion_cannot_skip_preceding_environment(self):
        self.dev(); before = self.snapshot()
        with self.assertRaises(ReleaseError): promote(self.root, SERVICE, 'production', IMAGE)
        self.assertEqual(self.snapshot(), before)

    def test_requested_digest_must_match_preceding_environment(self):
        self.dev(); before = self.snapshot()
        with self.assertRaises(ReleaseError): promote(self.root, SERVICE, 'staging', NEXT_IMAGE)
        self.assertEqual(self.snapshot(), before)

    def test_promotion_cannot_replace_the_chart(self):
        self.dev()
        with self.assertRaises(ReleaseError): promote(self.root, SERVICE, 'staging', IMAGE, self.package, COMMIT)

    def test_dev_rejects_mutable_and_wrong_service_images(self):
        for image in ('ghcr.io/subhankar12-spec/boutique-cart:latest', IMAGE.replace('boutique-cart', 'boutique-orders')):
            with self.subTest(image=image), self.assertRaises(ReleaseError): self.dev(image)

    def test_dev_requires_complete_publication_inputs(self):
        with self.assertRaises(ReleaseError): promote(self.root, SERVICE, 'dev', IMAGE)

    def test_bad_chart_does_not_mutate_environment(self):
        for data in (b'not a chart', self.chart(name='boutique-orders'), self.chart(unsafe=True), self.chart(version='0.1.0-' + 'd' * 40)):
            self.package.write_bytes(data); before = self.snapshot()
            with self.assertRaises(ReleaseError): self.dev()
            self.assertEqual(self.snapshot(), before)

    def test_unknown_target_is_rejected(self):
        with self.assertRaises(ReleaseError): promote(self.root, SERVICE, 'other', IMAGE, self.package, COMMIT)

    def test_rollback_restores_previous_image_and_exact_chart_from_main_history(self):
        self.git('init', '-b', 'main'); self.git('config', 'user.name', 'Test'); self.git('config', 'user.email', 'test@example.invalid')
        self.dev(); original = self.commit(); original_chart = selected_chart(self.root, SERVICE, 'dev')
        self.dev(NEXT_IMAGE); self.commit()
        rollback(self.root, SERVICE, 'dev', original)
        self.assertEqual(selected_image(self.root, SERVICE, 'dev'), IMAGE)
        self.assertEqual(selected_chart(self.root, SERVICE, 'dev'), original_chart)

    def test_rollback_rejects_unmerged_commit(self):
        self.git('init', '-b', 'main'); self.git('config', 'user.name', 'Test'); self.git('config', 'user.email', 'test@example.invalid')
        self.dev(); original = self.commit()
        self.git('checkout', '-b', 'unreviewed'); self.dev(NEXT_IMAGE)
        self.git('add', 'environments'); self.git('commit', '-m', 'Unmerged selection'); unmerged = self.git('rev-parse', 'HEAD')
        self.git('checkout', 'main'); before = self.snapshot()
        with self.assertRaises(ReleaseError): rollback(self.root, SERVICE, 'dev', unmerged)
        self.assertEqual(self.snapshot(), before)

    def test_rollback_requires_full_commit(self):
        with self.assertRaises(ReleaseError): rollback(self.root, SERVICE, 'dev', 'main')

if __name__ == '__main__': unittest.main()
