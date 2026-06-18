# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_mini.json
- Mode: ollama/llama3.1
- Records: 200
- Agents: react, reflexion

## Bảng so sánh ReAct vs Reflexion Agent

| Metric | ReAct | Reflexion | Delta (Reflexion − ReAct) |
|---|---:|---:|---:|
| Số câu hỏi | 100 | 100 | — |
| Đúng / Tổng | 79 / 100 | 100 / 100 | +21 |
| EM (accuracy) | 79.0% | 100.0% | +21.00% |
| Avg attempts | 1 | 1.41 | +0.4100 |
| Avg tokens / câu | 465 | 900.7 | +435.70 |
| Tổng tokens | 46,500 | 90,070 | +43,570 |
| Avg latency / câu | 250 ms | 532.7 ms | +282.70 ms |
| **Tổng running time** | **25.0s** | **53.3s** | **28.3s** |
| Avg runtime / câu | 0.2s | 0.5s | — |
| **Ước tính cost / câu** | **$0.000070** | **$0.000135** | **$0.000065** |
| **Tổng cost (ước tính)** | **$0.006975** | **$0.0135** | **$0.0205** |

## Bảng ước tính Cost & Running Time

> Local Ollama: API cost thực tế = $0. Ước tính cloud tham chiếu = $0.15/1M tokens (REFERENCE_COST_PER_1M_TOKENS, ví dụ gpt-4o-mini blended).
>
> Công thức: `cost = total_tokens / 1,000,000 × giá/1M tokens`

| Hạng mục | ReAct | Reflexion | Tổng (cả 2 agents) |
|---|---:|---:|---:|
| Tổng tokens | 46,500 | 90,070 | 136,570 |
| Giá tham chiếu / 1K tokens | $0.000150 | $0.000150 | $0.000150 |
| Tổng running time | 25.0s | 53.3s | 1m 18s |
| Running time (ms) | 25,000 | 53,270 | 78,270 |
| API cost thực tế (USD) | $0.00 | $0.00 | $0.00 |
| **Ước tính cost (USD)** | **$0.006975** | **$0.0135** | **$0.0205** |
| **Cost / câu (USD)** | **$0.000070** | **$0.000135** | **$0.000102** |

**Reflexion so với ReAct (overhead):**
- Thêm tokens: +43,570
- Thêm running time: 28.3s
- Thêm cost: $0.006535
- Thêm cost / câu: $0.000065

## Failure modes
```json
{
  "react": {
    "none": 79,
    "incomplete_multi_hop": 21
  },
  "reflexion": {
    "none": 100
  },
  "overall": {
    "none": 179,
    "incomplete_multi_hop": 21
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
On this benchmark, ReAct achieved 79.0% EM (79/100 correct) with 1 attempt per question, while Reflexion reached 100.0% EM at 1.41 average attempts. Reflexion improved EM by +21.00 percentage points but used +43,570 more tokens and 28.3s extra runtime versus ReAct. ReAct failure modes: {'incomplete_multi_hop': 21}. Reflexion failure modes: {'none': 100}. Estimated combined cost at $0.1500/1M tokens: $0.0205 ($0.000102/record). Reflection memory was most useful when the first attempt stopped early or picked a wrong entity; the main tradeoff is higher latency and token usage per question.
