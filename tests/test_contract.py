import unittest
from pydantic import ValidationError
from resume_contracts.fixtures import request_fixture,response_fixture,capabilities_fixture
from resume_contracts.models import AnalysisRequestV4,AnalysisResponseV4,KernelCapabilitiesV1


class ContractTests(unittest.TestCase):
    def test_examples_and_scenarios(self):
        AnalysisRequestV4.model_validate_json(request_fixture().model_dump_json())
        for scenario in ["success","low_match","failed","budget_exhausted","invalid_reference","incomplete"]:
            AnalysisResponseV4.model_validate(response_fixture(scenario=scenario))
    def test_reject_business_actions(self):
        with self.assertRaises(ValidationError):AnalysisResponseV4.model_validate(response_fixture(scenario="invalid_schema"))
    def test_duplicate_pool(self):
        payload=request_fixture().model_dump();payload["scope"]["jobs"].append(payload["scope"]["jobs"][0])
        with self.assertRaises(ValidationError):AnalysisRequestV4.model_validate(payload)
    def test_only_one_application_standard_and_bounded_tag_dictionary(self):
        from copy import deepcopy
        request = request_fixture().model_dump()
        other = deepcopy(request["scope"]["jobs"][0]); other["ref"] = "unapplied-software"
        request["scope"]["jobs"].append(other)
        with self.assertRaises(ValidationError): AnalysisRequestV4.model_validate(request)
        response = response_fixture(); response["matches"].append(deepcopy(response["matches"][0]))
        with self.assertRaises(ValidationError): AnalysisResponseV4.model_validate(response)
        request = request_fixture().model_dump()
        request["protocol_version"] = "resume-analysis/v2"
        with self.assertRaises(ValidationError): AnalysisRequestV4.model_validate(request)
        request = request_fixture().model_dump()
        tag = dict(code="cad", name="三维设计", category="skill", description="原文证实建模经历")
        request["scope"]["tag_catalog"] = [tag, tag]
        with self.assertRaises(ValidationError): AnalysisRequestV4.model_validate(request)
    def test_reject_retired_major_dictionary_and_v3_requests(self):
        payload = request_fixture().model_dump()
        payload["scope"]["taxonomy"] = []
        with self.assertRaises(ValidationError): AnalysisRequestV4.model_validate(payload)
        payload = request_fixture().model_dump()
        payload["protocol_version"] = "resume-analysis/v3"
        with self.assertRaises(ValidationError): AnalysisRequestV4.model_validate(payload)

    def test_internal_versions_can_evolve_without_sdk_upgrade(self):
        request = request_fixture().model_dump()
        request["pin"].update(toolset_version="tools/2027.5", instruction_version="prompt/a17", policy_version="policy/new")
        parsed = AnalysisRequestV4.model_validate(request)
        self.assertEqual(AnalysisResponseV4.model_validate(response_fixture(parsed)).pin, parsed.pin)
        capabilities_fixture(toolset_version="tools/2027.5", instruction_version="prompt/a17")
    def test_public_contract_and_nonempty_pins_remain_strict(self):
        for key in ("protocol_version", "result_schema_version"):
            payload=request_fixture().model_dump();payload["pin"][key]="unsupported/v99"
            with self.assertRaises(ValidationError):AnalysisRequestV4.model_validate(payload)
        for key in ("toolset_version", "instruction_version", "policy_version"):
            payload=request_fixture().model_dump();payload["pin"][key]=" "
            with self.assertRaises(ValidationError):AnalysisRequestV4.model_validate(payload)


class TextContractTests(unittest.TestCase):
    def test_canonical_pages_preserve_blank_page_and_global_lines(self):
        import hashlib
        from resume_contracts.models import ResumeTextV2
        pages = ["中文第一行\nEnglish second line\n", "", "负责后端服务开发与测试工作\n"]
        text = ResumeTextV2(file_sha256="a"*64, text_sha256=hashlib.sha256("\f".join(pages).encode()).hexdigest(),
                            extractor_version="test/v2", pages=pages, status="ready")
        self.assertEqual(text.lines()[3:5], [(2, ""), (3, "负责后端服务开发与测试工作")])
        self.assertEqual(len(text.lines()), 6)

    def test_reject_old_protocol_signed_artifact_tampered_and_oversize_text(self):
        from resume_contracts.models import AnalysisRequestV4
        import hashlib
        base = request_fixture().model_dump()
        from copy import deepcopy
        variants = []
        old = deepcopy(base); old["protocol_version"] = "resume-analysis/v1"; variants.append(old)
        artifact = deepcopy(base); artifact["scope"]["artifact"] = {}; variants.append(artifact)
        for pages in [["bad\rtext"], ["bad\fpage"], ["bad\x00text"], ["中" * 350000], [""]]:
            payload = deepcopy(base); text = payload["scope"]["resume_text"]
            text.update(pages=pages, text_sha256=hashlib.sha256("\f".join(pages).encode()).hexdigest())
            variants.append(payload)
        tampered = deepcopy(base); tampered["scope"]["resume_text"]["pages"] = ["changed"]; variants.append(tampered)
        for payload in variants:
            with self.assertRaises(ValidationError): AnalysisRequestV4.model_validate(payload)


class ConsumerBundleTests(unittest.TestCase):
    def test_distribution_only_writes_go_consumer_bundles(self):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            platform = Path(temporary) / "platform"
            kernel = Path(temporary) / "kernel"
            command = [sys.executable, str(root / "tools/build_bundle.py"),
                       "--platform", str(platform), "--kernel", str(kernel)]
            subprocess.run(command, check=True, capture_output=True)
            subprocess.run(command + ["--check"], check=True, capture_output=True)
            for consumer in (platform, kernel):
                self.assertEqual((consumer / "internal/contract/bundle/manifest.json").read_bytes(),
                                 (root / "resume_contracts/bundle/manifest.json").read_bytes())
                self.assertFalse((consumer / "backend").exists())


if __name__=="__main__":unittest.main()
