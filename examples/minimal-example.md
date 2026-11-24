# 最小调用示例（示意，非正式案例结果）

> 本目录全部内容为**接口与流程示意**，用于说明输入、调用方式与输出格式，不构成平台正式测试案例的答案。

## 1. 输入

- 英文示例：`original.txt`（含语法错误、过度断言、术语变体与中式英语的英文稿件片段）＋ `terms.tsv`；
- 中文示例：`original_zh.txt`（含口语化与过度断言的中文稿件片段）＋ `terms_zh.tsv`；
- 任务口径：期刊论文语域，保持限定强度与全部数据、引用、图表指向。

中文示例的调用方式相同（`--orig original_zh.txt --new polished_zh.txt --terms terms_zh.tsv`）。其校验输出含两条软警告，均为预期行为：

1. `HEDGE_WEAKENED`（证明→表明）：与英文示例句号 1 同类，属强度调整，须标注【待确认】；
2. `TERM_VARIANT_USED`（deep learning）：术语表按 `FULL_FIRST` 规则要求首次出现写出英文全称，"可接受变体"在首次出现处属允许用法，第二次及以后出现才构成漂移——脚本逐次出现不计语境，此类提示由人工按 `term-table-format.md` §3 复核销记。

## 2. 调用方式

Agent 加载本 Skill 后，按 `SKILL.md` §3 五阶段执行：

1. 文体判定：期刊论文；
2. 加载 `terms.tsv`，记录 `deep learning` 的规范写法与禁用写法；
3. 分句最小编辑，产出 `polished.txt`；
4. 运行守恒校验：

```bash
python scripts/check_polish.py --orig examples/original.txt \
    --new examples/polished.txt --terms examples/terms.tsv \
    --out verification_report.json
```

5. 写出润色文本、逐句修改说明与 `result.json`。

## 3. 示意输出

### 3.1 逐句修改说明（edit_log 节选）

| 句号 | 原文 | 改文 | 类型 | 理由 | 核验 |
|-|-|-|-|-|-|
| 1 | Our results proves that the new catalyst is very good and it can completely solve the stability problem. | Our results indicate that the new catalyst achieves high activity and markedly improved stability. | GRAMMAR; REGISTER | 主谓一致（proves→indicate 同时消除 very good / completely solve 的绝对化表述）；**限定强度由 5 级降为 4 级，属强度调整，标记【待确认：材料仅支持改善稳定性，是否接受降级表述】** | 脚本软警告 HEDGE_WEAKENED，已按规则列入 uncertainty |
| 2 | The catalyst show a activity of 12.5 mA/cm2 at 1.8 V, which is much better than reported works [3, 7]. | The catalyst shows an activity of 12.5 mA/cm2 at 1.8 V, exceeding that of previously reported works [3, 7]. | GRAMMAR; REGISTER | 主谓一致、冠词（a→an）；much better → exceeding（消除口语化程度表述）；数据 12.5 mA/cm2、1.8 V 与引用 [3, 7] 原样保留 | 脚本通过 |
| 3 | As shown in Figure 2, the material keep stable for 100 h. | As shown in Figure 2, the material remains stable for 100 h. | GRAMMAR | 主谓一致；Figure 2 与 100 h 原样保留 | 脚本通过 |
| 4 | These findings suggest that deep-learning models may accelerate catalyst discovery, and this is very important. | These findings suggest that deep learning models may accelerate catalyst discovery. | TERM; REGISTER | deep-learning → deep learning（术语表规范写法）；删除无依据评价 this is very important；suggest / may 限定强度原样保留（KEEP_STRENGTH） | 脚本通过 |

### 3.2 校验报告摘要（脚本实际运行输出，状态为示意运行结果）

```text
status=pass  hard=0  soft=1
SOFT HEDGE_WEAKENED: orig_max_level=5, new_max_level=4
```

说明：该软警告来自句号 1 的强度降级，已按 `references/hedge-scale.md` §2 在 edit_log 与 `uncertainty` 中显式标注，属可交付状态（exit 0）。若脚本报硬违规（exit 1），必须返回修正后重新校验。

脚本同时校验 LaTeX 输入：`\cite{}` 键名与 `\ref{}`/`\eqref{}` 标签的多重集在润色前后必须一致，键名或标签被增删即报硬违规；数学环境内的数字（如 `$12.5~\mathrm{mA/cm^2}$`）同样纳入数字守恒比对。

### 3.3 result.json（示意）

```json
{
  "case_id": "example-local-001",
  "status": "success",
  "polished_text": "polished.txt",
  "edit_log": "edit_log.md",
  "term_table": "terms.tsv",
  "verification_report": "verification_report.json",
  "sources": ["examples/original.txt", "examples/terms.tsv"],
  "uncertainty": ["句号 1：限定强度由 prove 级降为 indicate 级，需作者确认（原文存在过度断言）"],
  "changes": {"sentences_total": 4, "edited": 4, "kept": 0,
              "by_type": {"GRAMMAR": 3, "REGISTER": 3, "TERM": 1}}
}
```
