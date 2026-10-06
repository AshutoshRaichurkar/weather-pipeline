# Day 1: Containers and the core CLI

## Key ideas

- **Image:** a read-only template, built from layers. Like a class.
- **Container:** a running instance of an image. Like an object. One image can run many containers.
- **Container vs. VM:** a VM runs a whole guest OS. A container is just a process on the host's kernel, isolated by:
  - **Namespaces:** what the process can *see* (its own processes, network, filesystem, hostname).
  - **cgroups:** what it can *use* (CPU, memory, I/O limits).
- **Registry:** where images are stored. Docker Hub is the default; GHCR is GitHub's.
- **Image names** are `registry/repository:tag`. `postgres:16` is short for `docker.io/library/postgres:16`.
- **Tag vs. digest:**
  - A tag (`postgres:16`) is a label that can move to a newer image. `16` means the newest 16.x.
  - A digest (`postgres@sha256:...`) always points to one exact image.
- **Writable layer:** each container gets a thin writable layer on top of the read-only image layers. Every file it creates or changes lives there.
  - `docker stop` keeps the writable layer, so `docker start` brings the data back.
  - `docker rm` deletes it, so the data is gone. Databases need volumes (Day 4).
- **Port publishing:** `-p HOST:CONTAINER` forwards a port on your machine into the container. Without it, the service is only reachable inside the container's network namespace.

## Commands

```bash
# Run a container
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
#   -d        run in the background (detached)
#   --name    give it a name to refer to
#   -e        set an environment variable
#   -p        publish a port: host 5432 -> container 5432

# See what's there
docker ps                 # running containers only
docker ps -a              # all containers, including stopped and exited ones
docker images             # images on this machine
docker images postgres    # just the postgres images

# Look inside
docker logs pg            # the container's output
docker logs -f pg         # follow the logs live
docker inspect pg         # full JSON config: env, ports, mounts, state
docker inspect postgres:16 --format '{{.RepoDigests}}'   # the digest a tag points to

# Run a command inside a running container
docker exec -it pg psql -U postgres                      # interactive shell (-it)
docker exec pg psql -U postgres -c 'SELECT 1'            # one-off command, no -it

# Lifecycle
docker stop pg            # stop it (keeps the writable layer)
docker start pg           # start it again, data intact
docker rm pg              # delete it (and its writable layer)
docker rm -f pg           # stop and delete in one step
```

## psql cheat sheet

```sql
CREATE SCHEMA raw;
\dn                       -- list schemas
\dt raw.*                 -- list tables in the raw schema
\d raw.hourly_weather     -- describe a table
\x                        -- toggle vertical output for wide rows
\q                        -- quit

SELECT city, count(*) FROM raw.hourly_weather GROUP BY city;
```

## What I built

- `ingest/ingest.py` pulls 7 days of hourly temperatures for 4 cities from Open-Meteo and loads them into `raw.hourly_weather`.
- Connection settings come from environment variables (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`). The defaults point at `localhost:5432`, which works because of `-p 5432:5432`.
- Inserts use `ON CONFLICT ... DO UPDATE` on the `(city, observed_at)` primary key, so reruns are safe (idempotent).
- The script finds Postgres through the published port, not the container name. Names only work as hostnames between containers on the same Docker network (Day 5).

```bash
source venv/bin/activate          # start the virtualenv (deactivate to leave)
python ingest/ingest.py           # load the data
```

## Self-check answers

**Why did the data vanish after removing the container?**

> A container's changes live in its own writable layer on top of the read-only image. `docker rm` deletes that layer, so anything the container wrote is gone. Stopping keeps the data; removing doesn't. That's why stateful services like databases store their data in a volume, which lives outside the container's lifecycle.

**What does `docker ps -a` show that `docker ps` doesn't?**

> `docker ps` lists running containers only. `docker ps -a` includes stopped and exited ones too. It's the first thing I check when a container dies, because the exited container still has its logs and exit code.

## Gotchas

- `localhost` inside a container means the container itself, not your machine.
- A crashed container disappears from `docker ps` but not from `docker ps -a`, and `docker logs` still works on it.
- `postgres` with no tag means `postgres:latest`, which can jump major versions and break data files. Pin at least the major version.
