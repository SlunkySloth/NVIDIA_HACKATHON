# Operating the demo

Use one API worker per data directory. SQLite and the durable queue live in the
separate persistent disk, alongside exact evidence and public recordings. The
application container is non-root, read-only except for `/data` and temporary
files. The sandbox observer is a separate privileged observer that executes
candidate code as `nobody`; no inference or cloud credentials enter its image.

Check `https://YOUR_DOMAIN/health` and `docker compose ... ps`. A healthy API
does not establish model/Sandbox readiness; use the saved live preflight and a
fresh completed live investigation. Review bounded container logs locally and
avoid publishing provider diagnostics or private configuration.

Each run defaults to a 480-second deadline, 40,000 reserved/charged model tokens,
at most two candidate attempts, and bounded replay/scenario work. The single
queue defaults to eight waiting jobs. These are limits per run, not per visitor
or per day. Public sessions can initiate additional runs; monitor actual usage
and account quotas. Read-only recordings provide evidence without new spend.
Stop the app if you need to suspend new investigations. A provider error yields
an inconclusive result rather than a verified patch.

## Backups and restoration

The backup command uses SQLite's consistent backup API and includes complete
evidence and public recordings. It refuses to overwrite a file and produces a
private ZIP with a hash manifest. Copy backups off the host using a private
channel and retain only as needed. Check `missing_artifacts` is empty.

```bash
sudo mkdir -p /srv/replaylab/data/backups
sudo chown 10001:10001 /srv/replaylab/data/backups
sudo docker compose --env-file /srv/replaylab/hosting.env -f deploy/compose.yaml exec -T app \
  python -m replaylab.cli backup --output /data/backups/replaylab-2026-10-13.zip
```

Restore only trusted backups into an empty data directory while the app is
stopped. Verify the metadata hash in `backup-manifest.json`, restore `metadata.sqlite`,
`artifacts/`, and `recordings/`, then set owner 10001:10001. Runtime credentials
and TLS state require separate private recovery; they are excluded from backup.
Do not restore SQLite WAL/SHM from a running server over a consistent snapshot.

## Updates, rollback, and recovery

Back up first, stop the app, switch to a clean reviewed source revision, rebuild
the Sandbox image if its fingerprint changed, and repeat live preflight before
starting. Preserve the previous checkout/image and configuration for rollback.
An API restart marks an interrupted active run inconclusive. Retry from a new
clean investigation; ReplayLab does not silently resume candidate execution.
Saved evidence remains available. `docker compose down` does not delete bind
mounted data. Do not remove `/srv/replaylab` or the persistent disk as routine
cleanup. Terraform changes that replace the VM can still interrupt service.
