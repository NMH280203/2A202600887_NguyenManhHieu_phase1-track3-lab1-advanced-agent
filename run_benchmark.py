from __future__ import annotations
import json
import os
import time
from pathlib import Path
import typer
from rich import print
from src.reflexion_lab.agents import BaseAgent, ReActAgent, ReflexionAgent
from src.reflexion_lab.llm_client import is_mock_mode, is_ollama_backend
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.schemas import QAExample, RunRecord
from src.reflexion_lab.utils import load_dataset, save_jsonl

app = typer.Typer(add_completion=False)


def _run_agent(
    agent: BaseAgent,
    examples: list[QAExample],
    *,
    label: str,
) -> list[RunRecord]:
    records: list[RunRecord] = []
    total = len(examples)
    t0 = time.perf_counter()

    for i, example in enumerate(examples, start=1):
        q_t0 = time.perf_counter()
        record = agent.run(example)
        q_elapsed = time.perf_counter() - q_t0
        records.append(record)

        status = "[green]OK[/green]" if record.is_correct else "[red]WRONG[/red]"
        print(
            f"[cyan]{label}[/cyan] [{i}/{total}] "
            f"qid={example.qid[:12]}… {status} "
            f"attempts={record.attempts} "
            f"tokens={record.token_estimate} "
            f"time={q_elapsed:.1f}s"
        )

    elapsed = time.perf_counter() - t0
    correct = sum(1 for r in records if r.is_correct)
    print(
        f"[bold]{label} done:[/bold] {correct}/{total} correct "
        f"({100 * correct / total:.1f}%) in {elapsed:.1f}s\n"
    )
    return records


@app.command()
def main(
    dataset: str = "data/hotpot_part1.json",
    out_dir: str = "outputs/sample_run",
    reflexion_attempts: int = 3,
) -> None:
    examples = load_dataset(dataset)
    print(f"[bold]Dataset:[/bold] {dataset} ({len(examples)} questions)")
    print(f"[bold]Output:[/bold] {out_dir}")
    print(f"[bold]Reflexion max attempts:[/bold] {reflexion_attempts}\n")

    react_records = _run_agent(ReActAgent(), examples, label="ReAct")
    reflexion_records = _run_agent(
        ReflexionAgent(max_attempts=reflexion_attempts),
        examples,
        label="Reflexion",
    )

    all_records = react_records + reflexion_records
    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)

    if is_mock_mode():
        mode = "mock"
    elif is_ollama_backend():
        mode = f"ollama/{os.getenv('OPENAI_MODEL', 'llama3.1')}"
    else:
        mode = os.getenv("OPENAI_MODEL", "openai")

    report = build_report(all_records, dataset_name=Path(dataset).name, mode=mode)
    json_path, md_path = save_report(report, out_path)
    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(json.dumps(report.summary, indent=2))


if __name__ == "__main__":
    app()
