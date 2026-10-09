"""Mock receiver contract checks; these do not validate ServiceNow business rules."""
import importlib.util
import unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('receivers', Path(__file__).parent.parent/'mock-receivers.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class ScriptedContractTests(unittest.TestCase):
    def setUp(self):
        m.incidents.clear(); m.cycles.clear(); m.events.clear()
        self.firing = {'key':'a'*64,'status':'firing','revision':1,'summary':'synthetic test'}

    def test_retry_and_late_firing_do_not_duplicate_or_reopen(self):
        m.scripted_upsert(self.firing); m.scripted_upsert(self.firing)
        m.scripted_upsert(dict(self.firing,status='resolved',revision=2))
        m.scripted_upsert(self.firing)
        self.assertEqual(len(m.incidents),1)
        self.assertEqual(next(iter(m.incidents.values()))['state'],'6')
        self.assertEqual([event['operation'] for event in m.events],['create','resolve'])

    def test_resolution_before_firing_retains_tombstone(self):
        m.scripted_upsert(dict(self.firing,status='resolved',revision=2))
        m.scripted_upsert(self.firing)
        self.assertFalse(m.incidents)
        self.assertEqual(m.cycles[self.firing['key']]['status'],'resolved')

if __name__ == '__main__': unittest.main()
