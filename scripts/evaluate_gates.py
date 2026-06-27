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


def evaluate_metric_gates(data: dict) -> list[str]:
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
    return failures


def evaluate_integration_report(integration_data: dict | None) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    if integration_data is None:
        return failures, warnings

    final_decision = integration_data.get("finalDecision", "PASS")
    if final_decision == "BLOCK":
        failures.append("Integration suite reported BLOCK decision")
    elif final_decision == "WARN":
        warnings.append("Integration suite reported WARN decision")

    for scenario in integration_data.get("scenarios", []):
        decision = scenario.get("releaseDecision", "PASS")
        scenario_name = scenario.get("scenario", "unknown")
        reason = scenario.get("reason", "")
        if decision == "BLOCK":
            failures.append(f"Scenario '{scenario_name}' blocked release: {reason}")
        elif decision == "WARN":
            warnings.append(f"Scenario '{scenario_name}' raised warning: {reason}")

    return failures, warnings


def main() -> int:
    sample_path = Path(sys.argv[1] if len(sys.argv) > 1 else "sample-data/metrics.json")
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    integration_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    integration_data = None
    if integration_path:
        integration_data = json.loads(integration_path.read_text(encoding="utf-8"))

    failures = evaluate_metric_gates(data)
    integration_failures, warnings = evaluate_integration_report(integration_data)
    failures.extend(integration_failures)

    status = "PASS"
    if failures:
        status = "BLOCK"
    elif warnings:
        status = "WARN"

    report = {
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "evaluatedFrom": str(sample_path),
        "integrationReport": str(integration_path) if integration_path else "none",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/release-readiness.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    Path("reports/release-readiness.md").write_text(
        "# Release Readiness\n\n" +
        f"- Status: {report['status']}\n" +
        f"- Failures: {len(failures)}\n" +
        f"- Warnings: {len(warnings)}\n" +
        f"- Source: {sample_path}\n",
        encoding="utf-8"
    )

    if failures:
        print("Gate evaluation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    if warnings:
        print("Gate evaluation warnings:")
        for warning in warnings:
            print(f"- {warning}")
        return 0

    print("All quality gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
