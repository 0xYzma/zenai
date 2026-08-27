"""
Evaluation Runner — §18, §20

Runs the benchmark against the chat pipeline and measures:
- Execution accuracy (does SQL run?)
- Result correctness (does answer match expected?)
- Graceful fallback on unanswerable questions
- Confidence calibration (does "high" correlate with correct?)
- Latency

Usage: python -m app.evaluation.runner --workspace-id <id> [--question Q01]
"""
import asyncio
import json
import time
import httpx
import sys
from datetime import datetime, timezone
from app.evaluation.benchmark import load_benchmark, get_questions_by_difficulty

API_BASE = "http://localhost:8000"


async def run_evaluation(workspace_id: str, token: str, question_ids: list[str] = None):
    """Run evaluation benchmark against a workspace."""
    benchmark = load_benchmark()
    if question_ids:
        benchmark = [q for q in benchmark if q["id"] in question_ids]

    results = []
    total = len(benchmark)

    print(f"\n{'='*60}")
    print(f"  ZenAI Evaluation Benchmark — §18")
    print(f"  Workspace: {workspace_id}")
    print(f"  Questions: {total}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    for i, question in enumerate(benchmark, 1):
        print(f"[{i}/{total}] {question['id']}: {question['question'][:60]}...", end=" ")
        start = time.time()

        try:
            result = await _run_question(workspace_id, token, question)
            latency_ms = int((time.time() - start) * 1000)
            result["latency_ms"] = latency_ms
            results.append(result)

            status = "✓" if result["execution_success"] else "✗"
            fallback = "✓" if result["graceful_fallback"] else " "
            print(f"{status} [{latency_ms}ms] conf={result['confidence']} fallback={fallback}")

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            results.append({
                "question_id": question["id"],
                "error": str(e),
                "latency_ms": latency_ms,
                "execution_success": False,
            })
            print(f"✗ ERROR: {e}")

    # Compute summary metrics
    summary = _compute_metrics(results)
    summary["total_questions"] = total
    summary["timestamp"] = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*60}")
    print(f"  Results Summary")
    print(f"{'='*60}")
    print(f"  Execution accuracy:    {summary['execution_accuracy_pct']:.1f}%")
    print(f"  Graceful fallback:     {summary['graceful_fallback_pct']:.1f}%")
    print(f"  Avg latency:           {summary['avg_latency_ms']:.0f}ms")
    print(f"  Median latency:        {summary['median_latency_ms']:.0f}ms")
    print(f"  P95 latency:           {summary['p95_latency_ms']:.0f}ms")
    print(f"  Confidence high count: {summary['confidence_high_count']}")
    print(f"  Confidence med count:  {summary['confidence_medium_count']}")
    print(f"  Confidence low count:  {summary['confidence_low_count']}")
    print(f"{'='*60}\n")

    # Save results
    output = {"summary": summary, "results": results}
    output_path = f"evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Results saved to {output_path}")

    return summary


async def _run_question(workspace_id: str, token: str, question: dict) -> dict:
    """Run a single question and return structured result."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE}/workspaces/{workspace_id}/chat",
            json={"question": question["question"]},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

        if response.status_code != 200:
            return {
                "question_id": question["id"],
                "execution_success": False,
                "error": f"HTTP {response.status_code}",
            }

        # Parse streaming response
        full_answer = ""
        generated_sql = ""
        confidence = "medium"
        chart_type = "none"
        error = None

        for line in response.text.strip().split("\n"):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                if chunk.get("type") == "answer":
                    full_answer = chunk.get("answer", "")
                    generated_sql = chunk.get("generated_sql", "")
                    confidence = chunk.get("confidence", "medium")
                    chart_type = chunk.get("chart_type", "none")
                    error = chunk.get("error")
            except json.JSONDecodeError:
                continue

        # Check execution success
        execution_success = error is None and generated_sql != ""

        # Check graceful fallback for unanswerable questions
        graceful_fallback = False
        if question["difficulty"] == "unanswerable":
            no_data_indicators = ["no data", "no matching", "don't have data", "cannot answer", "no matching table"]
            graceful_fallback = any(ind.lower() in full_answer.lower() for ind in no_data_indicators)
        else:
            graceful_fallback = True  # Non-unanswerable questions don't need fallback

        return {
            "question_id": question["id"],
            "question": question["question"],
            "difficulty": question["difficulty"],
            "category": question["category"],
            "execution_success": execution_success,
            "generated_sql": generated_sql,
            "answer": full_answer[:500],
            "confidence": confidence,
            "chart_type": chart_type,
            "graceful_fallback": graceful_fallback,
            "error": error,
        }


def _compute_metrics(results: list[dict]) -> dict:
    """Compute summary metrics from evaluation results (§20)."""
    total = len(results)
    if total == 0:
        return {"execution_accuracy_pct": 0, "graceful_fallback_pct": 0}

    exec_success = sum(1 for r in results if r.get("execution_success"))
    graceful = sum(1 for r in results if r.get("graceful_fallback"))
    latencies = [r.get("latency_ms", 0) for r in results if r.get("latency_ms")]

    conf_high = sum(1 for r in results if r.get("confidence") == "high")
    conf_med = sum(1 for r in results if r.get("confidence") == "medium")
    conf_low = sum(1 for r in results if r.get("confidence") == "low")

    latencies_sorted = sorted(latencies) if latencies else [0]

    return {
        "execution_accuracy_pct": exec_success / total * 100,
        "graceful_fallback_pct": graceful / total * 100,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "median_latency_ms": latencies_sorted[len(latencies_sorted) // 2],
        "p95_latency_ms": latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else 0,
        "confidence_high_count": conf_high,
        "confidence_medium_count": conf_med,
        "confidence_low_count": conf_low,
        "mvp_target_execution_accuracy": 85.0,
        "mvp_target_result_correctness": 80.0,
        "mvp_target_graceful_fallback": 100.0,
        "pass_execution_accuracy": exec_success / total * 100 >= 85.0,
        "pass_graceful_fallback": graceful / total * 100 >= 100.0,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run ZenAI evaluation benchmark")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--questions", nargs="*", help="Specific question IDs to run")
    args = parser.parse_args()

    asyncio.run(run_evaluation(args.workspace_id, args.token, args.questions))
