# BorderFlow K3s Notes

The manifests in this folder are lightweight deployment templates for K3s.

## What is included

- `namespace.yaml`
- `site-stack.yaml` for one operational site stack
- `control-tower-stack.yaml` for the manager site

Each stack now uses an explicit bootstrap job that runs:

```text
python -m app.cli init-site
```

instead of relying on the API pod to create schema on startup.

## Replication setup in K3s

The repo's default topology file, [infra/replication_topology.json](/C:/Users/ACER/Downloads/BorderLine/infra/replication_topology.json), is wired for the Docker Compose hostnames.

For K3s, copy that file and replace the hostnames with your in-cluster service DNS names before running:

```text
python -m app.cli setup-replication --topology <your-k3s-topology.json> --reset
```

That keeps the K3s topology aligned with the same deterministic bootstrap flow used in Docker Compose.
