"""简历分析公开协议。这里不定义招聘准入或业务动作。"""
import hashlib
import json
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated

PROTOCOL = "resume-analysis/v5"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_TEXT_BYTES = 1024 * 1024
MAX_PAGES = 100
RESULT = "resume-application-assessment/v1"
VersionRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
SCORE_WEIGHTS = {"major_match": .30, "skills_match": .20, "experience_evidence": .25,
                 "job_requirement": .15, "resume_quality": .10}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TaskPinV1(StrictModel):
    pin_id: str = Field(min_length=1)
    kernel_build: VersionRef
    protocol_version: Literal[PROTOCOL] = PROTOCOL
    toolset_version: VersionRef
    result_schema_version: Literal[RESULT] = RESULT
    policy_version: VersionRef
    instruction_version: VersionRef
    model_config_revision: VersionRef


class KernelCapabilitiesV1(StrictModel):
    """公开兼容性固定；内部版本由内核声明，提交任务后必须精确执行冻结版本。"""
    protocol_version: Literal[PROTOCOL] = PROTOCOL
    result_schema_version: Literal[RESULT] = RESULT
    task_kinds: list[Literal["candidate.application_assessment"]] = Field(min_length=1)
    kernel_build: VersionRef
    toolset_version: VersionRef
    instruction_version: VersionRef
    mock: bool = False


class TaskBudgetV1(StrictModel):
    max_turns: int = Field(default=32, ge=1, le=64)
    max_tool_calls: int = Field(default=256, ge=1, le=512)
    max_duration_seconds: int = Field(default=600, ge=1, le=1800)
    max_tokens: int = Field(default=120000, ge=1, le=1000000)
    max_context_tokens: int = Field(default=32768, ge=1024, le=1000000)


class ModelConfigV1(StrictModel):
    api_style: Literal["responses", "chat_json"]
    base_url: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    structured_output_mode: str = "json_compat"
    timeout_seconds: float = Field(default=120, gt=0, le=1800)
    retry_count: int = Field(default=1, ge=0, le=5)
    insecure_skip_verify: bool = False


class ResumeTextV2(StrictModel):
    """唯一正文是 pages。页号从 1 开始；每页按 LF 分行，空页也占一行。

    CRLF/CR 在提取端统一为 LF，其余空白和末尾 LF 保留，不做 Unicode
    改写。全文仅在使用时以 FF 连接各页，UTF-8 编码后计算 text_sha256。
    """
    file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    extractor_version: VersionRef
    pages: list[str] = Field(min_length=1, max_length=MAX_PAGES)
    status: Literal["ready", "needs_attention"]
    warnings: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def canonical_text(self):
        if any(any(char in page for char in ("\r", "\f", "\x00")) for page in self.pages):
            raise ValueError("pages must contain canonical LF text without FF or NUL")
        raw = self.full_text().encode("utf-8")
        if len(raw) > MAX_TEXT_BYTES:
            raise ValueError("resume text exceeds byte limit")
        if hashlib.sha256(raw).hexdigest() != self.text_sha256:
            raise ValueError("resume text checksum mismatch")
        if self.status == "ready" and not any(page.strip() for page in self.pages):
            raise ValueError("ready text must not be empty")
        if self.status == "needs_attention" and not self.warnings:
            raise ValueError("incomplete text requires a quality warning")
        return self

    def full_text(self):
        return "\f".join(self.pages)

    def lines(self):
        return [(page + 1, line) for page, text in enumerate(self.pages) for line in text.split("\n")]


class CandidateContextV1(StrictModel):
    ref: str = Field(min_length=1, max_length=128)
    highest_major: str = ""
    highest_education: str = ""


class JobRequirementV1(StrictModel):
    ref: str = Field(min_length=1, max_length=128)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    entity: str = ""
    public_name: str = ""
    position_name: str = ""
    category: str = ""
    job_family: str = ""
    location: str = ""
    education: str = ""
    required_majors: list[str] = Field(default_factory=list)
    responsibilities: str = ""
    department_ref: str = ""
    department_name: str = ""


class AbilityTagV1(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=100)
    category: Literal["direction", "skill", "experience"]
    description: str = Field(min_length=1, max_length=1000)


class AnalysisScopeV5(StrictModel):
    candidate: CandidateContextV1
    volunteer_ref: str = Field(min_length=1, max_length=128)
    resume_text: ResumeTextV2
    # Exactly one application standard, independent of department demand and HC.
    jobs: list[JobRequirementV1] = Field(min_length=1, max_length=1)
    tag_catalog: list[AbilityTagV1] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def unique_jobs(self):
        if len({job.ref for job in self.jobs}) != len(self.jobs):
            raise ValueError("duplicate job reference")
        if len({tag.code for tag in self.tag_catalog}) != len(self.tag_catalog):
            raise ValueError("duplicate tag code")
        return self


class AnalysisRequestV5(StrictModel):
    protocol_version: Literal[PROTOCOL] = PROTOCOL
    task_kind: Literal["candidate.application_assessment"] = "candidate.application_assessment"
    task_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=256)
    trigger: str = "processing_run"
    workflow_revision: int = Field(ge=0)
    pin: TaskPinV1
    scope: AnalysisScopeV5
    model: ModelConfigV1
    budget: TaskBudgetV1 = Field(default_factory=TaskBudgetV1)


class EvidenceV1(StrictModel):
    quote: str = Field(min_length=8)
    page: int = Field(ge=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class ClaimDetailsV1(StrictModel):
    school_name: str = ""
    degree: str = ""
    major: str = ""
    period: str = ""
    name: str = ""
    role: str = ""


class ClaimV1(StrictModel):
    details: ClaimDetailsV1 = Field(default_factory=ClaimDetailsV1)
    confidence: float = Field(default=0, ge=0, le=1)
    kind: Literal["education", "project", "internship", "skill", "certificate", "major_direction", "agent_experience", "risk"]
    summary: str = Field(min_length=1)
    evidence: list[EvidenceV1] = Field(min_length=1)


class CandidateProfileV1(StrictModel):
    source_text: str = Field(default="", max_length=1000000)
    claims: list[ClaimV1] = Field(min_length=1)
    risks: list[str]
    tags: list["TagAssertionV1"] = Field(default_factory=list, max_length=200)


class TagAssertionV1(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    confidence: float = Field(ge=0, le=1)
    status: Literal["supported", "needs_verification"]
    evidence: list[EvidenceV1] = Field(min_length=1)


class ScoreBreakdown(StrictModel):
    major_match: float = Field(ge=0, le=1)
    skills_match: float = Field(ge=0, le=1)
    experience_evidence: float = Field(ge=0, le=1)
    job_requirement: float = Field(ge=0, le=1)
    resume_quality: float = Field(ge=0, le=1)


class JobMatchV1(StrictModel):
    job_ref: str
    dimensions: ScoreBreakdown
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceV1] = Field(min_length=1)
    risks: list[str]
    reason: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)


class TaskManifestV1(StrictModel):
    reused_from_task_id: str = ""
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    resume_checksum: str
    covered_jobs: list[str]
    tool_versions: dict[str, str]
    warnings: list[str]
    terminal_state: Literal["DONE", "FAILED"]
    failure_code: str = ""
    ocr_pages: int = Field(ge=0)


class TaskToolTraceV1(StrictModel):
    name: str = Field(max_length=200)
    status: str = Field(max_length=64)
    duration_ms: int = Field(ge=0)
    item_count: int = Field(ge=0)
    error_code: str = Field(default="", max_length=64)
    error_field: str = Field(default="", max_length=200)
    repeated: bool = False


class TaskRoundTraceV1(StrictModel):
    turn: int = Field(ge=1, le=64)
    phase: Literal["analysis", "finalize"]
    estimated_input_tokens: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    output_limit: int = Field(ge=0)
    remaining_tokens: int = Field(ge=0)
    reserved_tokens: int = Field(ge=0)
    model_duration_ms: int = Field(ge=0)
    usage_source: Literal["reported", "estimated", "mixed"]
    transport_attempts: int = Field(ge=1, le=6)
    progress: bool = False
    compacted: bool = False


class TaskBudgetTraceV1(StrictModel):
    max_tokens: int = Field(ge=1)
    max_context_tokens: int = Field(ge=1024)
    max_turns: int = Field(ge=1, le=64)
    max_tool_calls: int = Field(ge=1, le=512)
    remaining_tokens: int = Field(ge=0)
    next_input_tokens: int = Field(default=0, ge=0)
    reserved_tokens: int = Field(default=0, ge=0)
    stop_reason: Literal["", "token_limit", "next_request", "context_limit", "turn_limit", "tool_limit", "no_progress", "invalid_output", "materials_incomplete", "model_error", "cancelled", "timeout"] = ""
    tokenizer: str = Field(default="", max_length=64)
    usage_source: Literal["reported", "estimated", "mixed"] = "estimated"
    compactions: int = Field(default=0, ge=0)
    repeated_calls: int = Field(default=0, ge=0)
    format_repairs: int = Field(default=0, ge=0)
    validation_failures: int = Field(default=0, ge=0)
    transport_retries: int = Field(default=0, ge=0)


class TaskSafeTraceV1(StrictModel):
    trace_id: str = ""
    kernel_build: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    turns: int = Field(ge=0, le=64)
    tool_call_count: int = Field(default=0, ge=0, le=512)
    tool_calls: list[TaskToolTraceV1] = Field(default_factory=list)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    status: str = Field(default="", max_length=32)
    budget: Optional[TaskBudgetTraceV1] = None
    rounds: list[TaskRoundTraceV1] = Field(default_factory=list, max_length=64)


class AnalysisResponseV5(StrictModel):
    protocol_version: Literal[PROTOCOL] = PROTOCOL
    task_id: str
    idempotency_key: str
    pin: TaskPinV1
    workflow_revision: int = Field(ge=0)
    profile: Optional[CandidateProfileV1] = None
    matches: list[JobMatchV1] = Field(max_length=1)
    manifest: TaskManifestV1
    safe_trace: TaskSafeTraceV1


# Allocation contains references and verified facts only. No resume or free text.
ALLOCATION_PROTOCOL = "resume-allocation/v1"
ALLOCATION_RESULT = "resume-allocation-plan/v1"
AllocationRef = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")]
AllocationHash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
AllocationNumber = Annotated[int, Field(ge=0, le=9007199254740991)]
AllocationTime = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z$")]


class AllocationPin(StrictModel):
    pin_id: AllocationRef
    kernel_build: AllocationRef
    protocol_version: Literal[ALLOCATION_PROTOCOL] = ALLOCATION_PROTOCOL
    result_schema_version: Literal[ALLOCATION_RESULT] = ALLOCATION_RESULT
    toolset_version: AllocationRef
    policy_version: Literal["allocation-order/v1"] = "allocation-order/v1"
    instruction_version: Literal["allocation-deterministic/v1"] = "allocation-deterministic/v1"


class AllocationCapabilities(StrictModel):
    protocol_version: Literal[ALLOCATION_PROTOCOL] = ALLOCATION_PROTOCOL
    result_schema_version: Literal[ALLOCATION_RESULT] = ALLOCATION_RESULT
    task_kinds: list[Literal["pool.candidate_allocation"]]
    execution_modes: list[Literal["deterministic"]]
    kernel_build: AllocationRef
    toolset_version: AllocationRef
    policy_version: Literal["allocation-order/v1"] = "allocation-order/v1"
    instruction_version: Literal["allocation-deterministic/v1"] = "allocation-deterministic/v1"
    tool_names: list[AllocationRef] = Field(min_length=6, max_length=6)
    mock: bool = False


class AllocationTag(StrictModel):
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    status: Literal["supported", "needs_verification"]
    confidence_bps: int = Field(ge=0, le=10000)
    source: Literal["model", "manual"]
    assertion_ref: AllocationRef
    verified: Literal[True]


class AllocationMember(StrictModel):
    member_id: AllocationNumber
    candidate_ref: AllocationRef
    application_ref: AllocationRef
    qualification_ref: AllocationRef
    qualification_revision: AllocationNumber
    member_revision: AllocationNumber
    workflow_revision: AllocationNumber
    source_revision: AllocationNumber
    standard_ref: AllocationRef
    standard_hash: AllocationHash
    tags_hash: AllocationHash
    admitted: Literal[True]
    created_at: AllocationTime
    tags: list[AllocationTag] = Field(max_length=200)
    allowed_demand_ids: list[AllocationNumber] = Field(max_length=200)
    counted_demand_ids: list[AllocationNumber] = Field(max_length=200)


class AllocationDemand(StrictModel):
    demand_id: AllocationNumber
    department_ref: AllocationRef
    revision: AllocationNumber
    reception_state: Literal["receiving", "paused", "closed"]
    required_tags: list[AllocationRef] = Field(max_length=200)
    preferred_tags: list[AllocationRef] = Field(max_length=200)
    priority: int = Field(ge=0, le=999)
    recent_supply_count: AllocationNumber
    last_allocation_sequence: AllocationNumber


class AllocationSnapshot(StrictModel):
    snapshot_id: AllocationRef
    snapshot_at: AllocationTime
    scope_ref: AllocationRef
    entity_ref: AllocationRef
    pool_ref: AllocationRef
    scope_revision: AllocationNumber
    policy_revision: AllocationNumber
    epoch: AllocationNumber
    next_sequence: AllocationNumber
    window_seconds: Literal[604800] = 604800
    members: list[AllocationMember] = Field(min_length=1, max_length=100)
    demands: list[AllocationDemand] = Field(max_length=200)

    @model_validator(mode="after")
    def unique_references(self):
        datetime.fromisoformat(self.snapshot_at.replace('Z','+00:00'))
        for member in self.members:
            datetime.fromisoformat(member.created_at.replace('Z','+00:00'))
            if member.tags_hash != allocation_tags_hash([tag.model_dump() for tag in member.tags]):
                raise ValueError('allocation tag version hash mismatch')
        for items in ([m.member_id for m in self.members], [m.candidate_ref for m in self.members],
                      [d.demand_id for d in self.demands]):
            if len(set(items)) != len(items):
                raise ValueError("duplicate allocation reference")
        demand_ids = {d.demand_id for d in self.demands}
        for m in self.members:
            if len(set(m.allowed_demand_ids)) != len(m.allowed_demand_ids) or not set(m.allowed_demand_ids) <= demand_ids:
                raise ValueError("invalid allowed demand references")
            if len(set(m.counted_demand_ids)) != len(m.counted_demand_ids) or not set(m.counted_demand_ids) <= demand_ids:
                raise ValueError("invalid counted demand references")
            if len({t.code for t in m.tags}) != len(m.tags):
                raise ValueError("duplicate tag assertion")
        for d in self.demands:
            if any(len(set(tags)) != len(tags) for tags in (d.required_tags, d.preferred_tags)):
                raise ValueError("duplicate demand tag")
        return self


class AllocationBudget(StrictModel):
    max_duration_seconds: int = Field(default=30, ge=1, le=30)
    max_tool_calls: int = Field(default=16, ge=1, le=16)


class AllocationRequest(StrictModel):
    protocol_version: Literal[ALLOCATION_PROTOCOL] = ALLOCATION_PROTOCOL
    task_kind: Literal["pool.candidate_allocation"] = "pool.candidate_allocation"
    execution_mode: Literal["deterministic"] = "deterministic"
    task_id: AllocationRef
    idempotency_key: AllocationRef
    pin: AllocationPin
    snapshot_hash: AllocationHash
    snapshot: AllocationSnapshot
    budget: AllocationBudget = Field(default_factory=AllocationBudget)


class AllocationDecision(StrictModel):
    member_id: AllocationNumber
    qualification_ref: AllocationRef
    action: Literal["assign", "wait"]
    demand_id: AllocationNumber
    department_ref: str = Field(pattern=r"^([A-Za-z0-9][A-Za-z0-9_.:/-]{0,127})?$")
    matched_tags: list[AllocationRef] = Field(max_length=200)
    assertion_refs: list[AllocationRef] = Field(max_length=200)
    # [-preferred hits, priority, recent+provisional, last sequence, demand ID]
    order: list[int] = Field(max_length=5)
    sequence: AllocationNumber
    reason_code: Literal["allocated", "no_active_mapping", "no_receiving_demand", "required_tags_unavailable"]


class AllocationTrace(StrictModel):
    tool_names: list[AllocationRef] = Field(max_length=16)
    tool_call_count: int = Field(ge=0, le=16)
    duration_ms: AllocationNumber
    reused: bool


class AllocationResponse(StrictModel):
    protocol_version: Literal[ALLOCATION_PROTOCOL] = ALLOCATION_PROTOCOL
    result_schema_version: Literal[ALLOCATION_RESULT] = ALLOCATION_RESULT
    task_id: AllocationRef
    idempotency_key: AllocationRef
    pin: AllocationPin
    snapshot_hash: AllocationHash
    terminal_state: Literal["DONE"] = "DONE"
    decisions: list[AllocationDecision] = Field(min_length=1, max_length=100)
    safe_trace: AllocationTrace


def allocation_tags_hash(tags):
    raw=json.dumps(sorted(tags,key=lambda tag:tag['code']),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()
