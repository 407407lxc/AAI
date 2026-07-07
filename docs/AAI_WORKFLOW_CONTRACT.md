# AAI Workflow Contract

This document translates the user-designed AAI workflow diagram into an initial executable contract.

## Design rule

The external workflow is owned by AAI and may be manually authored.

LoongFlow is allowed to run inside a phase, but it must not own the global workflow state.

```text
AAI controls:
- phase transitions
- artifact contracts
- archive decisions
- memory updates
- safety gates
- Mode 3 harness-change approvals

LoongFlow controls:
- phase-local planning
- phase-local execution
- phase-local evaluation
- phase-local summarization
- phase-local trace/checkpoint generation
```

## Diagram-derived phases

### Phase -1: requirement parsing / feasibility check

Source nodes:

```text
用户需求
需求解析：明确模型、目标运行时、硬件、指标、质量门槛、依赖和凭据策略
是否已有可运行部署和基线？
```

Contract outputs:

```text
requirements.json
credential_policy.json
feasibility.json
```

### Mode 0: bootstrap / deployment / first baseline

Source nodes:

```text
模式 0 子环境：启动构建
识别缺失部分：模型、环境、服务、适配器、评测、基线
创建安装脚本、启动脚本、健康检查和评测适配器
运行健康检查
运行启动基线评测：bootstrap-baseline
基线是否有效？
```

Contract outputs:

```text
gap_report.json
bootstrap_manifest.json
health_check.json
baseline_result.json
```

### Phase 1: bounded child optimization

Source nodes:

```text
阶段 1 子环境：优化一次明确目标
读取 traces、评测用例、历史经验、solution
形成优化假设
修改受限范围：solution 或安全配置
运行带标签的评测
质量、schema、安全、错误率门槛是否通过？
输出证据包：ITERATIONS、trajectory、result、diff、logs
拒绝或修正；记录失败路径
```

Contract outputs:

```text
child_runtime_spec.json
hypothesis.md
iterations.jsonl
trajectory.json
result.json
diff.patch
logs/
audit_findings.json
```

### Phase 2: Master Campaign scheduling and archive

Source nodes:

```text
master 读取 reference archive：baseline、variants、traps、failed transcripts
选择 parent：seed 或已归档 variant
确定本轮搜索方向：写窄 prompt，避免一次优化所有问题
spawn child 并运行 worker agent
读取 child 证据：ITERATIONS、trajectory result、diff、stdout、audit findings、logs
预归档检查：无评测泄漏、无硬编码答案、无 baseline 修改、无隐藏评分修改、gates 通过
通过且有价值？
归档新 variant：solution、config、result、summary、parent
归档 failed 或 no-archive：保留原因、日志和失败 transcript
更新长期记忆：README、TRAPS、harness-ledger
选择下一轮 parent 和搜索方向，或停止 campaign
```

Contract outputs:

```text
reference_archive.json
parent_selection.json
round_prompt.md
child_evidence_manifest.json
prearchive_check.json
variant_manifest.json
failed_manifest.json
memory_update.json
harness-ledger.md
TRAPS.md
```

### Mode 3: harness-change proposal

Source nodes:

```text
Mode 3：是否有证据需要修改 harness
worker 写 PROPOSALS.md：只描述有证据的 harness 或工具缺口
master 审核 proposal：拒绝冻结范围、泛化知识和无证据修改
```

Contract outputs:

```text
PROPOSALS.md
proposal_review.json
accepted_proposal.json
proposal_diff.patch
```

## Runtime boundary

Runtime backends may write phase-local evidence. They may not directly advance global AAI workflow state.

A runtime is forbidden to directly modify:

```text
.aai/archive/
.aai/memory/
workflow definitions
evaluator definitions
scoring definitions
gate definitions
Mode 3 review records
```

unless a Mode 3 proposal has been accepted.

## Initial transition graph

See `aai_harness.workflow.DEFAULT_TRANSITIONS` for the executable version of this contract.
