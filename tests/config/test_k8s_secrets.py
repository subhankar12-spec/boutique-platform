"""Secret setup must fail closed and never rotate existing database credentials."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('local_secrets', Path(__file__).resolve().parents[2] / 'scripts/k8s-secrets.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def inventory(*names):
    return json.dumps({'items': [{'metadata': {'name': name}} for name in names]})


class SecretPreservationTests(unittest.TestCase):
    def test_api_failure_stops_before_secret_writes(self):
        with patch.object(helper, 'kubectl', side_effect=['namespace/boutique-dev', subprocess.CalledProcessError(1, 'kubectl')]) as call:
            with self.assertRaises(subprocess.CalledProcessError):
                helper.provision('dev')
            self.assertFalse(any(c.args[0] == 'create' for c in call.call_args_list))

    def test_partial_redis_pair_stops_before_any_write(self):
        with patch.object(helper, 'kubectl', side_effect=['namespace/boutique-dev', inventory('redis-auth')]) as call:
            with self.assertRaises(ValueError):
                helper.provision('dev')
            self.assertEqual(call.call_count, 2)

    def test_existing_secrets_are_never_rewritten(self):
        with patch.object(helper, 'kubectl', side_effect=['namespace/boutique-dev', inventory('redis-auth', 'cart-redis', 'frontend-session', 'orders-database')]) as call:
            helper.provision('dev')
            self.assertEqual(call.call_count, 2)

    def test_new_pair_uses_same_password_and_create_only(self):
        with patch.object(helper, 'kubectl', side_effect=['namespace/boutique-dev', inventory(), '', '', '', '']) as call:
            helper.provision('dev')
            writes = call.call_args_list[2:]
            self.assertTrue(all(c.args == ('create', '-f', '-') for c in writes))
            docs = {c.kwargs['document']['metadata']['name']: c.kwargs['document'] for c in writes}
            password = base64.b64decode(docs['redis-auth']['data']['password']).decode()
            self.assertEqual(base64.b64decode(docs['cart-redis']['data']['url']).decode(), 'redis://:' + password + '@redis:6379/0')


if __name__ == '__main__':
    unittest.main()
