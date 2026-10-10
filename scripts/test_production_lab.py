"""Regression checks for context isolation, credential safety and release gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('production_lab', Path(__file__).with_name('production-lab.py'))
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class ProductionLabSafety(unittest.TestCase):
    def test_explicit_context_never_uses_current_context(self):
        with patch.object(lab, 'run', return_value='') as run:
            lab.kube('production', 'get', 'pods')
        self.assertEqual(run.call_args.args[0], ['kubectl', '--context', 'kind-boutique-production', 'get', 'pods'])
        with patch.object(lab, 'run') as run:
            with self.assertRaises(ValueError): lab.kube('other-production', 'delete', 'namespace', 'anything')
            run.assert_not_called()

    def test_failed_doctor_prevents_cluster_creation(self):
        with patch.object(lab, 'doctor_report', return_value={'ready': False}), patch.object(lab, 'doctor'), patch.object(lab, 'run') as run:
            with self.assertRaises(ValueError): lab.bootstrap('production')
            run.assert_not_called()

    def test_mutable_and_wrong_registry_images_cannot_deploy(self):
        def render(suffix):
            return '\n'.join(f'  image: ghcr.io/subhankar12-spec/boutique-{svc}{suffix}' for svc in lab.SERVICES)
        lab.validate_release_images(render('@sha256:' + 'a'*64))
        for suffix in (':bootstrap', ':latest', ':local', ':sha-commit', '@sha256:short'):
            with self.assertRaises(ValueError): lab.validate_release_images(render(suffix))
        with self.assertRaises(ValueError): lab.validate_release_images(render('@sha256:' + 'a'*64).replace('ghcr.io/', 'untrusted.test/'))

    def test_project_destinations_are_scoped_and_profile_inherits_promotion(self):
        project, app = lab.argo_application('production', 'production')
        self.assertEqual(app['spec']['source']['path'], 'environments/production')
        self.assertEqual(app['spec']['source']['helm']['valueFiles'],['values.yaml','releases.yaml','../../lab-profiles/production/values.yaml'])
        self.assertEqual(project['spec']['destinations'], [{'namespace': 'boutique-production', 'server': 'https://kubernetes.default.svc'}])
        self.assertEqual(project['spec']['clusterResourceWhitelist'], [{'group': '', 'kind': 'Namespace'}])
        project, _ = lab.argo_application('production', 'production', monitoring=True)
        self.assertEqual({x['namespace'] for x in project['spec']['destinations']}, {'monitoring', 'monitoring-logs', 'boutique-production'})

    def test_monitoring_uses_shared_helm_chart_with_cluster_and_lab_values(self):
        for cluster in ('nonprod','production'):
            project,app=lab.argo_application(cluster,'production' if cluster=='production' else 'dev',monitoring=True)
            self.assertEqual(app['spec']['source']['path'],'monitoring')
            self.assertEqual({d['namespace'] for d in project['spec']['destinations']},{'monitoring','monitoring-logs'}|{'boutique-'+e for e in lab.CLUSTERS[cluster]})
            self.assertEqual(project['spec']['clusterResourceWhitelist'],[{'group':'','kind':'Namespace'}])
            self.assertEqual(app['spec']['source']['helm'],{'releaseName':'lab-monitoring-'+cluster,'valueFiles':['profiles/'+cluster+'/values.yaml','../lab-profiles/monitoring/'+cluster+'/values.yaml']})
            rendered='image: ghcr.io/subhankar12-spec/boutique-incident-bridge@sha256:'+'a'*64
            with patch.object(lab,'cluster_state'),patch.object(lab,'run',return_value=rendered) as render,patch.object(lab,'apply'):
                lab.deploy(cluster,monitoring=True)
                self.assertEqual(render.call_args.args[0],['python3',lab.GITOPS/'scripts/render-monitoring.py',cluster,'--lab'])

    def test_default_monitoring_needs_no_incident_image(self):
        self.assertEqual(lab.validate_release_images('image: prom/prometheus@sha256:' + 'a'*64, monitoring=True), [])
        with self.assertRaises(ValueError):
            lab.validate_release_images('image: ghcr.io/subhankar12-spec/boutique-incident-bridge:latest', monitoring=True)

    def test_private_credentials_reject_readable_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'token'; path.write_text('test-token'); path.chmod(0o644)
            with self.assertRaises(ValueError): lab.read_private(path)
            path.chmod(0o600); self.assertEqual(lab.read_private(path), 'test-token')
            alias = Path(tmp) / 'alias'; alias.symlink_to(path)
            with self.assertRaises(ValueError): lab.read_private(alias)

    def test_cache_checksum_cannot_be_bypassed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pinned.yaml'; path.write_bytes(b'tampered')
            with patch.object(lab.urllib.request, 'urlopen') as request:
                with self.assertRaises(ValueError): lab.download_verified({'sha256': '0'*64}, path)
                request.assert_not_called()

    def test_controller_manifests_have_no_mutable_tags_after_lock(self):
        for name in lab.LOCK['manifests']:
            cache = lab.CACHE / (name + '.yaml')
            if not cache.exists(): self.skipTest('Run production-lab.py fetch-manifests first for artifact validation')
            rendered = lab.pinned_manifest(name)
            images = lab.re.findall(r'^\s*image:\s*(\S+)', rendered, lab.re.M)
            self.assertTrue(images)
            self.assertTrue(all('@sha256:' in image and len(image.rsplit(':', 1)[1]) == 64 for image in images))

    def test_secret_lookup_failure_never_rotates_existing_credentials(self):
        with patch.object(lab, 'kube', side_effect=RuntimeError('API unavailable')), patch.object(lab, 'apply') as apply:
            with self.assertRaises(RuntimeError): lab.secret('production', 'monitoring', 'monitoring-incident-queue', {'password': 'new'})
            apply.assert_not_called()

    def test_verifier_identity_has_no_secret_or_write_permissions(self):
        admin = json.dumps({'clusters': [{'cluster': {'server': 'https://127.0.0.1:6443', 'certificate-authority-data': 'Y2E='}}]})
        with tempfile.TemporaryDirectory() as tmp, patch.object(lab, 'STATE', Path(tmp)), patch.object(lab, 'cluster_state'), patch.object(lab, 'namespace'), patch.object(lab, 'apply') as apply, patch.object(lab, 'kube', side_effect=['fixture-token', admin]):
            (Path(tmp)/'production').mkdir()
            lab.export_verifier('production', '1h')
            roles = [o for o in apply.call_args.args[1]['items'] if o['kind'] == 'Role']
            for role in roles:
                for rule in role['rules']:
                    self.assertNotIn('secrets', rule['resources'])
                    self.assertTrue(set(rule['verbs']) <= {'get','list','watch'})
            credential = Path(tmp)/'production/jenkins-verifier-production.json'
            self.assertEqual(credential.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('client-key-data', credential.read_text())

    def test_dev_can_activate_without_unreleased_staging(self):
        rendered='\n'.join('image: ghcr.io/subhankar12-spec/boutique-'+service+'@sha256:'+'a'*64 for service in lab.SERVICES)
        with patch.object(lab,'cluster_state'), patch.object(lab,'run',return_value=rendered) as render, patch.object(lab,'apply') as apply:
            lab.deploy('nonprod',environment='dev')
            self.assertEqual(len(render.call_args_list),1)
            self.assertEqual(render.call_args.args[0],['python3',lab.GITOPS/'scripts/render.py','dev','--profile','lab'])
            app=apply.call_args.args[1]['items'][1]
            self.assertEqual(app['metadata']['name'],'boutique-dev')
            self.assertEqual(app['spec']['destination']['namespace'],'boutique-dev')
        with patch.object(lab,'cluster_state') as cluster:
            with self.assertRaises(ValueError):lab.deploy('production',environment='dev')
            with self.assertRaises(ValueError):lab.readiness('nonprod',monitoring=True,environment='dev')
            cluster.assert_not_called()

    def test_policy_probe_has_no_token_and_uses_pinned_image(self):
        job = lab.probe_job('disposable', 'deny', '10.96.0.5', True)
        pod = job['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertIn('@sha256:', pod['containers'][0]['image'])
        self.assertNotIn('frontend.', pod['containers'][0]['command'][-1])  # DNS failure cannot masquerade as a block.


if __name__ == '__main__': unittest.main()
