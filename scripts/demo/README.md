# BorderFlow Demo Ops

These scripts support the Week 6 recovery demo against the full Docker Compose topology.

## Bring up the stack

```powershell
docker compose -f infra/docker-compose.yml up --build -d
```

The Compose file bootstraps each site, then runs replication setup, then starts the APIs and workers.

## Simulate a subscriber outage

Stop a site's app and worker:

```powershell
.\scripts\demo\Stop-Site.ps1 border
.\scripts\demo\Start-Site.ps1 border
```

## Simulate a database partition

Disconnect a site's Postgres container from the shared Docker network:

```powershell
.\scripts\demo\Partition-Site.ps1 port
.\scripts\demo\Heal-Site.ps1 port
```

## Inspect convergence

```powershell
python .\scripts\demo\verify_convergence.py
```

Use the convergence output together with the Control Tower UI on `http://localhost:8005` to show that replicated state catches up after recovery.
