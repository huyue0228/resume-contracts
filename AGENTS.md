# Resume Contracts

- 仅放公开数据协议、错误语义、合成样例、模拟服务和兼容性测试。
- 不依赖 Django、数据库、业务模型或 Agent 实现；不放真实简历或密钥。
- 权威来源是 `resume_contracts/models.py`；执行 `make bundle` 生成分发物，`make check` 验证。
- 平台和内核都消费固定版本快照，不使用运行时相对路径引用兄弟仓库。
- 不兼容变更必须显式升级协议版本；评分语义变更也必须经过双方验收。
- 不自动 stage、commit、push 或创建远端仓库。
