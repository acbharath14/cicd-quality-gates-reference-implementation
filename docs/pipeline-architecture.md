# Pipeline Architecture

## Stages
1. Build and lint
2. UI smoke verification
3. API smoke verification
4. Performance gate
5. Accessibility gate
6. Release readiness summary

## Design Principles
1. Fast feedback first.
2. Fail on threshold breach.
3. Preserve artifacts for audit and triage.
4. Keep thresholds version-controlled.
