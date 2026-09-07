import unittest
from pydantic import ValidationError
from resume_contracts.fixtures import request_fixture,response_fixture
from resume_contracts.models import AnalysisRequestV1,AnalysisResponseV1


class ContractTests(unittest.TestCase):
    def test_examples_and_scenarios(self):
        AnalysisRequestV1.model_validate_json(request_fixture().model_dump_json())
        for scenario in ["success","low_match","failed","budget_exhausted","invalid_reference","incomplete"]:
            AnalysisResponseV1.model_validate(response_fixture(scenario=scenario))
    def test_reject_business_actions(self):
        with self.assertRaises(ValidationError):AnalysisResponseV1.model_validate(response_fixture(scenario="invalid_schema"))
    def test_duplicate_pool(self):
        payload=request_fixture().model_dump();payload["scope"]["jobs"][1]=payload["scope"]["jobs"][0]
        with self.assertRaises(ValidationError):AnalysisRequestV1.model_validate(payload)


if __name__=="__main__":unittest.main()
