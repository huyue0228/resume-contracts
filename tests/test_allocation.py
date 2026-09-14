import copy
import unittest
from pydantic import ValidationError
from resume_contracts.models import AllocationRequest
from resume_contracts.allocation import allocation_request, allocation_response, snapshot_hash

class AllocationTests(unittest.TestCase):
    def test_whitelist(self):
        for path in ('root','snapshot','member','tag','demand'):
            for key in ('resume_text','quote','summary','file_url','headcount','is_public'):
                value=allocation_request().model_dump(mode='json')
                target={'root':value,'snapshot':value['snapshot'],'member':value['snapshot']['members'][0],'tag':value['snapshot']['members'][0]['tags'][0],'demand':value['snapshot']['demands'][0]}[path]
                target[key]='forbidden'
                with self.assertRaises(ValidationError):AllocationRequest.model_validate(value)
    def test_hash_canonical_sets(self):
        s=allocation_request().snapshot.model_dump(mode='json');other=copy.deepcopy(s)
        for collection in ('members','demands'):other[collection].reverse()
        self.assertEqual(snapshot_hash(s),snapshot_hash(other))
    def test_mock_coverage_and_required(self):
        req=allocation_request();self.assertEqual(allocation_response(req)['decisions'][0]['action'],'assign')
        req.snapshot.members[0].tags[0].confidence_bps=7999
        self.assertEqual(allocation_response(req)['decisions'][0]['reason_code'],'required_tags_unavailable')
    def test_duplicates(self):
        req=allocation_request().model_dump(mode='json');req['snapshot']['members']*=2
        with self.assertRaises(ValidationError):AllocationRequest.model_validate(req)
