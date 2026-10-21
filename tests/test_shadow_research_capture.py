import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

PATH=Path(__file__).resolve().parents[1]/'scripts/shadow_research_capture.py'
spec=importlib.util.spec_from_file_location('capture_runner',PATH);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ShadowResearchCaptureTests(unittest.TestCase):
    def runtime(self):
        return {'mode':'shadow','minimum_legs':2,'maximum_legs':4,'pregame_only':True,
                'mappings':[{'pricing_block_reason':'unverified_payoff'},{'pricing_block_reason':'unverified_selector'}]}

    def test_no_unblocked_or_live_capture(self):
        config=self.runtime();self.assertEqual(sum(module.validate_runtime(config).values()),2)
        config['mappings'][0]['pricing_block_reason']=None
        with self.assertRaisesRegex(ValueError,'pricing_blocks'):module.validate_runtime(config)
        config=self.runtime();config['mode']='live'
        with self.assertRaisesRegex(ValueError,'shadow_mode'):module.validate_runtime(config)

    def test_account_selection_rejects_wrong_tier_and_ambiguous_subscription(self):
        sub={'is_active':True,'bookmakers':{'pinnacle+30':{}},'sport_ids':[14],
             'valid_from':'2026-09-07T00:00:00Z','valid_until':'2026-10-07T00:00:00Z',
             'request_count':19,'request_limit':100000}
        polling={'bookmakers':['pinnacle+30'],'sport_id':14,'subscription_request_limit':100000}
        account={'retrieved_at':1788819047.,'subscriptions':[sub]}
        result=module.choose_subscription(account,polling,now=1788819047.)
        self.assertEqual(result['known_used'],19)
        self.assertEqual(result['billing_cycle_start'],1788739200.)
        self.assertEqual(polling.get('known_used'),None)
        with self.assertRaisesRegex(ValueError,'tier'):module.choose_subscription(account,{**polling,'subscription_request_limit':500000},now=1788819047.)
        with self.assertRaisesRegex(ValueError,'one_active'):module.choose_subscription({**account,'subscriptions':[sub,sub]},polling,now=1788819047.)

    def test_cleanup_stops_owned_process_group(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            module.stop_groups([child])
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None:child.kill();child.wait()

if __name__=='__main__':unittest.main()
