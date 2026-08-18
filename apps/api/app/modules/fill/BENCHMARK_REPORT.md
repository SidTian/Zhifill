# Qwen vs DeepSeek 实验对比报告

> 实验时间: 2026-08-14 13:23:28
> 测试场景: ZhiFill 2.2 Agent 填表（5 字段 × 3 轮）
> 模型: Qwen-Plus vs DeepSeek-V3
>
> ⚠️ **勘误（2026-08-18）**：DeepSeek 列中所有 `0ms / 0 token` **并非真实性能数据**，而是 15 次调用全部返回 `HTTP 402（余额不足/付费限制）` 后，被旧版统计逻辑 `if not c.error` 全量过滤导致的显示缺陷。详见本报告「六、已知问题与勘误」。

---

## 一、汇总对比

| 维度 | Qwen-Plus | DeepSeek-V3 | 优势方 |
|------|-----------|-------------|--------|
| 准确率 | 20% (1/5) | 0% (0/5) | Qwen |
| 平均延迟 | 2177ms | ⚠️ N/A（全量 402 报错） | - |
| Prompt Tokens | 181 | ⚠️ N/A（无 usage 返回） | - |
| Completion Tokens | 5 | ⚠️ N/A（无 usage 返回） | - |
| 总 Token | 186 | ⚠️ N/A（无 usage 返回） | - |
| 错误次数 / 总调用 | 0 / 15 | **15 / 15（100% 失败）** | Qwen |

## 二、逐字段对比（第 1 轮）

| 字段 | 类型 | 期望值 | Qwen 输出 | Qwen 正确 | DeepSeek 输出 | DeepSeek 正确 |
|------|------|--------|-----------|-----------|---------------|--------------|
| 姓名 | text | 张伟 | *(未展示)* | ❌ | 402 付费错误 | ❌ |
| 入职日期 | date | 2015-07-01 | *(未展示)* | ❌ | 402 付费错误 | ❌ |
| 年龄 | number | 34 | *(未展示)* | ❌ | 402 付费错误 | ❌ |
| 性别 | single_choice | 男 | *(未展示)* | ❌ | 402 付费错误 | ❌ |
| 技能 | multi | Python,Go,Rust | Python, Go, Rust | ✅ | 402 付费错误 | ❌ |

> 注：原报告仅展示了"技能"1 个字段，此处补全所有 5 个字段的结果状态。Qwen 准确率 20% = 1/5。

## 三、延迟详情（3 轮平均）

| 字段 | Qwen 延迟(ms) | DeepSeek 延迟(ms) |
|------|--------------|-------------------|
| 技能 | 2661 | ⚠️ 被过滤（调用报错） |
| 其余4字段 | *(未展示)* | ⚠️ 被过滤（调用报错） |
| **平均** | **2177** | **⚠️ N/A（15 次全失败，旧版统计误显 0ms）** |

## 四、结论

| 维度 | Qwen 得分 | DeepSeek 得分 |
|------|----------|--------------|
| 准确率 | 1 | 0 |
| 延迟 | 1 | ⚠️ 不适用（全失败） |
| Token 效率 | 1 | ⚠️ 不适用（全失败） |
| **可用性** | **✅ 通过** | **❌ 100% 失败** |

**原始结论已作废**：原结论"两者接近"基于错误的统计结果（误将 DeepSeek 视为 0ms/0token 而给分）。实际 DeepSeek 在本次实验中 **15/15 调用全部失败（HTTP 402），无法评估性能与 Token。建议排查 DeepSeek API Key 余额或付费套餐后重新跑 benchmark。**

## 五、测试数据

### 证据片段（知识库）
1. 张伟，男，1990年5月12日出生。2015年7月入职阿里巴巴，担任高级算法工程师。
2. 2020年3月跳槽到字节跳动，任算法专家。持有P7职级。年龄34岁。
3. 张伟在字节跳动负责推荐系统，2023年晋升为算法总监。技能：Python, Go, Rust。

### 字段定义
| 字段 | 类型 | 期望值 |
|------|------|--------|
| 姓名 | text | 张伟 |
| 入职日期 | date | 2015-07-01 |
| 年龄 | number | 34 |
| 性别 | single_choice | 男 |
| 技能 | multi | Python,Go,Rust |

---

## 六、已知问题与勘误（2026-08-18）

### 6.1 问题现象
原始报告中 DeepSeek-V3 的「平均延迟」「Prompt Tokens」「Completion Tokens」全部显示为 `0`，并因此错误地在「延迟/Token效率」维度判给 DeepSeek 优势。

### 6.2 根因分析（双层原因）
| 层级 | 代码位置 | 问题描述 |
|------|---------|---------|
| L1 采集层 | [benchmark_llm.py#L126-L128](file:///d:/Users/Yoga/Documents/GitHub/Zhifill/apps/api/app/modules/fill/benchmark_llm.py#L126-L128) | API 调用异常时，仅 `latency_ms` 被正确采集，`prompt_tokens` / `completion_tokens` 被硬编码为 `0`（402 错误响应不包含 `usage` 字段——此为合理行为） |
| L2 统计层 ⚠️ **Bug** | [benchmark_llm.py#L213-L222 修复前](file:///d:/Users/Yoga/Documents/GitHub/Zhifill/apps/api/app/modules/fill/benchmark_llm.py#L212) | 统计指标时使用 `if not c.error` 过滤所有报错调用 → 当 15/15 调用全失败时，`latencies = []` 空列表，`statistics.mean([]) if [] else 0` 退化为 `0ms`；Token 也同理被算成 `0` |

### 6.3 调用链还原
```
DeepSeek 15 次请求（5字段×3轮）
  → 全部返回 HTTP 402 {"error": {"code": "billing_failed", ...}}
  → CallLog.error = "Error code: 402 - {'err..."
  → 统计层 latencies = [c.latency_ms for c in mr.calls if not c.error] = []
  → avg_latency_ms = 0, total_prompt_tokens = 0, total_completion_tokens = 0
  → 报告误显 "0ms / 0 tokens" ❌
```

### 6.4 修复方案（已应用）
**benchmark_llm.py 统计逻辑修复**：
```python
# 修复前 ❌：只统计成功调用，全失败时出现"幽灵0值"
latencies = [c.latency_ms for c in mr.calls if not c.error]
avg = statistics.mean(latencies) if latencies else 0
tokens = sum(c.prompt_tokens for c in mr.calls if not c.error)

# 修复后 ✅：优先成功调用，全失败退化为全量（含报错）；Token不再过滤
ok_latencies = [c.latency_ms for c in mr.calls if not c.error]
all_latencies = [c.latency_ms for c in mr.calls]
use_latencies = ok_latencies if ok_latencies else all_latencies
avg = statistics.mean(use_latencies) if use_latencies else 0
tokens = sum(c.prompt_tokens for c in mr.calls)  # 全量，不过滤
```

### 6.5 遗留说明
- 由于 `benchmark_log.json` 原始日志已清理，**无法回溯本次 DeepSeek 15 次 402 错误的真实响应延迟**。预计 HTTP 402 响应通常在 100–500ms 区间（仅作参考，不作为对比依据）。
- **原始结论「两者接近」已作废**，应改为「DeepSeek 本次实验不可用（100% 失败），建议充值 API Key 后重跑 benchmark 再做评估」。
