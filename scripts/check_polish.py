#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
check_polish.py — 学术润色守恒校验脚本（仅依赖 Python 3 标准库）

核验润色前后文本在以下维度保持一致：
  1. 数字与单位（多重集比对）
  2. 引用编号 [n] 与图表指向（Figure/Table/图/表 n）
  3. LaTeX 引用键 \cite{} 与图表标签 \ref{}/\eqref{}（多重集比对）
  4. 限定强度（按 references/hedge-scale.md 五级词表，逐句与全文比对）
  5. 句数漂移
  6. 术语表规范（可选 --terms，禁用写法为硬违规）

用法：
  python check_polish.py --orig ORIG.txt --new NEW.txt [--terms TERMS.tsv] --out REPORT.json

退出码：0 = 通过或仅有软警告；1 = 存在硬违规；2 = 运行错误。
报告同时写入 --out 指定路径（JSON）与标准输出（摘要）。
"""

import argparse
import json
import re
import sys
from collections import Counter

# ---------------------------------------------------------------- 词表（与 references/hedge-scale.md 一致）

HEDGE_LEXICON = {
    5: ["prove", "proves", "proved", "proven", "demonstrate", "demonstrates", "demonstrated",
        "confirm", "confirms", "confirmed", "establish", "establishes", "established",
        "undoubtedly", "conclusively",
        "证明", "证实", "确证", "无疑", "必然"],
    4: ["show", "shows", "showed", "shown", "indicate", "indicates", "indicated",
        "reveal", "reveals", "revealed", "find", "finds", "found",
        "表明", "显示", "明确显示"],
    3: ["suggest", "suggests", "suggested", "imply", "implies", "implied",
        "argue", "argues", "argued", "propose", "proposes", "proposed",
        "support", "supports", "supported", "consistent with",
        "提示", "暗示", "支持", "与…一致", "与...一致"],
    2: ["may", "might", "could", "possibly", "potentially", "appear", "appears",
        "appeared", "seem", "seems", "seemed", "likely",
        "可能", "或许", "似乎", "有望", "倾向于"],
    1: ["perhaps", "conceivably", "cannot rule out", "can not rule out",
        "不能排除", "尚待", "初步提示"],
}

# 方法描述语境中的 show/indicate 不计入论断强度
NONCLAIM_CONTEXT = re.compile(
    r"(figure|fig\.?|table|scheme|chart|图|表)\s*\d+", re.IGNORECASE)

# ---------------------------------------------------------------- 基础工具


def read_text(path):
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as fh:
                return fh.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise RuntimeError(f"无法解码文件：{path}")


def split_sentences(text):
    """中英混合分句：按句末标点切分，保留非空句。"""
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=[.])\s+(?=[A-Z0-9\"“])", text)
    return [p.strip() for p in parts if p and p.strip()]


NUM_RE = re.compile(
    r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:%|‰|°C|°F|K|eV|keV|MeV|GeV|e?V|mM|uM|µM|nM|M|mol/?L|mg/?mL|g/?L|kDa|Da|bp|nm|µm|um|mm|cm|mL|µL|uL|L|h|min|s|ms|V|mV|A|mA|W|kW|Hz|kHz|MHz|GHz|GPa|MPa|Pa|bar|atm|rpm|cfu|IU|ppm|ppb|×10\^\d+|\*\d+))?")

CITE_RE = re.compile(r"\[(\d+(?:\s*[-,–]\s*\d+)*)\]")
FIGTAB_RE = re.compile(
    r"(figure|fig\.?|table|scheme|图|表)\s*([0-9]+[a-zA-Z]?)", re.IGNORECASE)
LATEXCITE_RE = re.compile(r"\\cite[a-z*]*\{([^}]*)\}")
LATEXREF_RE = re.compile(r"\\(?:eq)?ref\{([^}]*)\}")


def norm_number(tok):
    return re.sub(r"\s+", "", tok.strip()).rstrip(".,;")


def extract_numbers(text):
    return Counter(norm_number(m.group(0)) for m in NUM_RE.finditer(text)
                   if norm_number(m.group(0)))


def extract_citations(text):
    out = []
    for m in CITE_RE.finditer(text):
        for part in re.split(r"[,，]", m.group(1)):
            out.append(re.sub(r"\s+", "", part))
    return Counter(out)


def extract_figtab(text):
    return Counter((m.group(1).lower().rstrip("."), m.group(2).lower())
                   for m in FIGTAB_RE.finditer(text))


def hedge_level(sentence):
    """返回句中命中的最高限定级别与命中词；图表描述语境的 show 类词除外。"""
    best, hits = 0, []
    low = sentence.lower()
    for level, words in HEDGE_LEXICON.items():
        for w in words:
            if w.isascii():
                pattern = r"\b" + re.escape(w) + r"\b"
                found = re.search(pattern, low)
            else:
                found = re.search(re.escape(w), sentence)
            if found:
                if level == 4 and w.startswith(("show", "indicate")) and NONCLAIM_CONTEXT.search(sentence):
                    continue
                hits.append((level, w))
                best = max(best, level)
    return best, hits


def counter_diff(a, b):
    """返回 (a 有而 b 缺, b 有而 a 缺) 的元素列表。"""
    missing = list((a - b).elements())
    added = list((b - a).elements())
    return missing, added


# ---------------------------------------------------------------- 术语表

def load_terms(path):
    terms = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split("\t")
            while len(cols) < 5:
                cols.append("")
            canonical, variants, banned, first_req, note = cols[:5]
            terms.append({
                "line": ln,
                "canonical": canonical.strip(),
                "variants": [v.strip() for v in variants.split(",") if v.strip()],
                "banned": [b.strip() for b in banned.split(",") if b.strip()],
                "first": first_req.strip(),
                "note": note.strip(),
            })
    return terms


def check_terms(terms, text):
    banned_hits, variant_hits = [], []
    for t in terms:
        for b in t["banned"]:
            if b and b in text:
                banned_hits.append({"term": t["canonical"], "banned": b,
                                    "count": text.count(b), "line": t["line"]})
        for v in t["variants"]:
            if v and v in text:
                variant_hits.append({"term": t["canonical"], "variant": v,
                                     "count": text.count(v), "line": t["line"]})
    return banned_hits, variant_hits


# ---------------------------------------------------------------- 主流程

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="学术润色守恒校验")
    ap.add_argument("--orig", required=True, help="原文路径")
    ap.add_argument("--new", required=True, help="润色后文本路径")
    ap.add_argument("--terms", default=None, help="术语表 TSV（可选）")
    ap.add_argument("--out", required=True, help="校验报告 JSON 输出路径")
    ap.add_argument("--sentence-drift-warn", type=float, default=0.10,
                    help="句数漂移率软警告阈值（默认 0.10）")
    args = ap.parse_args()

    report = {"orig": args.orig, "new": args.new, "terms": args.terms,
              "hard_violations": [], "soft_warnings": [], "details": {}}

    try:
        orig = read_text(args.orig)
        new = read_text(args.new)
    except Exception as exc:  # noqa: BLE001
        print(f"[check_polish] 读取失败：{exc}", file=sys.stderr)
        return 2

    # 1. 数字与单位
    num_o, num_n = extract_numbers(orig), extract_numbers(new)
    miss, add = counter_diff(num_o, num_n)
    report["details"]["numbers"] = {"missing_in_new": miss, "added_in_new": add,
                                    "orig_count": sum(num_o.values()),
                                    "new_count": sum(num_n.values())}
    if miss or add:
        report["hard_violations"].append(
            {"type": "NUMBER_UNIT_CHANGED", "missing_in_new": miss, "added_in_new": add})

    # 2. 引用编号
    cit_o, cit_n = extract_citations(orig), extract_citations(new)
    miss, add = counter_diff(cit_o, cit_n)
    report["details"]["citations"] = {"missing_in_new": miss, "added_in_new": add}
    if miss or add:
        report["hard_violations"].append(
            {"type": "CITATION_CHANGED", "missing_in_new": miss, "added_in_new": add})

    # 3. 图表指向
    ft_o, ft_n = extract_figtab(orig), extract_figtab(new)
    miss, add = counter_diff(ft_o, ft_n)
    report["details"]["figtab_refs"] = {
        "missing_in_new": [f"{k}{n}" for k, n in miss],
        "added_in_new": [f"{k}{n}" for k, n in add]}
    if miss or add:
        report["hard_violations"].append(
            {"type": "FIGTAB_REF_CHANGED",
             "missing_in_new": [f"{k}{n}" for k, n in miss],
             "added_in_new": [f"{k}{n}" for k, n in add]})

    # 3b. LaTeX 引用键与图表标签（\cite{}/\ref{}，键名多重集比对）
    def latex_keys(rx, text):
        keys = []
        for m in rx.finditer(text):
            keys.extend(k.strip() for k in m.group(1).split(",") if k.strip())
        return Counter(keys)

    for label, rx, vtype in (("latex_cite_keys", LATEXCITE_RE, "LATEX_CITE_CHANGED"),
                             ("latex_ref_keys", LATEXREF_RE, "LATEX_REF_CHANGED")):
        ko, kn = latex_keys(rx, orig), latex_keys(rx, new)
        miss, add = counter_diff(ko, kn)
        report["details"][label] = {"missing_in_new": miss, "added_in_new": add}
        if miss or add:
            report["hard_violations"].append(
                {"type": vtype, "missing_in_new": miss, "added_in_new": add})

    # 4. 限定强度（逐句计算后取全文最高级，避免图表语境污染全篇）
    so, sn = split_sentences(orig), split_sentences(new)

    def max_level(sentences):
        lv = [hedge_level(s)[0] for s in sentences]
        return max(lv) if lv else 0

    lo, ln_ = max_level(so), max_level(sn)
    report["details"]["hedge"] = {"orig_max_level": lo, "new_max_level": ln_}
    if ln_ > lo:
        report["hard_violations"].append(
            {"type": "HEDGE_STRENGTHENED",
             "orig_max_level": lo, "new_max_level": ln_})
    elif ln_ < lo:
        report["soft_warnings"].append(
            {"type": "HEDGE_WEAKENED", "orig_max_level": lo, "new_max_level": ln_})

    # 全文各级命中计数分布
    def level_counts(text):
        c = Counter()
        for lvl, words in HEDGE_LEXICON.items():
            for w in words:
                if w.isascii():
                    c[lvl] += len(re.findall(r"\b" + re.escape(w) + r"\b", text.lower()))
                else:
                    c[lvl] += text.count(w)
        return {str(k): c[k] for k in sorted(c) if c[k]}
    report["details"]["hedge_distribution"] = {"orig": level_counts(orig),
                                               "new": level_counts(new)}

    # 5. 句数漂移
    drift = abs(len(sn) - len(so)) / max(1, len(so))
    report["details"]["sentences"] = {"orig": len(so), "new": len(sn),
                                      "drift": round(drift, 4)}
    if drift > args.sentence_drift_warn:
        report["soft_warnings"].append(
            {"type": "SENTENCE_DRIFT", "orig": len(so), "new": len(sn),
             "drift": round(drift, 4),
             "note": "句数漂移超过阈值；若为长句切分所致，需在 edit_log 中逐句说明"})

    # 6. 术语表
    if args.terms:
        try:
            terms = load_terms(args.terms)
            banned_hits, variant_hits = check_terms(terms, new)
            report["details"]["terms"] = {"banned_hits": banned_hits,
                                          "variant_hits": variant_hits,
                                          "terms_loaded": len(terms)}
            if banned_hits:
                report["hard_violations"].append(
                    {"type": "TERM_BANNED_USED", "hits": banned_hits})
            if variant_hits:
                report["soft_warnings"].append(
                    {"type": "TERM_VARIANT_USED", "hits": variant_hits})
        except Exception as exc:  # noqa: BLE001
            report["soft_warnings"].append(
                {"type": "TERM_TABLE_ERROR", "error": str(exc)})

    report["status"] = "fail" if report["hard_violations"] else "pass"

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f"[check_polish] status={report['status']}  "
          f"hard={len(report['hard_violations'])}  soft={len(report['soft_warnings'])}")
    for v in report["hard_violations"]:
        print(f"  HARD {v['type']}: {json.dumps(v, ensure_ascii=False)[:200]}")
    for v in report["soft_warnings"]:
        print(f"  SOFT {v['type']}: {json.dumps(v, ensure_ascii=False)[:200]}")
    print(f"[check_polish] 报告已写入 {args.out}")

    return 1 if report["hard_violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
