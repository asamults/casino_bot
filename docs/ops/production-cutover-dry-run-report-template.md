## Production cutover dry-run report (TEMPLATE)

Date: YYYY-MM-DD  
Owner: <name>  
Target SHA/tag: <sha or vX.Y.Z>  
Domain: <api.example.com>  

### Preflight
- Env contract validation: PASS/FAIL
- Secrets inventory reviewed: PASS/FAIL
- DB backup plan confirmed: PASS/FAIL

### DNS
- TTL reduced: PASS/FAIL (value)
- Rollback DNS target identified: PASS/FAIL

### TLS / reverse proxy
- TLS configured: PASS/FAIL (Let’s Encrypt / existing)
- `/metrics` policy enforced: PASS/FAIL (401/403 without auth; 200 with auth)
- TrustedHost/Host header validated: PASS/FAIL

### Smoke
Results (via proxy/domain):
- `/health`: PASS/FAIL
- `/ready`: PASS/FAIL
- `/metrics`: PASS/FAIL
- Legacy deprecation headers: PASS/FAIL

### Rollback readiness
- Rollback plan reviewed: PASS/FAIL
- Verification steps executed: PASS/FAIL

### Notes / issues found
- <bullet list>

### Decision
Ready for production cutover: YES/NO  

