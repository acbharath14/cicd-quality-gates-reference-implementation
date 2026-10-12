"""CI/CD Quality Gates evaluator.

Feed it metrics JSON (smoke, performance, accessibility, static analysis) plus
an optional integration-suite report, and it produces a PASS/WARN/BLOCK decision
with reports in JSON, Markdown, JUnit XML, and HTML formats.

Usage:
    python scripts/evaluate_gates.py [metrics.json] [integration.json]
                                     [--junit out.xml] [--html out.html]
"""
import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

THRESHOLDS = {
    "p95LatencyMs": 800,
    "errorRatePercent": 1,
    "throughputRps": 100,
    "criticalViolations": 0,
    "blockers": 0,
}

GATE_CHECKS = [
    ("smoke", "Smoke gate"),
    ("performance.p95LatencyMs", "Performance p95 latency"),
    ("performance.errorRatePercent", "Error rate"),
    ("performance.throughputRps", "Throughput"),
    ("accessibility.criticalViolations", "Accessibility critical violations"),
    ("staticAnalysis.blockers", "Static analysis blockers"),
]


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


def gate_states(failures: list[str], warnings: list[str],
                has_integration: bool) -> list[tuple[str, str]]:
    """Return [(gate label, 'pass'|'fail'|'warn')] for every gate."""
    states = []
    for _key, label in GATE_CHECKS:
        if any(label.lower() in f.lower() for f in failures):
            states.append((label, "fail"))
        else:
            states.append((label, "pass"))
    if has_integration:
        if any("integration" in f.lower() or "scenario" in f.lower() for f in failures):
            states.append(("Integration suite report", "fail"))
        elif warnings:
            states.append(("Integration suite report", "warn"))
        else:
            states.append(("Integration suite report", "pass"))
    return states


def write_junit_xml(failures: list[str], warnings: list[str],
                    has_integration: bool, path: Path) -> None:
    """JUnit XML: one testcase per gate, failures marked."""
    states = gate_states(failures, warnings, has_integration)
    n_fail = sum(1 for _, s in states if s == "fail")
    n_warn = sum(1 for _, s in states if s == "warn")
    suite = ET.Element("testsuite", name="quality-gates",
                       tests=str(len(states)),
                       failures=str(n_fail),
                       skipped=str(n_warn))
    for label, state in states:
        tc = ET.SubElement(suite, "testcase", classname="quality-gates", name=label)
        if state == "fail":
            msg = next((f for f in failures if label.lower() in f.lower()),
                       next((f for f in failures
                             if "integration" in f.lower() or "scenario" in f.lower()), label))
            fail = ET.SubElement(tc, "failure", message="gate breached")
            fail.text = msg
        elif state == "warn":
            ET.SubElement(tc, "skipped", message="warning")
    tree = ET.ElementTree(suite)
    ET.indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build_markdown(status: str, failures: list[str], warnings: list[str],
                   has_integration: bool, sample_path: Path,
                   integration_path: Path | None) -> str:
    md = ["# Release Readiness\n", f"**Status: {status}**\n",
          f"- Source metrics: `{sample_path}`",
          f"- Integration report: `{integration_path if integration_path else 'none'}`\n"]
    md.append("## Gate results\n")
    md.append("| Gate | Result |")
    md.append("| --- | --- |")
    for label, state in gate_states(failures, warnings, has_integration):
        mark = {"pass": "✅ PASS", "fail": "❌ FAIL", "warn": "⚠️ WARN"}[state]
        md.append(f"| {label} | {mark} |")
    if failures:
        md.append("\n## Failures\n")
        md.extend(f"- ❌ {f}" for f in failures)
    if warnings:
        md.append("\n## Warnings\n")
        md.extend(f"- ⚠️ {w}" for w in warnings)
    if not failures and not warnings:
        md.append("\nAll quality gates passed. ✅\n")
    md.append("\n## Thresholds\n")
    md.append("| Metric | Threshold |")
    md.append("| --- | --- |")
    for k, v in THRESHOLDS.items():
        md.append(f"| `{k}` | `{v}` |")
    return "\n".join(md) + "\n"


def build_html(status: str, failures: list[str], warnings: list[str],
               has_integration: bool, sample_path: Path,
               integration_path: Path | None) -> str:
    """Self-contained HTML report with inline CSS. Open directly in a browser."""
    color = {"PASS": "#16a34a", "WARN": "#d97706", "BLOCK": "#dc2626"}[status]
    icon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}
    rows = "\n".join(
        f'<tr><td>{html.escape(label)}</td>'
        f'<td class="{state}">{icon[state]} {state.upper()}</td></tr>'
        for label, state in gate_states(failures, warnings, has_integration)
    )
    thresh_rows = "\n".join(
        f"<tr><td><code>{html.escape(k)}</code></td><td><code>{v}</code></td></tr>"
        for k, v in THRESHOLDS.items()
    )
    fails = "".join(f"<li>❌ {html.escape(f)}</li>" for f in failures)
    warns = "".join(f"<li>⚠️ {html.escape(w)}</li>" for w in warnings)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Release Readiness — {status}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;color:#1f2937}}
h1{{display:flex;align-items:center;gap:.5rem}}
.badge{{background:{color};color:#fff;padding:.25rem .75rem;border-radius:9999px;font-size:1rem}}
table{{width:100%;border-collapse:collapse;margin:1rem 0}}
th,td{{text-align:left;padding:.5rem .75rem;border-bottom:1px solid #e5e7eb}}
th{{background:#f9fafb}}
.pass{{color:#16a34a;font-weight:600}}.fail{{color:#dc2626;font-weight:600}}.warn{{color:#d97706;font-weight:600}}
ul{{line-height:1.8}}
.meta{{color:#6b7280;font-size:.9rem}}
</style></head><body>
<h1>Release Readiness <span class="badge">{status}</span></h1>
<p class="meta">Metrics: {html.escape(str(sample_path))} &middot;
Integration: {html.escape(str(integration_path) if integration_path else "none")}</p>
<h2>Gate results</h2>
<table><tr><th>Gate</th><th>Result</th></tr>{rows}</table>
{"<h2>Failures</h2><ul>" + fails + "</ul>" if fails else ""}
{"<h2>Warnings</h2><ul>" + warns + "</ul>" if warns else ""}
{"<p>All quality gates passed. ✅</p>" if not fails and not warns else ""}
<h2>Thresholds</h2>
<table><tr><th>Metric</th><th>Threshold</th></tr>{thresh_rows}</table>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate release quality gates")
    parser.add_argument("metrics", nargs="?", default="sample-data/metrics.json")
    parser.add_argument("integration", nargs="?", default=None)
    parser.add_argument("--junit", default=None, help="Write JUnit XML report to this path")
    parser.add_argument("--html", default=None, help="Write HTML report to this path")
    args = parser.parse_args()

    sample_path = Path(args.metrics)
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    integration_path = Path(args.integration) if args.integration else None
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

    has_integration = integration_path is not None
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
        build_markdown(status, failures, warnings, has_integration, sample_path, integration_path),
        encoding="utf-8",
    )
    if args.junit:
        write_junit_xml(failures, warnings, has_integration, Path(args.junit))
    if args.html:
        Path(args.html).write_text(
            build_html(status, failures, warnings, has_integration, sample_path, integration_path),
            encoding="utf-8",
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
