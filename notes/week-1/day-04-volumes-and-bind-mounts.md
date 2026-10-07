# Day 4: Volumes and bind mounts

## Key ideas

- **The problem (Day 1):** container data lives in the writable layer, and `docker rm` deletes it. Mounts store data **outside** the container.

| Type | Syntax | Data lives | Managed by | Typical use |
| --- | --- | --- | --- | --- |
| **Named volume** | `-v pgdata:/var/lib/postgresql/data` | Docker's storage area | Docker | Database files, data the app owns |
| **Bind mount** | `-v "$(pwd)/dbt:/usr/app/dbt"` | A folder you choose on the host | You | Source code in dev, config, certs, logs |
| **tmpfs** | `--tmpfs /tmp` | Memory only, gone on stop | Docker | Scratch space, sensitive temp files (Day 10) |

- **Docker tells them apart by the first part of `-v`:** a name (`pgdata`) is a volume; a path starting with `/` is a bind mount.
- **Named volume:** the container is disposable, the data isn't. Recreate the container with the same `-v pgdata:...` and the data is back.
- **Bind mount:** two-way and live. The container sees host edits instantly; files the container writes appear on the host (dbt's `target/` and `logs/`).
- **`:ro`** at the end of a mount makes it read-only inside the container. Standard for config files.
- **Where volumes live on a Mac:** `docker volume inspect` says `/var/lib/docker/volumes/pgdata/_data`, but that path is inside Docker Desktop's Linux VM (containers need a Linux kernel). On the Mac, the whole VM is one disk file (`~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw`). On a Linux server, the path is real.
- **UID/permission issues:** a container user (e.g. UID 999) writing into a host folder owned by another UID can get "permission denied" or leave root-owned files. Docker Desktop on Mac mostly hides this; Linux servers don't.
- **Backups:** mount the volume and a host folder into a throwaway container and `tar` one into the other. For databases, `pg_dump` is safer than copying live data files.

## Official images vs. building your own

| | ingest | dbt | postgres |
| --- | --- | --- | --- |
| Image | `weather-ingest` | `ghcr.io/dbt-labs/dbt-postgres:1.9.latest` | `postgres:16` |
| Built by | Me (`docker build`) | dbt Labs | Postgres maintainers |
| Gets here by | Building locally | Pull | Pull |
| My code is | Baked in (`COPY . .`) | Supplied at run time (bind mount) | n/a |

- `docker run` pulls an image automatically if it's not on the machine. `docker pull` does it explicitly.
- Write a Dockerfile only when you need your own code or packages inside. It usually starts `FROM` an existing image.
- `docker run` = `docker create` + `docker start`. Every run makes a new container; `--rm` deletes it when it exits. The dbt container only exists for the seconds `dbt run` takes.

## dbt runs in three places

| What | Where |
| --- | --- |
| dbt itself (Python, dbt-core, adapter) | Inside the `dbt-postgres` container |
| My project files (models, `dbt_project.yml`, `profiles.yml`) | On my Mac in `dbt/`, bind-mounted to `/usr/app/dbt` |
| The SQL | Executed inside the `pg` container. dbt is just a client. |

- `run` at the end of the command is an argument to the image's `ENTRYPOINT ["dbt"]`, so it runs `dbt run` (Day 2).
- `profiles.yml` sits in the project and uses `env_var('DB_HOST', 'localhost')`. dbt checks the current folder for `profiles.yml` first.
- Schemas come out as `analytics_staging` / `analytics_marts`: dbt joins the profile's `schema` with each model's `+schema`.
- Editing a model needs **no rebuild**, unlike ingest, because the container reads my files directly.

## Apple Silicon and `--platform`

The official dbt image has no `linux/arm64` build:

```
no matching manifest for linux/arm64/v8 in the manifest list entries
```

`--platform linux/amd64` runs the x86 image through emulation on Docker Desktop. Slower, but works. Alternative: build your own (`FROM python:3.12-slim` + `RUN pip install dbt-postgres`), which runs natively.

## Commands

```bash
# Volumes
docker volume create pgdata
docker volume ls
docker volume inspect pgdata
docker volume rm pgdata                      # deletes the data for real

# Postgres with a named volume
docker run -d --name pg \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16

# Prove it survives: remove, recreate with the same volume, count again
docker rm -f pg                              # -f = stop + remove
docker exec pg psql -U postgres -c "SELECT count(*) FROM raw.hourly_weather"

# Look inside a volume
docker run --rm -v pgdata:/data alpine ls -la /data

# dbt from the official image, project bind-mounted
docker run --rm --platform linux/amd64 \
  -v "$(pwd)/dbt:/usr/app/dbt" \
  -e DB_HOST=host.docker.internal \
  ghcr.io/dbt-labs/dbt-postgres:1.9.latest run

# Run something else in the dbt image (replace the entrypoint)
docker run --rm --platform linux/amd64 -v "$(pwd)/dbt:/usr/app/dbt" \
  --entrypoint ls ghcr.io/dbt-labs/dbt-postgres:1.9.latest -la /usr/app/dbt

# Back up a volume to a host folder
mkdir -p ~/backups
docker run --rm -v pgdata:/data -v ~/backups:/backup alpine \
  tar czf /backup/pgdata.tgz -C /data .

# Clean up stopped containers
docker container prune
```

## What I built

- Postgres now runs with the named volume `pgdata`. Data survived deleting and recreating the container (768 rows).
- `dbt/` project:
  - `models/sources.yml`: source `raw.hourly_weather`
  - `models/staging/stg_hourly_weather.sql`: view, adds `observed_date`, drops null temps
  - `models/marts/daily_weather_summary.sql`: table, per city per day min/max/avg/range and hours observed (32 rows: 4 cities × 8 days)
- `.gitignore`: `dbt/target/`, `dbt/logs/`, `dbt/.user.yml`
- Added `temp_range_c` live, no rebuild.

## Self-check answer

**When would you use a bind mount instead of a named volume in production?**

> I use named volumes for data the application owns, like database files, because Docker manages them and they're portable. I'd use a bind mount in production when the host owns the files: config or TLS certificates managed outside the container, usually mounted read-only, or a specific host path for logs, backups or a particular disk. Bind-mounting source code is a development pattern; in production the code belongs in the image.

My answer was "to keep the backup on my local." Backups to a known host path are a valid case, but a narrow one, and "local" in production means the server, not my laptop. The main reason is host-managed files, especially config.

| Production use | Example |
| --- | --- |
| Config files | `-v /etc/nginx/nginx.conf:/etc/nginx/nginx.conf:ro` |
| TLS certificates | `-v /etc/letsencrypt:/certs:ro` |
| Logs for a host agent | `-v /var/log/myapp:/app/logs` |
| A specific disk | `-v /mnt/ssd/data:/data` |
| Backups/exports | `-v /backups:/backup` |

## Gotchas

- `REAL` (float4) can't store most decimals exactly. `max - min` gave `3.9999998092651374`; wrap it in `round((...)::numeric, 1)`. Cast the whole expression, not one side.
- `docker rm -f pg` doesn't touch `pgdata`. `docker volume rm pgdata` (or `docker compose down -v` later) does.
- Images show as an ID instead of a name when you rebuild: the name moved to the new image, and old containers still point at the old one.
- Containers run without `--rm` pile up as `Exited` in `docker ps -a`. Clean them with `docker container prune`.
- If `psql` says `the database system is starting up`, wait a few seconds after starting the container.
