# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_part1.json
- Mode: ollama/llama3.1
- Records: 100
- Agents: react, reflexion

## Bảng so sánh ReAct vs Reflexion Agent

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) |
|---|---:|---:|---:|
| Số câu hỏi | 50 | 50 | — |
| Đúng / Tổng | 39 / 50 | 50 / 50 | +11 |
| EM (accuracy) | 78.0% | 100.0% | +22.00% |
| Avg attempts | 1 | 1.38 | +0.3800 |
| Avg tokens / câu | 465 | 877.6 | +412.60 |
| Tổng tokens | 23,250 | 43,880 | +20,630 |
| Avg latency / câu | 250 ms | 518.6 ms | +268.60 ms |
| **Tổng running time** | **12.5s** | **25.9s** | **13.4s** |
| Avg runtime / câu | 0.2s | 0.5s | — |
| **Ước tính cost / câu** | **$0.000070** | **$0.000132** | **$0.000062** |
| **Tổng cost (ước tính)** | **$0.003487** | **$0.006582** | **$0.0101** |

## Bảng ước tính Cost & Running Time

> Local Ollama: API cost thực tế = $0. Ước tính cloud tham chiếu = $0.15/1M tokens (REFERENCE_COST_PER_1M_TOKENS, ví dụ gpt-4o-mini blended).
>
> Công thức: `cost = total_tokens / 1,000,000 × giá/1M tokens`

| Hạng mục | ReAct | Reflexion | Tổng (cả 2 agents) |
|---|---:|---:|---:|
| Tổng tokens | 23,250 | 43,880 | 67,130 |
| Giá tham chiếu / 1K tokens | $0.000150 | $0.000150 | $0.000150 |
| Tổng running time | 12.5s | 25.9s | 38.4s |
| Running time (ms) | 12,500 | 25,930 | 38,430 |
| API cost thực tế (USD) | $0.00 | $0.00 | $0.00 |
| **Ước tính cost (USD)** | **$0.003487** | **$0.006582** | **$0.0101** |
| **Cost / câu (USD)** | **$0.000070** | **$0.000132** | **$0.000101** |

**Reflexion so với ReAct (overhead):**
- Thêm tokens: +20,630
- Thêm running time: 13.4s
- Thêm cost: $0.003095
- Thêm cost / câu: $0.000062

## Failure modes
```json
{
  "react": {
    "none": 39,
    "incomplete_multi_hop": 11
  },
  "reflexion": {
    "none": 50
  },
  "overall": {
    "none": 89,
    "incomplete_multi_hop": 11
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
On this benchmark, ReAct achieved 78.0% EM (39/50 correct) with 1 attempt per question, while Reflexion reached 100.0% EM at 1.38 average attempts. Reflexion improved EM by +22.00 percentage points but used +20,630 more tokens and 13.4s extra runtime versus ReAct. ReAct failure modes: {'incomplete_multi_hop': 11}. Reflexion failure modes: {'none': 50}. Estimated combined cost at $0.1500/1M tokens: $0.0101 ($0.000101/record). Reflection memory was most useful when the first attempt stopped early or picked a wrong entity; the main tradeoff is higher latency and token usage per question.
