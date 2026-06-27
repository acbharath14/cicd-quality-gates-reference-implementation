# Integration Governance Evidence

## PASS Command

```powershell
python scripts\evaluate_gates.py sample-data\metrics.json sample-data\integration-suite-report-pass.json
```

## PASS Output

```text
All quality gates passed
```

## BLOCK Command (cross-repo)

```powershell
python scripts\evaluate_gates.py sample-data\metrics.json ..\microservices-contract-and-integration-testing\reports\integration-suite-report.json
```

## BLOCK Output

```text
Gate evaluation failed:
- Integration suite reported BLOCK decision
- Scenario 'schema-drift' blocked release: Field 'orderId' expected type 'number' but got 'str'
```
