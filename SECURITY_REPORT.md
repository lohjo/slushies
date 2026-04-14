## Security Review - platform

### Findings

| Severity | Area | Issue | Fix |
|---|---|---|---|
| HIGH | Webhook Auth | Production with empty webhook secret could allow unauthenticated form-submit calls. | Enforce fail-closed secret check in production; return 401 when secret missing/mismatch. |
| MEDIUM | Access Control | Registration path previously allowed role escalation via client-controlled role value. | Force server-side role assignment and restrict admin creation flow. |
| MEDIUM | Supply Chain | Dashboard loaded external React scripts without integrity pinning. | Remove external CDN dependency; serve local widget script only. |
| LOW | Ops Safety | init-db command could bypass migration history in production. | Block init-db in production; require flask db upgrade. |

### PDPA Compliance Assessment
Pass. Current models store anonymous participant code and psychometric data without direct personal identifiers (no NRIC, phone, name, or email on participant records).

### Launch Verdict
YES - no unresolved HIGH findings remain.
