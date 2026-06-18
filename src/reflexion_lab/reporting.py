from __future__ import annotations
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from .schemas import ReportPayload, RunRecord

DEFAULT_COST_PER_1M_TOKENS = float(os.getenv("COST_PER_1M_TOKENS", "0"))
REFERENCE_COST_PER_1M_TOKENS = float(os.getenv("REFERENCE_COST_PER_1M_TOKENS", "0.15"))


def _format_duration(ms: int | float) -> str:
    total_sec = max(0, int(ms)) / 1000
    if total_sec < 60:
        return f"{total_sec:.1f}s"
    minutes = int(total_sec // 60)
    seconds = total_sec % 60
    if minutes < 60:
        return f"{minutes}m {seconds:.0f}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


def _token_cost_usd(total_tokens: int, price_per_1m: float) -> float:
    return round(total_tokens / 1_000_000 * price_per_1m, 6)


def _fmt_usd(value: float) -> str:
    if value == 0:
        return "$0.00"
    if abs(value) < 0.01:
        return f"${value:.6f}"
    return f"${value:.4f}"


def _agent_metrics(rows: list[RunRecord]) -> dict:
    if not rows:
        return {}
    total_tokens = sum(r.token_estimate for r in rows)
    total_latency_ms = sum(r.latency_ms for r in rows)
    correct = sum(1 for r in rows if r.is_correct)
    count = len(rows)
    return {
        "count": count,
        "correct": correct,
        "wrong": count - correct,
        "em": round(correct / count, 4),
        "em_pct": round(100 * correct / count, 2),
        "avg_attempts": round(mean(r.attempts for r in rows), 4),
        "avg_token_estimate": round(mean(r.token_estimate for r in rows), 2),
        "total_tokens": total_tokens,
        "avg_latency_ms": round(mean(r.latency_ms for r in rows), 2),
        "total_latency_ms": total_latency_ms,
        "total_runtime": _format_duration(total_latency_ms),
        "avg_runtime_per_question": _format_duration(total_latency_ms / count),
    }


def summarize(records: list[RunRecord]) -> dict:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)

    react_rows = grouped.get("react", [])
    reflexion_rows = grouped.get("reflexion", [])
    react = _agent_metrics(react_rows)
    reflexion = _agent_metrics(reflexion_rows)

    summary: dict = {}
    if react:
        summary["react"] = react
    if reflexion:
        summary["reflexion"] = reflexion

    if react and reflexion:
        summary["delta_reflexion_minus_react"] = {
            "em_abs": round(reflexion["em"] - react["em"], 4),
            "em_pct_abs": round(reflexion["em_pct"] - react["em_pct"], 2),
            "attempts_abs": round(reflexion["avg_attempts"] - react["avg_attempts"], 4),
            "tokens_abs": round(reflexion["avg_token_estimate"] - react["avg_token_estimate"], 2),
            "total_tokens_abs": reflexion["total_tokens"] - react["total_tokens"],
            "latency_abs": round(reflexion["avg_latency_ms"] - react["avg_latency_ms"], 2),
            "total_runtime_ms_abs": reflexion["total_latency_ms"] - react["total_latency_ms"],
        }
    return summary


def build_cost_estimate(records: list[RunRecord], price_per_1m_tokens: float | None = None) -> dict:
    actual_price = DEFAULT_COST_PER_1M_TOKENS if price_per_1m_tokens is None else price_per_1m_tokens
    estimate_price = actual_price if actual_price > 0 else REFERENCE_COST_PER_1M_TOKENS
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)

    def _cost_block(rows: list[RunRecord]) -> dict:
        total_tokens = sum(r.token_estimate for r in rows)
        total_latency_ms = sum(r.latency_ms for r in rows)
        estimated_cost = _token_cost_usd(total_tokens, estimate_price)
        actual_api_cost = _token_cost_usd(total_tokens, actual_price)
        count = len(rows)
        return {
            "total_tokens": total_tokens,
            "total_runtime_ms": total_latency_ms,
            "total_runtime": _format_duration(total_latency_ms),
            "estimated_cost_usd": estimated_cost,
            "actual_api_cost_usd": actual_api_cost,
            "cost_per_question_usd": round(estimated_cost / count, 6) if count else 0,
            "actual_cost_per_question_usd": round(actual_api_cost / count, 6) if count else 0,
            "cost_per_1k_tokens_usd": round(estimate_price / 1000, 6),
        }

    react = _cost_block(grouped.get("react", []))
    reflexion = _cost_block(grouped.get("reflexion", []))
    combined_tokens = react["total_tokens"] + reflexion["total_tokens"]
    combined_runtime_ms = react["total_runtime_ms"] + reflexion["total_runtime_ms"]
    combined_cost = _token_cost_usd(combined_tokens, estimate_price)
    combined_actual_cost = _token_cost_usd(combined_tokens, actual_price)
    question_count = len(grouped.get("react", [])) + len(grouped.get("reflexion", []))

    if actual_price > 0:
        pricing_note = (
            f"Tính theo giá thực tế ${actual_price}/1M tokens "
            f"(COST_PER_1M_TOKENS)."
        )
    else:
        pricing_note = (
            f"Local Ollama: API cost thực tế = $0. "
            f"Ước tính cloud tham chiếu = ${estimate_price}/1M tokens "
            f"(REFERENCE_COST_PER_1M_TOKENS, ví dụ gpt-4o-mini blended)."
        )

    return {
        "price_per_1m_tokens_usd": estimate_price,
        "actual_price_per_1m_tokens_usd": actual_price,
        "reference_price_per_1m_tokens_usd": REFERENCE_COST_PER_1M_TOKENS,
        "pricing_note": pricing_note,
        "react": react,
        "reflexion": reflexion,
        "combined": {
            "total_tokens": combined_tokens,
            "total_runtime_ms": combined_runtime_ms,
            "total_runtime": _format_duration(combined_runtime_ms),
            "estimated_cost_usd": combined_cost,
            "actual_api_cost_usd": combined_actual_cost,
            "cost_per_question_usd": round(combined_cost / question_count, 6) if question_count else 0,
        },
        "delta_reflexion_minus_react": {
            "extra_tokens": reflexion["total_tokens"] - react["total_tokens"],
            "extra_runtime_ms": reflexion["total_runtime_ms"] - react["total_runtime_ms"],
            "extra_runtime": _format_duration(reflexion["total_runtime_ms"] - react["total_runtime_ms"]),
            "extra_cost_usd": round(reflexion["estimated_cost_usd"] - react["estimated_cost_usd"], 6),
            "extra_cost_per_question_usd": round(
                reflexion["cost_per_question_usd"] - react["cost_per_question_usd"], 6
            ),
        },
    }


def failure_breakdown(records: list[RunRecord]) -> dict:
    by_agent: dict[str, Counter] = defaultdict(Counter)
    overall: Counter = Counter()
    for record in records:
        by_agent[record.agent_type][record.failure_mode] += 1
        overall[record.failure_mode] += 1
    return {
        "react": dict(by_agent.get("react", Counter())),
        "reflexion": dict(by_agent.get("reflexion", Counter())),
        "overall": dict(overall),
    }


def build_discussion(summary: dict, cost: dict, failure_modes: dict) -> str:
    react = summary.get("react", {})
    reflexion = summary.get("reflexion", {})
    delta = summary.get("delta_reflexion_minus_react", {})
    cost_delta = cost.get("delta_reflexion_minus_react", {})

    react_failures = failure_modes.get("react", {})
    wrong_modes = {k: v for k, v in react_failures.items() if k != "none"}

    return (
        f"On this benchmark, ReAct achieved {react.get('em_pct', 0)}% EM "
        f"({react.get('correct', 0)}/{react.get('count', 0)} correct) with 1 attempt per question, "
        f"while Reflexion reached {reflexion.get('em_pct', 0)}% EM "
        f"at {reflexion.get('avg_attempts', 0)} average attempts. "
        f"Reflexion improved EM by {delta.get('em_pct_abs', 0):+.2f} percentage points but used "
        f"{cost_delta.get('extra_tokens', 0):+,} more tokens and "
        f"{cost_delta.get('extra_runtime', '0s')} extra runtime versus ReAct. "
        f"ReAct failure modes: {wrong_modes or 'none'}. "
        f"Reflexion failure modes: {failure_modes.get('reflexion', {}) or 'none'}. "
        f"Estimated combined cost at ${_fmt_usd(cost.get('price_per_1m_tokens_usd', 0)).lstrip('$')}/1M tokens: "
        f"{_fmt_usd(cost.get('combined', {}).get('estimated_cost_usd', 0))} "
        f"({_fmt_usd(cost.get('combined', {}).get('cost_per_question_usd', 0))}/record). "
        f"Reflection memory was most useful when the first attempt stopped early or picked a wrong entity; "
        f"the main tradeoff is higher latency and token usage per question."
    )


def build_report(records: list[RunRecord], dataset_name: str, mode: str = "mock") -> ReportPayload:
    summary = summarize(records)
    failure_modes = failure_breakdown(records)
    cost_estimate = build_cost_estimate(records)
    summary["cost_estimate"] = cost_estimate

    examples = [
        {
            "qid": r.qid,
            "agent_type": r.agent_type,
            "gold_answer": r.gold_answer,
            "predicted_answer": r.predicted_answer,
            "is_correct": r.is_correct,
            "attempts": r.attempts,
            "failure_mode": r.failure_mode,
            "reflection_count": len(r.reflections),
        }
        for r in records
    ]

    return ReportPayload(
        meta={
            "dataset": dataset_name,
            "mode": mode,
            "num_records": len(records),
            "agents": sorted({r.agent_type for r in records}),
        },
        summary=summary,
        failure_modes=failure_modes,
        examples=examples,
        extensions=[
            "structured_evaluator",
            "reflection_memory",
            "benchmark_report_json",
            "mock_mode_for_autograding",
        ],
        discussion=build_discussion(summary, cost_estimate, failure_modes),
    )


def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")

    react = report.summary.get("react", {})
    reflexion = report.summary.get("reflexion", {})
    delta = report.summary.get("delta_reflexion_minus_react", {})
    cost = report.summary.get("cost_estimate", {})
    cost_react = cost.get("react", {})
    cost_reflexion = cost.get("reflexion", {})
    cost_combined = cost.get("combined", {})
    cost_delta = cost.get("delta_reflexion_minus_react", {})
    ext_lines = "\n".join(f"- {item}" for item in report.extensions)

    md = f"""# Lab 16 Benchmark Report

## Metadata
- Dataset: {report.meta['dataset']}
- Mode: {report.meta['mode']}
- Records: {report.meta['num_records']}
- Agents: {', '.join(report.meta['agents'])}

## Bảng so sánh ReAct vs Reflexion Agent

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) |
|---|---:|---:|---:|
| Số câu hỏi | {react.get('count', 0)} | {reflexion.get('count', 0)} | — |
| Đúng / Tổng | {react.get('correct', 0)} / {react.get('count', 0)} | {reflexion.get('correct', 0)} / {reflexion.get('count', 0)} | {reflexion.get('correct', 0) - react.get('correct', 0):+d} |
| EM (accuracy) | {react.get('em_pct', 0)}% | {reflexion.get('em_pct', 0)}% | {delta.get('em_pct_abs', 0):+.2f}% |
| Avg attempts | {react.get('avg_attempts', 0)} | {reflexion.get('avg_attempts', 0)} | {delta.get('attempts_abs', 0):+.4f} |
| Avg tokens / câu | {react.get('avg_token_estimate', 0)} | {reflexion.get('avg_token_estimate', 0)} | {delta.get('tokens_abs', 0):+.2f} |
| Tổng tokens | {react.get('total_tokens', 0):,} | {reflexion.get('total_tokens', 0):,} | {delta.get('total_tokens_abs', 0):+,} |
| Avg latency / câu | {react.get('avg_latency_ms', 0)} ms | {reflexion.get('avg_latency_ms', 0)} ms | {delta.get('latency_abs', 0):+.2f} ms |
| **Tổng running time** | **{react.get('total_runtime', '0s')}** | **{reflexion.get('total_runtime', '0s')}** | **{cost_delta.get('extra_runtime', '0s')}** |
| Avg runtime / câu | {react.get('avg_runtime_per_question', '0s')} | {reflexion.get('avg_runtime_per_question', '0s')} | — |
| **Ước tính cost / câu** | **{_fmt_usd(cost_react.get('cost_per_question_usd', 0))}** | **{_fmt_usd(cost_reflexion.get('cost_per_question_usd', 0))}** | **{_fmt_usd(cost_delta.get('extra_cost_per_question_usd', 0))}** |
| **Tổng cost (ước tính)** | **{_fmt_usd(cost_react.get('estimated_cost_usd', 0))}** | **{_fmt_usd(cost_reflexion.get('estimated_cost_usd', 0))}** | **{_fmt_usd(cost_combined.get('estimated_cost_usd', 0))}** |

## Bảng ước tính Cost & Running Time

> {cost.get('pricing_note', '')}
>
> Công thức: `cost = total_tokens / 1,000,000 × giá/1M tokens`

| Hạng mục | ReAct | Reflexion | Tổng (cả 2 agents) |
|---|---:|---:|---:|
| Tổng tokens | {cost_react.get('total_tokens', 0):,} | {cost_reflexion.get('total_tokens', 0):,} | {cost_combined.get('total_tokens', 0):,} |
| Giá tham chiếu / 1K tokens | {_fmt_usd(cost_react.get('cost_per_1k_tokens_usd', 0))} | {_fmt_usd(cost_reflexion.get('cost_per_1k_tokens_usd', 0))} | {_fmt_usd(cost.get('price_per_1m_tokens_usd', 0) / 1000)} |
| Tổng running time | {cost_react.get('total_runtime', '0s')} | {cost_reflexion.get('total_runtime', '0s')} | {cost_combined.get('total_runtime', '0s')} |
| Running time (ms) | {cost_react.get('total_runtime_ms', 0):,} | {cost_reflexion.get('total_runtime_ms', 0):,} | {cost_combined.get('total_runtime_ms', 0):,} |
| API cost thực tế (USD) | {_fmt_usd(cost_react.get('actual_api_cost_usd', 0))} | {_fmt_usd(cost_reflexion.get('actual_api_cost_usd', 0))} | {_fmt_usd(cost_combined.get('actual_api_cost_usd', 0))} |
| **Ước tính cost (USD)** | **{_fmt_usd(cost_react.get('estimated_cost_usd', 0))}** | **{_fmt_usd(cost_reflexion.get('estimated_cost_usd', 0))}** | **{_fmt_usd(cost_combined.get('estimated_cost_usd', 0))}** |
| **Cost / câu (USD)** | **{_fmt_usd(cost_react.get('cost_per_question_usd', 0))}** | **{_fmt_usd(cost_reflexion.get('cost_per_question_usd', 0))}** | **{_fmt_usd(cost_combined.get('cost_per_question_usd', 0))}** |

**Reflexion so với ReAct (overhead):**
- Thêm tokens: {cost_delta.get('extra_tokens', 0):+,}
- Thêm running time: {cost_delta.get('extra_runtime', '0s')}
- Thêm cost: {_fmt_usd(cost_delta.get('extra_cost_usd', 0))}
- Thêm cost / câu: {_fmt_usd(cost_delta.get('extra_cost_per_question_usd', 0))}

## Failure modes
```json
{json.dumps(report.failure_modes, indent=2)}
```

## Extensions implemented
{ext_lines}

## Discussion
{report.discussion}
"""
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path
