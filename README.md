# Resume Contracts

业务平台和简历分析引擎之间的公开契约，版本 1.0.0。

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
make check PYTHON=.venv/bin/python
```

权威定义为 `resume_contracts/models.py`，机械生成的 JSON Schema、合成输入输出和摘要在 `resume_contracts/bundle/`。
协议为 `resume-analysis/v1`，HTTP 入口为 `POST /v2/tasks/execute`。请求只携带已准入范围，不携带历史志愿、学校规则或 HC；结果不包含业务动作。

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

## 发布

私有仓：`https://github.com/huyue0228/resume-contracts`。PR 必须通过独立契约检查；协议变更由平台和 Kernel 双方评审，当前负责人为 `@huyue0228`。
手动执行 Release 工作流只构建演练产物。维护者在 main 已合并提交上推送与包版本完全一致的 `vX.Y.Z` 标签，才自动发布 GitHub Release（wheel、sdist、SHA256SUMS）；不发布到 PyPI，不覆盖旧版本。发布测试还会在隔离环境安装 wheel，验证 Schema 与模拟服务可用。
消费者升级通过 PR 同步固定版本；不自动覆盖两个仓的文件，也不需要跨仓 Actions 写令牌。
