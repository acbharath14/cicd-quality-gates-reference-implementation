#!/usr/bin/env bash
set -euo pipefail

echo "=== Evaluator unit tests ==="
python -m pytest tests/ -q

echo "=== Gate evaluation (PASS sample) ==="
python scripts/evaluate_gates.py sample-data/metrics.json \
    --junit reports/junit-pass.xml --html reports/readiness-pass.html || true

echo "=== Gate evaluation (WARN sample) ==="
python scripts/evaluate_gates.py sample-data/metrics.json \
    sample-data/integration-suite-report-warn.json \
    --junit reports/junit-warn.xml --html reports/readiness-warn.html || true

echo "=== Reports in reports/ ==="
ls reports/
