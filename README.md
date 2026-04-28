# BorderFlow

BorderFlow is a submission-ready distributed logistics demo for tracking one container journey across:

- `DEPOT-MSU`
- `BORDER-MB`
- `PORT-DBN`
- `HUB-JHB`
- `CTRL-TOWER`

The system uses one shared FastAPI + Jinja2 codebase, PostgreSQL logical replication for cross-site sync, Celery + Redis for background refresh and health checks, and Docker/K3s deployment scaffolding.

## Stack

- FastAPI + Jinja2
- SQLAlchemy
- PostgreSQL logical replication
- Celery + Redis
- Docker Compose
- K3s templates

## Local preview

Install dependencies:

```powershell
pip install -e .[dev]
```

Run the single-site preview:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Default local login:

- Email: `depot.controller@borderflow.local`
- Password: `borderflow123`

## Full distributed stack

Bring up the five-site Docker environment:

```powershell
docker compose -f infra/docker-compose.yml up --build -d
```

The Compose flow is deterministic:

1. Postgres and Redis containers start.
2. `init-site` runs once for each site.
3. `setup-replication` creates publications, subscriptions, and replication users.
4. APIs and workers start only after bootstrap completes.

Site URLs:

- Depot: `http://localhost:8001`
- Border: `http://localhost:8002`
- Port: `http://localhost:8003`
- Hub: `http://localhost:8004`
- Control Tower: `http://localhost:8005`

## CLI operations

- `python -m app.cli init-site`
- `python -m app.cli refresh-projections`
- `python -m app.cli poll-replication`
- `python -m app.cli setup-replication --topology infra/replication_topology.json --reset`

## Demo and recovery helpers

The Week 6 demo scripts live in [scripts/demo/README.md](scripts/demo/README.md).

Useful commands:

```powershell
.\scripts\demo\Stop-Site.ps1 border
.\scripts\demo\Start-Site.ps1 border
.\scripts\demo\Partition-Site.ps1 port
.\scripts\demo\Heal-Site.ps1 port
python .\scripts\demo\verify_convergence.py
```

## Seeded users

- `depot.controller@borderflow.local`
- `border.agent@borderflow.local`
- `port.agent@borderflow.local`
- `hub.operator@borderflow.local`
- `manager@borderflow.local`

Password for all seeded demo accounts: `borderflow123`

## Key implementation notes

- Shared current state is derived from immutable milestones and handovers through the `container_current_state_v` view plus the `container_state_projection` cache table.
- Depot owns master data and trip planning.
- Border, Port, and Hub own milestones, handovers, and incidents they originate.
- Milestones and handovers are append-only in the PostgreSQL runtime guards migration.
- Replication topology is defined in [infra/replication_topology.json](infra/replication_topology.json).

## K3s

K3s deployment templates and bootstrap notes are in [infra/k8s/README.md](infra/k8s/README.md).

## Project documents

Supporting Word documents are stored in [docs/](docs/):

- [BorderFlow_Week1_Proposal.docx](docs/BorderFlow_Week1_Proposal.docx)
- [Squad_X_Week4.docx](docs/Squad_X_Week4.docx)
- [Squad_X_ERD_and_schema.docx](docs/Squad_X_ERD_and_schema.docx)
