# Resume Contracts

业务平台和简历分析引擎之间的公开契约，版本 4.0.0。

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
make check PYTHON=.venv/bin/python
```

权威定义为 `resume_contracts/models.py`，机械生成的 JSON Schema、合成输入输出和摘要在 `resume_contracts/bundle/`。
协议为 `resume-analysis/v4`，HTTP 入口为 `POST /v2/tasks/execute`。请求只携带已准入范围，不携带历史志愿、学校规则或 HC；结果不包含业务动作。

维护者修改模型后先升级版本，再运行：

```sh
make bundle PYTHON=.venv/bin/python
.venv/bin/python tools/build_bundle.py --platform ../resume-platform --kernel ../resume-agent-kernel
.venv/bin/python tools/build_bundle.py --check --platform ../resume-platform --kernel ../resume-agent-kernel
```

同步是维护者的发布操作，不是消费者构建步骤。两个消费者仓库自身包含固定副本，单独检出即可验证。发布后不得覆盖同一版本；Schema 与消费者行为都要通过测试。

## 模拟服务

```sh
.venv/bin/python -m resume_contracts.mock_server --port 8091 --token local-contract-mock
```

支持 `--scenario success|low_match|failed|budget_exhausted|timeout|invalid_reference|incomplete|invalid_schema`。
所有结果标记 `MOCK_ONLY`，只用于脱敏开发环境；没有真实匹配含义。服务不读取文件、不访问模型或数据库。请求格式验证不等于语义验收：覆盖不足和引用越界必须由平台拒绝。

## 版本边界

认证的 `GET /v2/capabilities` 描述 Kernel 的公开协议、任务种类、build、工具集和指令版本。
协议仓只固定公开协议、结果结构与评分语义；内部版本为非空不透明引用，不使用枚举。
平台发现后冻结 pin；Kernel 必须拒绝与实际 build/工具/指令不符的执行请求（409），而非静默升级任务。
平台独立拥有 policy_version。内部工具/指令更新无需同步协议仓；公开结构或评分语义变化才走双方验收。

## 发布

先安装 `build setuptools>=68 wheel`，再执行 `make check package RELEASE_VERSION=v4.0.0`。
仓库脚本生成 wheel/sdist、SHA256SUMS，并在仓库外的临时环境离线安装 wheel 验证。
产物在 `dist/v4.0.0/`，拒绝覆盖已有目录。构建依赖由运行环境预置，脚本不下载它们。
GitLab 与 GitHub 都只调用这些入口；内网通过 pip 镜像源供应依赖即可。

消费者升级通过合并请求同步固定副本；普通消费者构建不检出协议仓、不自动覆盖兄弟仓。
公开协议升级先发布本仓，再升级两个消费者并验收选定的版本组合；不兼容旧 AI 任务。

文本输入使用原文件 SHA256、文本 SHA256、提取器版本、按页完整文本、提取状态与质量提示。页内仅使用 LF；页间按 FF 拼接计算文本校验值，空白页保留一个空行，行号跨页连续。全文上限 1 MiB，HTTP 请求包含岗位和 JSON 编码后上限 2 MiB；不支持旧签名 PDF 输入。

`--platform` 和 `--kernel` 分发 Go 消费者的 `internal/contract/bundle` 及生成的 `internal/contract/allocation_types.go`，不再生成旧 Django 后端目录。Python DTO 和模拟服务仅由本协议仓发行。Git 标签记录版本；GitHub 分发物回下载校验后不保留本地 release 或源码备份。

v4 任务 `candidate.application_assessment` 每次只携带一个当前投递评估标准（`scope.jobs` 长度恰好为 1），结果 `resume-application-assessment/v1` 最多含一个契合度结果。`scope.tag_catalog` 是受控标签字典，`profile.tags` 含 code、confidence、status 和必填原文 evidence；标签所属范围和原文语义校验由 Kernel 与平台共同执行。保留 `ResumeTextV2` 正文格式和既有评分权重，入池、复核和分配不进入模型输出。v4 删除 `scope.taxonomy`，旧版本请求不再受支持。


4.0.0 保留独立分配协议 `resume-allocation/v1`（任务 `pool.candidate_allocation`），结果 `resume-allocation-plan/v1`。筛选协议升级为 v4，不保留专业大类词表。模拟服务也提供 `/v2/allocation/capabilities` 和 `/v2/allocation/tasks/execute`。

分配 DTO 仅含受控资格、标签、版本引用、允许需求、接收状态和供给事实；禁止自由文本、原文、摘录、文件地址、HC 数量和公开状态。`counted_demand_ids` 是当前候选人在近 7 天已被计入供给的需求，用于批内去重。集合字段规范排序后按 UTF-8 紧凑 JSON（键排序）计算 SHA-256；`tags_hash` 使用同一规范的标签数组。时间统一 UTC，最多 6 位小数。包内含跨语言 hash 向量、17 个明确预期结果的分配案例及机械生成 Go DTO，不在消费者手工维护协议副本。
