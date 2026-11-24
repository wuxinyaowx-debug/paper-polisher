# 限定强度分级词表（Hedge Scale）

限定强度守恒是本 Skill 的核心红线：润色不得把弱表述改强，也不得无故把强表述改弱。本表为阶段 2 编辑与 `scripts/check_polish.py` 校验的共同依据。

## 1. 分级原则

按论断对事实的承诺程度分为五级（5 最强，1 最弱）：

| 级别 | 语义 | 英文典型词 | 中文典型词 |
|-|-|-|-|
| 5 | 断言已确证 | prove, demonstrate, confirm, establish, show conclusively, undoubtedly | 证明、证实、确证、无疑、必然 |
| 4 | 证据支持的明确表述 | show, indicate, reveal, find, clear evidence | 表明、显示、明确显示 |
| 3 | 推论性表述 | suggest, imply, argue, propose, support, consistent with | 提示、表明（初步）、支持、暗示、与…一致 |
| 2 | 可能性表述 | may, might, could, possibly, potentially, appear, seem, likely | 可能、或许、似乎、有望、倾向于 |
| 1 | 极弱推测或条件 | perhaps, conceivably, cannot rule out, 尚待、初步、可能（弱） | 或许、不能排除、尚待验证、初步提示 |

## 2. 守恒规则

1. 润色后同一句的限定词级别**不得高于原文**（防止偷偷加强结论）。
2. 润色后同一句的限定词级别**不得无故低于原文**；若因语法修正必须改写句式，应保留同级限定词或标记 `待确认`。
3. 同级别内的同义替换（show → indicate；表明 → 显示）允许，需在 edit_log 注明 `KEEP_STRENGTH`。
4. 原文无明确限定词时，按上下文证据强度判定默认级别（结果描述默认 4；推论默认 3），改写后不得超出该默认级别。
5. 以下情况需在 edit_log 中显式标注，并列入 `uncertainty`：
   - 原文限定词与证据强度明显不匹配（如相关性数据写 "prove"）；
   - 同一段落内限定强度前后不一致；
   - 无法判定应属级别。

## 3. 脚本校验逻辑（实现约定）

`check_polish.py` 对每个句子提取命中的最高级别限定词，逐句比较原文与改文：

- 改文最高级别 > 原文 → 硬违规（exit 1）；
- 改文最高级别 < 原文且无 `KEEP_STRENGTH` 或 `待确认` 标注 → 软警告（exit 0，report 中列出）；
- 全文级别的强度分布偏移（强词总数显著增加）也列入报告。

## 4. 常见误判提示

- "show" 在方法描述中（"The figure shows…"）不属于论断限定词，不参与强度比较；
- 否定句中的限定词（"did not show"）按否定范围处理，不视为强度 4；
- 条件句（"if…, would demonstrate…"）按条件成立后的强度计，但需保留条件结构，删除条件即视为加强。
- 复合限定语（"初步表明""初步提示"）按其所含最高级词计级（保守方向），改写时以保留原复合结构为首选。
- 本表与 `scripts/check_polish.py` 中的 `HEDGE_LEXICON` 一一对应；维护时两处必须同步修改。
