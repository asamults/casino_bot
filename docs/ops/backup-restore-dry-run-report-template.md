## Backup/restore rehearsal report (TEMPLATE)

Date: YYYY-MM-DD  
Owner: <name>  
Target compose: `docker-compose.prod.yml`  
Env file: `.env.prod.example` / `.env.prod`  

### Objective
Prove the invariant: **a backup can be restored into a clean DB volume and the app becomes ready again**.

### Backup
- Command: `make pg-backup-compose`
- Backup file: `./backups/<file>.dump`
- Backup time: <seconds>

### Restore
- Command: `BACKUP_PATH=./backups/<file>.dump make pg-restore-compose`
- Volume destroyed: YES/NO
- Restore time: <seconds>

### Verification (smoke)
- Command: `make pg-verify-compose`
- Probes (from inside `casino_bot-api`):
  - `/health`: PASS/FAIL
  - `/ready`: PASS/FAIL
  - `/metrics`: PASS/FAIL

### Notes / issues
- <bullets>

### Result
PASS/FAIL

