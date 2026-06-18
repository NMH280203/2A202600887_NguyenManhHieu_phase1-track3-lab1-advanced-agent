from __future__ import annotations
from .schemas import QAExample, JudgeResult, ReflectionEntry, CallMetrics
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .utils import normalize_answer
from .llm_client import chat_completion, chat_json, is_mock_mode

FAILURE_MODE_BY_QID: dict[str, str] = {}


def _format_context(example: QAExample) -> str:
    blocks = []
    for chunk in example.context:
        blocks.append(f"[{chunk.title}]\n{chunk.text}")
    return "\n\n".join(blocks)


def _mock_should_fail_first(example: QAExample, agent_type: str, attempt_id: int, reflection_memory: list[str]) -> bool:
    bucket = hash(example.qid) % 5
    if agent_type == "react":
        return attempt_id == 1 and bucket == 0
    if attempt_id == 1 and not reflection_memory:
        return bucket in {0, 1}
    return False


def _mock_wrong_answer(example: QAExample) -> str:
    if example.context:
        return example.context[0].title
    return "unknown"


def infer_failure_mode(example: QAExample, judge: JudgeResult, traces: list) -> str:
    if judge.score == 1:
        return "none"
    if example.qid in FAILURE_MODE_BY_QID:
        return FAILURE_MODE_BY_QID[example.qid]
    reason = judge.reason.lower()
    if any(k in reason for k in ("hop", "second", "chain", "partial", "incomplete")):
        return "incomplete_multi_hop"
    if judge.spurious_claims:
        return "entity_drift"
    if len(traces) >= 2:
        answers = [t.answer for t in traces]
        if len(set(normalize_answer(a) for a in answers)) == 1:
            return "looping"
        if traces[-1].score == 0 and any(t.score == 1 for t in traces[:-1]):
            return "reflection_overfit"
    return "wrong_final_answer"


def actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> tuple[str, CallMetrics]:
    if is_mock_mode():
        if _mock_should_fail_first(example, agent_type, attempt_id, reflection_memory):
            answer = _mock_wrong_answer(example)
        else:
            answer = example.gold_answer
        tokens = 320 + (attempt_id * 65) + (120 if agent_type == "reflexion" else 0)
        latency = 160 + (attempt_id * 40) + (90 if agent_type == "reflexion" else 0)
        return answer, CallMetrics(token_estimate=tokens, latency_ms=latency)

    reflection_block = ""
    if reflection_memory:
        reflection_block = "\n\nPrior reflections:\n" + "\n---\n".join(reflection_memory)

    user = (
        f"Question: {example.question}\n\n"
        f"Context:\n{_format_context(example)}"
        f"{reflection_block}\n\n"
        f"Attempt: {attempt_id}\n"
        "Final answer:"
    )
    text, tokens, latency_ms = chat_completion(ACTOR_SYSTEM, user)
    answer = text.strip().split("\n")[0].strip()
    return answer, CallMetrics(token_estimate=tokens, latency_ms=latency_ms)


def evaluator(example: QAExample, answer: str) -> tuple[JudgeResult, CallMetrics]:
    if is_mock_mode():
        if normalize_answer(example.gold_answer) == normalize_answer(answer):
            judge = JudgeResult(
                score=1,
                reason="Final answer matches the gold answer after normalization.",
            )
        elif normalize_answer(answer) == normalize_answer(_mock_wrong_answer(example)):
            judge = JudgeResult(
                score=0,
                reason="The answer stopped after the first hop and did not complete multi-hop reasoning.",
                missing_evidence=["Need to chain evidence across multiple context passages."],
                spurious_claims=[],
            )
        else:
            judge = JudgeResult(
                score=0,
                reason="The final answer does not match the gold answer.",
                missing_evidence=["Re-read all context passages and verify the final entity."],
                spurious_claims=[answer],
            )
        return judge, CallMetrics(token_estimate=80, latency_ms=50)

    user = (
        f"Question: {example.question}\n"
        f"Gold answer: {example.gold_answer}\n"
        f"Predicted answer: {answer}"
    )
    payload, tokens, latency_ms = chat_json(EVALUATOR_SYSTEM, user)
    judge = JudgeResult.model_validate(payload)
    return judge, CallMetrics(token_estimate=tokens, latency_ms=latency_ms)


def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> tuple[ReflectionEntry, CallMetrics]:
    if is_mock_mode():
        entry = ReflectionEntry(
            attempt_id=attempt_id,
            failure_reason=judge.reason,
            lesson="A partial first-hop answer is not enough; complete all reasoning hops before answering.",
            next_strategy="Trace each hop explicitly across context passages, then verify the final entity.",
        )
        return entry, CallMetrics(token_estimate=120, latency_ms=90)

    user = (
        f"Question: {example.question}\n"
        f"Attempt: {attempt_id}\n"
        f"Evaluator reason: {judge.reason}\n"
        f"Missing evidence: {judge.missing_evidence}\n"
        f"Spurious claims: {judge.spurious_claims}\n"
        f"Context:\n{_format_context(example)}"
    )
    payload, tokens, latency_ms = chat_json(REFLECTOR_SYSTEM, user)
    payload.setdefault("attempt_id", attempt_id)
    entry = ReflectionEntry.model_validate(payload)
    return entry, CallMetrics(token_estimate=tokens, latency_ms=latency_ms)
