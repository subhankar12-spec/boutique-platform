"""Exercise monitoring scopes, persistence and lab overrides through real Helm."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3] / 'boutique-gitops'


@unittest.skipUnless(shutil.which('helm'), 'Helm required for monitoring render checks')
class MonitoringHelmTests(unittest.TestCase):
    def render(self, profile, lab=False, image_values=None):
        args=['helm','template','boutique-monitoring-'+profile,str(ROOT/'monitoring'),'-f',str(ROOT/'monitoring/profiles'/profile/'values.yaml')]
        if lab:args += ['-f',str(ROOT/'lab-profiles/monitoring'/profile/'values.yaml')]
        if image_values:
            args += ['--set','incidentBridge.image.tag=','--set','incidentBridge.image.digest='+image_values]
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        resources=[d for d in yaml.safe_load_all(result.stdout) if d]
        identities=[(r['kind'],r['metadata'].get('namespace',''),r['metadata']['name']) for r in resources]
        self.assertEqual(len(identities),len(set(identities)))
        return resources

    def resource(self, resources, kind, name):
        return next(d for d in resources if d['kind']==kind and d['metadata']['name']==name)

    def test_profile_target_and_rbac_scopes_match(self):
        expected={'homelab':['boutique-dev'],'nonprod':['boutique-dev','boutique-staging'],'production':['boutique-production']}
        for profile,namespaces in expected.items():
            with self.subTest(profile=profile):
                resources=self.render(profile)
                config=yaml.safe_load(self.resource(resources,'ConfigMap','boutique-prometheus')['data']['prometheus.yml'])
                for job in config['scrape_configs']:
                    if job['job_name'] in ('boutique','orders'):
                        self.assertEqual(job['kubernetes_sd_configs'][0]['namespaces']['names'],namespaces)
                roles=[d for d in resources if d['kind']=='Role' and d['metadata']['name']=='monitoring-pod-discovery']
                self.assertEqual({r['metadata']['namespace'] for r in roles},set(namespaces))
                for role in roles:
                    for rule in role['rules']:
                        self.assertEqual(rule['resources'],['pods'])
                        self.assertEqual(set(rule['verbs']),{'get','list','watch'})
                alloy=self.resource(resources,'DaemonSet','alloy')['spec']['template']['spec']['containers'][0]
                labels={e['name']:e.get('value') for e in alloy['env']}
                self.assertEqual(labels['CLUSTER_NAME'],profile)

    def test_production_queue_uses_two_workers_and_scoped_secret(self):
        resources=self.render('production')
        deployment=self.resource(resources,'Deployment','incident-bridge')
        self.assertEqual(deployment['spec']['replicas'],2)
        pod=deployment['spec']['template']['spec'];container=pod['containers'][0]
        env={e['name']:e for e in container['env']}
        self.assertNotIn('QUEUE_PATH',env)
        self.assertEqual(env['QUEUE_DATABASE_URL']['valueFrom']['secretKeyRef']['name'],'monitoring-incident-queue')
        self.assertEqual(env['SERVICENOW_MODE']['value'],'scripted')
        self.assertFalse(any(d['kind']=='PersistentVolumeClaim' and d['metadata']['name']=='incident-bridge-data' for d in resources))
        self.assertEqual(self.resource(resources,'PodDisruptionBudget','incident-bridge')['spec']['minAvailable'],1)

    def test_lab_adds_only_mock_receiver_and_production_tls_queue(self):
        for profile in ('nonprod','production'):
            with self.subTest(profile=profile):
                cloud=self.render(profile);lab=self.render(profile,lab=True)
                key=lambda d:(d['kind'],d['metadata'].get('namespace',''),d['metadata']['name'])
                cloud_map={key(d):d for d in cloud};lab_map={key(d):d for d in lab}
                differences=[k for k in cloud_map if cloud_map[k]!=lab_map[k]]
                self.assertEqual(differences,[('Deployment','monitoring','incident-bridge')])
                self.resource(lab,'Deployment','mock-receivers')
                pod=self.resource(lab,'Deployment','incident-bridge')['spec']['template']['spec']
                env={e['name']:e.get('value') for e in pod['containers'][0]['env']}
                self.assertEqual(env['SERVICENOW_URL'],'http://mock-receivers:18080')
                self.assertEqual(env['ALLOW_HTTP_MOCK'],'true')
                self.assertEqual(pod['imagePullSecrets'],[{'name':'ghcr-pull'}])
                if profile=='production':
                    queue=self.resource(lab,'StatefulSet','incident-queue-postgres')
                    self.assertIn('ssl=on',queue['spec']['template']['spec']['containers'][0]['args'])
                    self.resource(lab,'Certificate','incident-queue-tls')
                else:
                    self.assertFalse(any(d['kind']=='StatefulSet' for d in lab))

    def test_one_reviewed_image_selection_reaches_cloud_and_lab(self):
        digest='sha256:'+'a'*64
        for profile in ('homelab','nonprod','production'):
            for lab in ([False] if profile=='homelab' else [False,True]):
                with self.subTest(profile=profile,lab=lab):
                    resources=self.render(profile,lab,digest)
                    image=self.resource(resources,'Deployment','incident-bridge')['spec']['template']['spec']['containers'][0]['image']
                    self.assertEqual(image,'ghcr.io/subhankar12-spec/boutique-incident-bridge@'+digest)

    def test_mutable_image_and_invalid_profile_are_rejected(self):
        for setting in ('incidentBridge.image.tag=latest','incidentBridge.image.digest=sha256:short','profile=unknown'):
            result=subprocess.run(['helm','template','monitoring',str(ROOT/'monitoring'),'--set',setting],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)

    def test_config_template_strings_and_dashboard_survive(self):
        resources=self.render('production')
        config=self.resource(resources,'ConfigMap','boutique-prometheus')['data']
        self.assertIn('{{ $labels.service }}',config['rules.yml'])
        dashboards=[d for d in resources if d['kind']=='ConfigMap' and any(k.endswith('.json') for k in d.get('data',{}))]
        self.assertTrue(dashboards)
        for d in dashboards:
            for key,value in d['data'].items():
                if key.endswith('.json'):self.assertEqual(len(json.loads(value)['panels']),13)

    def test_cloud_projects_admit_every_rendered_resource_with_scoped_namespaces(self):
        for profile in ('homelab','nonprod','production'):
            docs=list(yaml.safe_load_all((ROOT/'applications'/('monitoring-'+profile+'.yaml')).read_text()))
            project=next(d for d in docs if d['kind']=='AppProject')['spec']
            namespaces={d['namespace'] for d in project['destinations']}
            for resource in self.render(profile):
                group=resource['apiVersion'].split('/')[0] if '/' in resource['apiVersion'] else ''
                kind=resource['kind'];namespace=resource['metadata'].get('namespace')
                allowed=project['namespaceResourceWhitelist'] if namespace else project['clusterResourceWhitelist']
                self.assertIn({'group':group,'kind':kind},allowed)
                if namespace:self.assertIn(namespace,namespaces)

    def test_cloud_argo_sources_select_chart_and_profile_values(self):
        for profile in ('homelab','nonprod','production'):
            docs=list(yaml.safe_load_all((ROOT/'applications'/('monitoring-'+profile+'.yaml')).read_text()))
            source=next(d for d in docs if d['kind']=='Application')['spec']['source']
            self.assertEqual(source['path'],'monitoring')
            self.assertEqual(source['helm'],{'releaseName':'boutique-monitoring-'+profile,'valueFiles':['profiles/'+profile+'/values.yaml']})


if __name__ == '__main__':
    unittest.main()
