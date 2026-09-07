import unittest
from pydantic import ValidationError
from resume_contracts.fixtures import request_fixture,response_fixture,capabilities_fixture
from resume_contracts.models import AnalysisRequestV1,AnalysisResponseV1,KernelCapabilitiesV1


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
    def test_internal_versions_can_evolve_without_sdk_upgrade(self):
        request = request_fixture().model_dump()
        request["pin"].update(toolset_version="tools/2027.5", instruction_version="prompt/a17", policy_version="policy/new")
        parsed = AnalysisRequestV1.model_validate(request)
        self.assertEqual(AnalysisResponseV1.model_validate(response_fixture(parsed)).pin, parsed.pin)
        capabilities_fixture(toolset_version="tools/2027.5", instruction_version="prompt/a17")
    def test_public_contract_and_nonempty_pins_remain_strict(self):
        for key in ("protocol_version", "result_schema_version"):
            payload=request_fixture().model_dump();payload["pin"][key]="unsupported/v99"
            with self.assertRaises(ValidationError):AnalysisRequestV1.model_validate(payload)
        for key in ("toolset_version", "instruction_version", "policy_version"):
            payload=request_fixture().model_dump();payload["pin"][key]=" "
            with self.assertRaises(ValidationError):AnalysisRequestV1.model_validate(payload)


if __name__=="__main__":unittest.main()
