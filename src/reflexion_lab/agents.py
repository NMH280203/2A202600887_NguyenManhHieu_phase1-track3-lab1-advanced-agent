from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Literal
from rich import print
from .mock_runtime import actor_answer, evaluator, reflector, infer_failure_mode
from .schemas import AttemptTrace, JudgeResult, QAExample, ReflectionEntry, RunRecord

VERBOSE_LLM_LOGS = os.getenv("VERBOSE_LLM_LOGS", "1").lower() in {"1", "true", "yes"}


def _log_llm_step(message: str) -> None:
    if VERBOSE_LLM_LOGS:
        print(f"[dim]{message}[/dim]")

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        last_judge = JudgeResult(score=0, reason="No attempt completed.")

        for attempt_id in range(1, self.max_attempts + 1):
            _log_llm_step(
                f"Calling actor... agent={self.agent_type} qid={example.qid} attempt={attempt_id}"
            )
            answer, actor_metrics = actor_answer(
                example, attempt_id, self.agent_type, reflection_memory
            )
            _log_llm_step(
                f"Calling evaluator... agent={self.agent_type} qid={example.qid} attempt={attempt_id}"
            )
            judge, judge_metrics = evaluator(example, answer)
            last_judge = judge
            token_estimate = actor_metrics.token_estimate + judge_metrics.token_estimate
            latency_ms = actor_metrics.latency_ms + judge_metrics.latency_ms

            trace = AttemptTrace(
                attempt_id=attempt_id,
                answer=answer,
                score=judge.score,
                reason=judge.reason,
                token_estimate=token_estimate,
                latency_ms=latency_ms,
            )
            final_answer = answer
            final_score = judge.score

            if judge.score == 1:
                traces.append(trace)
                break

            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                _log_llm_step(
                    f"Calling reflector... agent={self.agent_type} qid={example.qid} attempt={attempt_id}"
                )
                reflection_entry, reflect_metrics = reflector(example, attempt_id, judge)
                reflections.append(reflection_entry)
                trace.reflection = reflection_entry
                trace.token_estimate += reflect_metrics.token_estimate
                trace.latency_ms += reflect_metrics.latency_ms
                reflection_memory.append(
                    f"Attempt {attempt_id} failed.\n"
                    f"Lesson: {reflection_entry.lesson}\n"
                    f"Strategy: {reflection_entry.next_strategy}"
                )

            traces.append(trace)

        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = infer_failure_mode(example, last_judge, traces)

        return RunRecord(
            qid=example.qid,
            question=example.question,
            gold_answer=example.gold_answer,
            agent_type=self.agent_type,
            predicted_answer=final_answer,
            is_correct=bool(final_score),
            attempts=len(traces),
            token_estimate=total_tokens,
            latency_ms=total_latency,
            failure_mode=failure_mode,
            reflections=reflections,
            traces=traces,
        )

class ReActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_type="react", max_attempts=1)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts)
