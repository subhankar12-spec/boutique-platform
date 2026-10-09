"""Delivery gates against real Git history and real Ed25519 signatures."""
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SOURCE = Path(__file__).resolve().parents[3] / 'boutique-gitops'
IMAGE = 'ghcr.io/subhankar12-spec/boutique-cart@sha256:' + 'a' * 64
OTHER_IMAGE = 'ghcr.io/subhankar12-spec/boutique-cart@sha256:' + 'b' * 64
CHECKS = ['browse', 'cart', 'validation', 'origin', 'session_isolation', 'server_pricing',
          'checkout', 'repeat_idempotency', 'concurrent_idempotency', 'order_ownership',
          'empty_cart', 'deletion']


class DeliveryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'gitops'
        shutil.copytree(SOURCE, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        self.private = Path(self.temporary.name) / 'verification-private.pem'
        self.public = Path(self.temporary.name) / 'verification-public.pem'
        self.command('openssl', 'genpkey', '-algorithm', 'ED25519', '-out', self.private)
        self.command('openssl', 'pkey', '-in', self.private, '-pubout', '-out', self.public)
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'Delivery gate test')
        self.initial_commit = self.commit()
        self.assert_success(self.promote('dev'))
        self.dev_commit = self.commit()
        self.dev_evidence = self.create('dev')

    def command(self, *args, cwd=None):
        result = subprocess.run([str(arg) for arg in args], cwd=cwd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def git(self, *args):
        return self.command('git', '-C', self.root, *args)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'Test deployment selection')
        return self.git('rev-parse', 'HEAD')

    def script(self, name, *args):
        return subprocess.run([sys.executable, str(self.root / 'scripts' / name), *map(str, args)], capture_output=True, text=True)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assert_rejected(self, result, text=None):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        if text:
            self.assertIn(text, result.stderr)

    def promote(self, environment, image=IMAGE, evidence=None, public=None):
        args = ['cart', environment, image]
        if evidence:
            args += ['--evidence', evidence, '--public-key', public or self.public]
        return self.script('promote.py', *args)

    def reports(self, environment, commit, image=IMAGE):
        now = dt.datetime.now(dt.timezone.utc)
        deployment = {'items': [{
            'metadata': {'name': 'cart', 'namespace': 'boutique-' + environment, 'generation': 3},
            'spec': {'replicas': 1, 'template': {'spec': {'containers': [{'name': 'cart', 'image': image}]}}},
            'status': {'observedGeneration': 3, 'updatedReplicas': 1, 'readyReplicas': 1, 'availableReplicas': 1,
                       'conditions': [{'type': 'Available', 'status': 'True'}, {'type': 'Progressing', 'status': 'True'}]},
        }]}
        deployment['items'].append({'metadata': {'name': 'frontend', 'namespace': 'boutique-' + environment},
            'spec': {'template': {'spec': {'containers': [{'name': 'frontend', 'env': [{'name': 'PUBLIC_ORIGIN', 'value': 'https://' + environment + '.boutique.example.com'}]}]}}}})
        pods = {'items': [{
            'metadata': {'name': 'cart-123-abc', 'namespace': 'boutique-' + environment,
                         'labels': {'app.kubernetes.io/name': 'cart'}},
            'spec': {'containers': [{'name': 'cart', 'image': image}]},
            'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}],
                       'containerStatuses': [{'name': 'cart', 'ready': True, 'imageID': 'containerd://' + image}]},
        }]}
        argo = {'metadata': {'name': 'boutique-' + environment, 'namespace': 'argocd'},
                'spec': {'source': {'path': 'environments/' + environment, 'repoURL': 'https://github.com/subhankar12-spec/boutique-gitops.git'}, 'destination': {'namespace': 'boutique-' + environment}},
                'status': {'sync': {'status': 'Synced', 'revision': commit}, 'health': {'status': 'Healthy'}}}
        smoke = {'schema_version': 1, 'environment': environment, 'origin': 'https://' + environment + '.boutique.example.com',
                 'started_at': (now - dt.timedelta(seconds=10)).isoformat(), 'completed_at': (now - dt.timedelta(seconds=1)).isoformat(),
                 'success': True, 'checks': CHECKS}
        return {'deployment': deployment, 'pods': pods, 'argocd': argo, 'smoke': smoke}

    def create(self, environment, image=IMAGE, mutation=None, expect_failure=False):
        commit = self.git('rev-parse', 'HEAD')
        reports = self.reports(environment, commit, image)
        if mutation:
            mutation(reports)
        output = Path(self.temporary.name) / (environment + '-evidence.json')
        args = ['create', '--environment', environment, '--service', 'cart', '--image', image,
                '--gitops-commit', commit, '--build-url', 'https://jenkins.example.com/job/boutique-verify/42/',
                '--signing-key', self.private, '--output', output]
        for name, report in reports.items():
            path = Path(self.temporary.name) / (environment + '-' + name + '.json')
            path.write_text(json.dumps(report))
            args += ['--' + name + '-json', path]
        result = self.script('release_evidence.py', *args)
        if expect_failure:
            self.assert_rejected(result)
            return result
        self.assert_success(result)
        return output

    def resign(self, evidence, mutation):
        envelope = json.loads(evidence.read_text())
        mutation(envelope['payload'])
        message = Path(self.temporary.name) / 'canonical.json'
        message.write_text(json.dumps(envelope['payload'], sort_keys=True, separators=(',', ':')))
        signature = Path(self.temporary.name) / 'signature.bin'
        self.command('openssl', 'pkeyutl', '-sign', '-rawin', '-inkey', self.private, '-in', message, '-out', signature)
        import base64
        envelope['signature'] = base64.b64encode(signature.read_bytes()).decode()
        evidence.write_text(json.dumps(envelope))

    def select(self, environment, image):
        path = self.root / 'services' / 'cart' / 'overlays' / environment / 'kustomization.yaml'
        data = yaml.safe_load(path.read_text())
        data['images'][0].pop('newTag', None)
        data['images'][0]['digest'] = image.split('@')[1]
        path.write_text(yaml.safe_dump(data, sort_keys=False))


class PromotionTests(DeliveryFixture):
    def test_valid_promotion_chain_requires_measured_evidence(self):
        self.assert_success(self.promote('staging', evidence=self.dev_evidence))
        self.commit()
        staging_evidence = self.create('staging')
        result = self.assert_success(self.promote('production', evidence=staging_evidence))
        self.assertEqual(result['image'], IMAGE)

    def test_missing_evidence_rejected_without_mutation(self):
        path = self.root / 'services/cart/overlays/staging/kustomization.yaml'
        before = path.read_bytes()
        self.assert_rejected(self.promote('staging'), 'Signed successful dev')
        self.assertEqual(path.read_bytes(), before)

    def test_mutable_image_rejected(self):
        self.assert_rejected(self.promote('dev', 'ghcr.io/subhankar12-spec/boutique-cart:latest'))

    def test_unselected_preceding_image_rejected(self):
        self.assert_rejected(self.promote('production', evidence=self.dev_evidence), 'already be selected in staging')

    def test_tampered_evidence_rejected(self):
        envelope = json.loads(self.dev_evidence.read_text())
        envelope['payload']['build_url'] += 'tampered'
        self.dev_evidence.write_text(json.dumps(envelope))
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'signature validation failed')

    def test_untrusted_key_rejected(self):
        other_private, other_public = Path(self.temporary.name) / 'other.pem', Path(self.temporary.name) / 'other-public.pem'
        self.command('openssl', 'genpkey', '-algorithm', 'ED25519', '-out', other_private)
        self.command('openssl', 'pkey', '-in', other_private, '-pubout', '-out', other_public)
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence, public=other_public), 'trusted verification key')

    def test_valid_signature_wrong_environment_rejected(self):
        self.select('staging', IMAGE)
        self.commit()
        self.assert_rejected(self.promote('production', evidence=self.dev_evidence), 'environment does not match')

    def test_valid_signature_wrong_digest_rejected(self):
        self.resign(self.dev_evidence, lambda payload: payload.update(image=OTHER_IMAGE))
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'image does not match')

    def test_stale_evidence_rejected(self):
        self.resign(self.dev_evidence, lambda payload: payload.update(verified_at=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=25)).isoformat()))
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'stale')

    def test_future_evidence_rejected(self):
        self.resign(self.dev_evidence, lambda payload: payload.update(verified_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).isoformat()))
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'future')

    def test_signed_failed_rollout_rejected(self):
        self.resign(self.dev_evidence, lambda payload: payload['deployment'].update(available_replicas=0))
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'rollout did not complete')

    def test_signed_failed_smoke_rejected(self):
        self.resign(self.dev_evidence, lambda payload: payload['smoke'].update(success=False))
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'smoke checks did not pass')

    def test_wrong_gitops_commit_rejected(self):
        def change(payload):
            payload['gitops_commit'] = self.initial_commit
            payload['argocd']['revision'] = self.initial_commit
        self.resign(self.dev_evidence, change)
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'recorded GitOps commit')

    def test_nonancestor_gitops_commit_rejected(self):
        self.git('checkout', '-b', 'unmerged')
        marker = self.root / 'unmerged-marker'
        marker.write_text('not reviewed')
        unmerged = self.commit()
        self.git('checkout', 'main')
        def change(payload):
            payload['gitops_commit'] = unmerged
            payload['argocd']['revision'] = unmerged
        self.resign(self.dev_evidence, change)
        self.assert_rejected(self.promote('staging', evidence=self.dev_evidence), 'trusted history')

    def test_create_rejects_incomplete_rollout(self):
        self.create('dev', mutation=lambda reports: reports['deployment']['items'][0]['status'].update(readyReplicas=0), expect_failure=True)

    def test_create_rejects_unobserved_generation(self):
        self.create('dev', mutation=lambda reports: reports['deployment']['items'][0]['status'].update(observedGeneration=2), expect_failure=True)

    def test_create_rejects_wrong_runtime_image_id(self):
        self.create('dev', mutation=lambda reports: reports['pods']['items'][0]['status']['containerStatuses'][0].update(imageID=OTHER_IMAGE), expect_failure=True)

    def test_create_rejects_wrong_argo_revision(self):
        self.create('dev', mutation=lambda reports: reports['argocd']['status']['sync'].update(revision=self.initial_commit), expect_failure=True)

    def test_create_rejects_missing_smoke_check(self):
        self.create('dev', mutation=lambda reports: reports['smoke'].update(checks=CHECKS[:-1]), expect_failure=True)

    def test_create_rejects_wrong_deployment_namespace(self):
        self.create('dev', mutation=lambda reports: reports['deployment']['items'][0]['metadata'].update(namespace='boutique-production'), expect_failure=True)

    def test_create_rejects_old_homelab_argo_path(self):
        self.create('dev', mutation=lambda reports: reports['argocd']['spec']['source'].update(path='homelab/dev'), expect_failure=True)

    def test_create_rejects_untrusted_argo_repository(self):
        self.create('dev', mutation=lambda reports: reports['argocd']['spec']['source'].update(repoURL='https://example.com/untrusted.git'), expect_failure=True)

    def test_create_accepts_production_lab_argo_profile(self):
        self.create('dev', mutation=lambda reports: reports['argocd']['spec']['source'].update(path='lab-profiles/dev'))

    def test_create_rejects_smoke_origin_from_another_environment(self):
        self.create('dev', mutation=lambda reports: reports['smoke'].update(origin='https://production.boutique.example.com'), expect_failure=True)

    def test_rollback_requires_previous_same_environment_verified_digest(self):
        self.select('production', IMAGE)
        self.commit()
        evidence = self.create('production')
        self.select('production', OTHER_IMAGE)
        self.commit()
        result = self.script('rollback.py', 'cart', 'production', IMAGE, '--evidence', evidence,
                             '--public-key', self.public, '--current-image', OTHER_IMAGE)
        output = self.assert_success(result)
        self.assertEqual(output['image'], IMAGE)
        self.assertEqual(output['previous_image'], OTHER_IMAGE)

    def test_rollback_rejects_cross_environment_evidence(self):
        self.select('production', OTHER_IMAGE)
        self.commit()
        result = self.script('rollback.py', 'cart', 'production', IMAGE, '--evidence', self.dev_evidence,
                             '--public-key', self.public, '--current-image', OTHER_IMAGE)
        self.assert_rejected(result, 'environment does not match')

    def test_rollback_rejects_stale_current_selection(self):
        self.select('production', IMAGE)
        self.commit()
        evidence = self.create('production')
        self.select('production', OTHER_IMAGE)
        self.commit()
        result = self.script('rollback.py', 'cart', 'production', IMAGE, '--evidence', evidence,
                             '--public-key', self.public, '--current-image', IMAGE)
        self.assert_rejected(result, 'Current environment image changed')


class DeliveryRecordTests(DeliveryFixture):
    def setUp(self):
        super().setUp()
        self.release_private = Path(self.temporary.name) / 'release-private.pem'
        self.release_public = Path(self.temporary.name) / 'release-public.pem'
        self.command('openssl', 'genpkey', '-algorithm', 'ED25519', '-out', self.release_private)
        self.command('openssl', 'pkey', '-in', self.release_private, '-pubout', '-out', self.release_public)
        self.release_record = self.attest(IMAGE)

    def attest(self, image, mutation=None):
        record = {'schema_version': 1, 'service': 'cart', 'image': image,
                  'source_commit': 'e' * 40, 'build_url': 'https://jenkins.example.com/job/boutique-cart/job/main/42/',
                  'tests_passed': True, 'security_gate_passed': True, 'sbom_sha256': 'c' * 64, 'scan_sha256': 'd' * 64}
        if mutation:
            mutation(record)
        plain = Path(self.temporary.name) / 'release.json'
        envelope = Path(self.temporary.name) / 'release-attestation.json'
        plain.write_text(json.dumps(record))
        self.assert_success(self.script('release_attestation.py', 'sign', '--record', plain,
                                       '--signing-key', self.release_private, '--output', envelope))
        return envelope

    def promote_with_release(self, environment, image=IMAGE, evidence=None):
        args = ['cart', environment, image, '--release-record', self.release_record,
                '--release-public-key', self.release_public]
        if evidence:
            args += ['--evidence', evidence, '--public-key', self.public]
        return self.script('promote.py', *args)

    def gate(self, base):
        return self.script('check_delivery_change.py', '--base', base,
                           '--release-public-key', self.release_public, '--evidence-public-key', self.public)

    def delivery_record(self, environment):
        return self.root / 'promotionrecords' / environment / 'cart.json'

    def test_dev_requires_signed_release_record_in_pr(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote('dev', OTHER_IMAGE))
        self.commit()
        self.assert_rejected(self.gate(base), 'requires a new signed delivery record')

    def test_registry_rename_cannot_bypass_image_change_gate(self):
        base = self.git('rev-parse', 'HEAD')
        path = self.root / 'services/cart/overlays/dev/kustomization.yaml'
        data = yaml.safe_load(path.read_text())
        data['images'][0]['newName'] = 'registry.example.com/unscanned-cart'
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        self.commit()
        self.assert_rejected(self.gate(base), 'requires a new signed delivery record')

    def test_dev_signed_release_passes_pr_gate(self):
        base = self.git('rev-parse', 'HEAD')
        self.release_record = self.attest(OTHER_IMAGE)
        self.assert_success(self.promote_with_release('dev', OTHER_IMAGE))
        self.commit()
        self.assertEqual(len(self.assert_success(self.gate(base))['verified_changes']), 1)

    def test_staging_signed_release_and_verification_pass_pr_gate(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        self.commit()
        self.assert_success(self.gate(base))

    def test_forged_release_record_rejected(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        path = self.delivery_record('staging')
        record = json.loads(path.read_text())
        record['release']['payload']['source_commit'] = 'f' * 40
        path.write_text(json.dumps(record))
        self.commit()
        self.assert_rejected(self.gate(base), 'signature validation failed')

    def test_forged_verification_record_rejected(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        path = self.delivery_record('staging')
        record = json.loads(path.read_text())
        record['verification']['payload']['smoke']['success'] = False
        path.write_text(json.dumps(record))
        self.commit()
        self.assert_rejected(self.gate(base), 'signature validation failed')

    def test_untrusted_release_key_rejected(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        self.commit()
        result = self.script('check_delivery_change.py', '--base', base,
                             '--release-public-key', self.public, '--evidence-public-key', self.public)
        self.assert_rejected(result, 'trusted verification key')

    def test_stale_base_target_selection_requires_replanning(self):
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        manifest = self.root / 'services/cart/overlays/staging/kustomization.yaml'
        planned_manifest = manifest.read_bytes()
        path = self.delivery_record('staging')
        planned_record = path.read_bytes()
        self.git('checkout', 'HEAD', '--', 'services/cart/overlays/staging/kustomization.yaml')
        path.unlink()
        self.select('staging', OTHER_IMAGE)
        new_base = self.commit()
        manifest.write_bytes(planned_manifest)
        path.write_bytes(planned_record)
        self.commit()
        self.assert_rejected(self.gate(new_base), 'base image changed')

    def test_changed_preceding_environment_selection_rejected(self):
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        self.git('stash', 'push', '--include-untracked')
        self.select('dev', OTHER_IMAGE)
        new_base = self.commit()
        self.git('stash', 'pop')
        self.commit()
        self.assert_rejected(self.gate(new_base), 'Preceding environment image changed')

    def test_record_without_matching_image_change_rejected(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote_with_release('dev'))
        self.commit()
        self.assert_rejected(self.gate(base), 'matching image selection')

    def test_rollback_record_passes_only_for_same_env_prior_verified_image(self):
        self.select('production', IMAGE)
        self.commit()
        proof = self.create('production')
        self.select('production', OTHER_IMAGE)
        base = self.commit()
        result = self.script('rollback.py', 'cart', 'production', IMAGE, '--evidence', proof,
                             '--public-key', self.public, '--current-image', OTHER_IMAGE,
                             '--release-record', self.release_record, '--release-public-key', self.release_public)
        self.assert_success(result)
        self.commit()
        self.assert_success(self.gate(base))

    def test_tools_can_evaluate_separate_pr_checkout(self):
        base = self.git('rev-parse', 'HEAD')
        self.assert_success(self.promote_with_release('staging', evidence=self.dev_evidence))
        self.commit()
        result = subprocess.run([sys.executable, str(SOURCE / 'scripts/check_delivery_change.py'),
                                 '--base', base, '--root', str(self.root),
                                 '--release-public-key', str(self.release_public), '--evidence-public-key', str(self.public)],
                                capture_output=True, text=True)
        self.assert_success(result)


@unittest.skipUnless(shutil.which('kubectl'), 'kubectl required for real Kustomize policy tests')
class RenderedImagePolicyTests(DeliveryFixture):
    def render_gate(self):
        return self.script('check_rendered_images.py')

    def test_real_kustomize_profiles_match_overlay_image_selections(self):
        self.assert_success(self.render_gate())

    def test_base_image_registry_change_cannot_bypass_overlay_gate(self):
        path = self.root / 'services/cart/base/deployment.yaml'
        data = yaml.safe_load(path.read_text())
        data['spec']['template']['spec']['containers'][0]['image'] = 'evil.example.com/cart@sha256:' + 'c' * 64
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        self.assert_rejected(self.render_gate(), 'bypasses its environment overlay')

    def test_unscanned_init_container_rejected(self):
        path = self.root / 'services/cart/base/deployment.yaml'
        data = yaml.safe_load(path.read_text())
        data['spec']['template']['spec']['initContainers'] = [{'name': 'unscanned', 'image': 'evil.example.com/sidecar:latest'}]
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        self.assert_rejected(self.render_gate(), 'Unapproved app sidecar')


if __name__ == '__main__':
    unittest.main()
