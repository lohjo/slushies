# Launch Security Report — 2026-04-15

## Scope
- Traceback fixed: production startup crash from missing env-name compatibility.
- Files validated:
  - app/config.py
  - tests/test_pipeline_and_config.py
  - .github/workflows/Ci.yml

## Validated
- Production config now accepts `DATABASE_URL` or `SQLALCHEMY_DATABASE_URI`.
- App still fails closed when neither env var exists.
- Existing production safeguard unchanged: warning on default secret key.
- CI now has fail-early production bootstrap preflight.

## Remaining Risk
- Runtime still depends on deploy platform injecting one DB URI env var correctly.
- Separate pre-existing test failure in row parsing domain exists (`test_parse_row_partial_submission_is_safe`) and is unrelated to this traceback fix.

## Security Notes
- No secrets added to repository.
- No auth boundary relaxation.
- No endpoint exposure changes.

## Launch Verdict
APPROVED WITH CONDITIONS

## Conditions
- Deployment environment must set either `DATABASE_URL` or `SQLALCHEMY_DATABASE_URI`.
- Resolve unrelated parse-row test failure before broad release gate uses full test suite as hard blocker.
