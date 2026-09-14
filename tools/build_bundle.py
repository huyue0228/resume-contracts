"""机械生成协议分发物；--check 只验证，不写入。"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from resume_contracts import VERSION
from resume_contracts.models import AllocationRequest, AllocationResponse, AllocationCapabilities
from resume_contracts.allocation import allocation_request, allocation_response, allocation_capabilities, canonical_snapshot
from allocation_codegen import generate
import subprocess
from resume_contracts.models import AnalysisRequestV3,AnalysisResponseV3,KernelCapabilitiesV1
from resume_contracts.fixtures import request_fixture,response_fixture,capabilities_fixture


def render(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()


def bundle():
    result={"request.schema.json":render(AnalysisRequestV3.model_json_schema()),"response.schema.json":render(AnalysisResponseV3.model_json_schema()),
            "request.example.json":render(request_fixture().model_dump(mode="json")),"response.example.json":render(response_fixture()),
            "capabilities.schema.json":render(KernelCapabilitiesV1.model_json_schema()),
            "capabilities.example.json":render(capabilities_fixture().model_dump(mode="json"))}
    for name,model,example in [('allocation.request',AllocationRequest,allocation_request().model_dump(mode='json')),('allocation.response',AllocationResponse,allocation_response()),('allocation.capabilities',AllocationCapabilities,allocation_capabilities().model_dump(mode='json'))]:
        result[name+'.schema.json']=render(model.model_json_schema())
        result[name+'.example.json']=render(example)
    result['allocation.cases.json']=(ROOT/'resume_contracts'/'allocation_cases.json').read_bytes()
    request=allocation_request()
    result['allocation.hash-vectors.json']=render([dict(snapshot=request.snapshot.model_dump(mode='json'),canonical=canonical_snapshot(request.snapshot.model_dump(mode='json')).decode(),sha256=request.snapshot_hash)])
    result['allocation_types.go.txt']=subprocess.run(['gofmt'],input=generate(),capture_output=True,check=True).stdout
    sdk={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT/"resume_contracts").glob("*.py")}
    result["manifest.json"]=render(dict(version=VERSION,files={name:hashlib.sha256(raw).hexdigest() for name,raw in result.items()},python=sdk))
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--platform",type=Path)
    parser.add_argument("--kernel",type=Path)
    args=parser.parse_args()
    destinations=[ROOT/"resume_contracts"/"bundle"]
    if args.platform:
        destinations.append(args.platform/"internal"/"contract"/"bundle")
    if args.kernel:destinations.append(args.kernel/"internal"/"contract"/"bundle")
    for destination in destinations:
        for name,raw in bundle().items():
            path=destination/name
            if args.check:
                if not path.exists() or path.read_bytes()!=raw:raise SystemExit(f"contract drift: {path}")
            else:
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for consumer in (args.platform,args.kernel):
        if consumer:
            path=consumer/'internal'/'contract'/'allocation_types.go'
            raw=bundle()['allocation_types.go.txt']
            if args.check:
                if not path.exists() or path.read_bytes()!=raw: raise SystemExit(f'contract drift: {path}')
            else: path.write_bytes(raw)
    print("Contract bundle verified" if args.check else "Contract bundle generated")


if __name__=="__main__":main()
