"""Unit tests for scripts/evaluate_gates.py.

Covers threshold boundaries, escalation rules, and integration-report handling.
Run: pytest tests/ -q  (from repo root)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from evaluate_gates import (  # noqa: E402
    THRESHOLDS,
    evaluate_integration_report,
    evaluate_metric_gates,
)


def _metrics(**overrides):
    base = {
        "smoke": {"passed": True},
        "performance": {"p95LatencyMs": 640, "errorRatePercent": 0.4, "throughputRps": 120},
        "accessibility": {"criticalViolations": 0},
        "staticAnalysis": {"blockers": 0},
    }
    for section, values in overrides.items():
        base[section].update(values)
    return base


# --- Threshold boundaries ---

def test_all_clean_passes():
    assert evaluate_metric_gates(_metrics()) == []


def test_p95_at_threshold_passes():
    assert evaluate_metric_gates(_metrics(performance={"p95LatencyMs": THRESHOLDS["p95LatencyMs"]})) == []


def test_p95_one_over_threshold_fails():
    failures = evaluate_metric_gates(_metrics(performance={"p95LatencyMs": THRESHOLDS["p95LatencyMs"] + 1}))
    assert failures == ["Performance p95 latency breached"]


def test_error_rate_at_threshold_passes():
    assert evaluate_metric_gates(_metrics(performance={"errorRatePercent": THRESHOLDS["errorRatePercent"]})) == []


def test_error_rate_over_threshold_fails():
    failures = evaluate_metric_gates(_metrics(performance={"errorRatePercent": 1.1}))
    assert "Error rate breached" in failures


def test_throughput_at_threshold_passes():
    assert evaluate_metric_gates(_metrics(performance={"throughputRps": THRESHOLDS["throughputRps"]})) == []


def test_throughput_one_under_threshold_fails():
    failures = evaluate_metric_gates(_metrics(performance={"throughputRps": THRESHOLDS["throughputRps"] - 1}))
    assert failures == ["Throughput breached"]


def test_smoke_failure_blocks():
    failures = evaluate_metric_gates(_metrics(smoke={"passed": False}))
    assert failures == ["Smoke gate failed"]


def test_accessibility_violation_blocks():
    failures = evaluate_metric_gates(_metrics(accessibility={"criticalViolations": 1}))
    assert failures == ["Accessibility critical violations found"]


def test_static_analysis_blocker_blocks():
    failures = evaluate_metric_gates(_metrics(staticAnalysis={"blockers": 2}))
    assert failures == ["Static analysis blockers found"]


def test_multiple_failures_all_reported():
    failures = evaluate_metric_gates(_metrics(
        smoke={"passed": False},
        performance={"p95LatencyMs": 9999},
    ))
    assert len(failures) == 2


# --- Integration report handling ---

def test_no_integration_report_is_clean():
    failures, warnings = evaluate_integration_report(None)
    assert failures == [] and warnings == []


def test_integration_pass_is_clean():
    failures, warnings = evaluate_integration_report({"finalDecision": "PASS", "scenarios": []})
    assert failures == [] and warnings == []


def test_integration_block_escalates_to_failure():
    failures, warnings = evaluate_integration_report({"finalDecision": "BLOCK", "scenarios": []})
    assert failures == ["Integration suite reported BLOCK decision"]
    assert warnings == []


def test_integration_warn_escalates_to_warning():
    failures, warnings = evaluate_integration_report({"finalDecision": "WARN", "scenarios": []})
    assert failures == []
    assert warnings == ["Integration suite reported WARN decision"]


def test_blocked_scenario_reported_with_reason():
    data = {"finalDecision": "BLOCK", "scenarios": [
        {"scenario": "schema-drift", "releaseDecision": "BLOCK", "reason": "type mismatch on orderId"},
        {"scenario": "happy-path", "releaseDecision": "PASS", "reason": ""},
    ]}
    failures, warnings = evaluate_integration_report(data)
    assert any("schema-drift" in f and "orderId" in f for f in failures)
    assert not any("happy-path" in f for f in failures)


def test_warn_scenario_does_not_block():
    data = {"finalDecision": "WARN", "scenarios": [
        {"scenario": "timeout-fallback", "releaseDecision": "WARN", "reason": "fallback used"},
    ]}
    failures, warnings = evaluate_integration_report(data)
    assert failures == []
    assert any("timeout-fallback" in w for w in warnings)


def test_missing_final_decision_defaults_to_pass():
    failures, warnings = evaluate_integration_report({"scenarios": []})
    assert failures == [] and warnings == []
