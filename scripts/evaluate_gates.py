import json
import sys
from pathlib import Path

THRESHOLDS = {
    "p95LatencyMs": 800,
    "errorRatePercent": 1,
    "throughputRps": 100,
    "criticalViolations": 0,
    "blockers": 0,
}


def main() -> int:
    sample_path = Path(sys.argv[1] if len(sys.argv) > 1 else "sample-data/metrics.json")
    data = json.loads(sample_path.read_text(encoding="utf-8"))

    failures = []
    if not data["smoke"]["passed"]:
        failures.append("Smoke gate failed")
    if data["performance"]["p95LatencyMs"] > THRESHOLDS["p95LatencyMs"]:
        failures.append("Performance p95 latency breached")
    if data["performance"]["errorRatePercent"] > THRESHOLDS["errorRatePercent"]:
        failures.append("Error rate breached")
    if data["performance"]["throughputRps"] < THRESHOLDS["throughputRps"]:
        failures.append("Throughput breached")
    if data["accessibility"]["criticalViolations"] > THRESHOLDS["criticalViolations"]:
        failures.append("Accessibility critical violations found")
    if data["staticAnalysis"]["blockers"] > THRESHOLDS["blockers"]:
        failures.append("Static analysis blockers found")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "evaluatedFrom": str(sample_path),
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/release-readiness.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    Path("reports/release-readiness.md").write_text(
        "# Release Readiness\n\n" +
        f"- Status: {report['status']}\n" +
        f"- Failures: {len(failures)}\n" +
        f"- Source: {sample_path}\n",
        encoding="utf-8"
    )

    if failures:
        print("Gate evaluation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("All quality gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
