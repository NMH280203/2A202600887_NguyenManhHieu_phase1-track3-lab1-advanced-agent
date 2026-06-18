# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_golden.json
- Mode: ollama/llama3.1
- Records: 40
- Agents: react, reflexion

## Bảng so sánh ReAct vs Reflexion Agent

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) |
|---|---:|---:|---:|
| Số câu hỏi | 20 | 20 | — |
| Đúng / Tổng | 18 / 20 | 19 / 20 | +1 |
| EM (accuracy) | 90.0% | 95.0% | +5.00% |
| Avg attempts | 1 | 1.15 | +0.1500 |
| Avg tokens / câu | 424.05 | 554.15 | +130.10 |
| Tổng tokens | 8,481 | 11,083 | +2,602 |
| Avg latency / câu | 3306.5 ms | 13578.15 ms | +10271.65 ms |
| **Tổng running time** | **1m 6s** | **4m 32s** | **3m 25s** |
| Avg runtime / câu | 3.3s | 13.6s | — |
| **Ước tính cost / câu** | **$0.000064** | **$0.000083** | **$0.000019** |
| **Tổng cost (ước tính)** | **$0.001272** | **$0.001662** | **$0.002935** |

## Bảng ước tính Cost & Running Time

> Local Ollama: API cost thực tế = $0. Ước tính cloud tham chiếu = $0.15/1M tokens (REFERENCE_COST_PER_1M_TOKENS, ví dụ gpt-4o-mini blended).
>
> Công thức: `cost = total_tokens / 1,000,000 × giá/1M tokens`

| Hạng mục | ReAct | Reflexion | Tổng (cả 2 agents) |
|---|---:|---:|---:|
| Tổng tokens | 8,481 | 11,083 | 19,564 |
| Giá tham chiếu / 1K tokens | $0.000150 | $0.000150 | $0.000150 |
| Tổng running time | 1m 6s | 4m 32s | 5m 38s |
| Running time (ms) | 66,130 | 271,563 | 337,693 |
| API cost thực tế (USD) | $0.00 | $0.00 | $0.00 |
| **Ước tính cost (USD)** | **$0.001272** | **$0.001662** | **$0.002935** |
| **Cost / câu (USD)** | **$0.000064** | **$0.000083** | **$0.000073** |

**Reflexion so với ReAct (overhead):**
- Thêm tokens: +2,602
- Thêm running time: 3m 25s
- Thêm cost: $0.000390
- Thêm cost / câu: $0.000019

## Failure modes
```json
{
  "react": {
    "none": 18,
    "entity_drift": 2
  },
  "reflexion": {
    "none": 19,
    "entity_drift": 1
  },
  "overall": {
    "none": 37,
    "entity_drift": 3
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
On this benchmark, ReAct achieved 90.0% EM (18/20 correct) with 1 attempt per question, while Reflexion reached 95.0% EM at 1.15 average attempts. Reflexion improved EM by +5.00 percentage points but used +2,602 more tokens and 3m 25s extra runtime versus ReAct. ReAct failure modes: {'entity_drift': 2}. Reflexion failure modes: {'none': 19, 'entity_drift': 1}. Estimated combined cost at $0.1500/1M tokens: $0.002935 ($0.000073/record). Reflection memory was most useful when the first attempt stopped early or picked a wrong entity; the main tradeoff is higher latency and token usage per question.
