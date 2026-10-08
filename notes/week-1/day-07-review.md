# Day 7: Catch-up and review

## Objectives

By the end of the day I can:

1. Explain the whole Week 1 stack from one diagram: every service, the network, the volume, and the start order.
2. Clean up *only* this project's Docker resources, without touching other projects on my Mac.
3. Prove the repo is self-contained: a fresh clone runs with nothing but `cp .env.example .env` and `docker compose up`.
4. Explain the design decisions behind the stack, in a README someone else can follow.
5. Answer every Week 1 self-check question without notes.

## 1. Week 1 in one picture

![Weather Pipeline architecture at the end of Week 1: Open-Meteo feeds the ingest job over HTTPS; ingest and dbt jobs connect to the postgres service by name on the Compose network; postgres stores data in the pgdata volume; ./dbt is bind-mounted and .env supplies the password; start order is postgres healthy, then ingest exits 0, then dbt.](../../docs/architecture.svg)

Every part of this picture came from one day:

| Piece | Day | Why it's there |
| --- | --- | --- |
| Containers from images, `-p`, the writable layer | 1 | The basics: what a container is and why its data is fragile |
| `ingest/Dockerfile`, `.dockerignore`, `ENTRYPOINT` | 2 | Package my code with its dependencies; runs the same everywhere |
| Dependencies before code, pip cache mount, `slim` base | 3 | Fast rebuilds, reasonable image size |
| `pgdata` volume, dbt from the official image + bind mount | 4 | Data outlives containers; edit models without rebuilding |
| Network, names as hostnames, no `-p` on Postgres | 5 | Containers talk directly; the database isn't exposed |
| `compose.yml`, `.env`, healthcheck, job ordering | 6 | One command, no secrets in git, no startup races |

> **Real-world analogy:** Like **giving a tour of your own house**: you can walk into every room and say why it's there, without checking the floor plan.

**Why it matters:** in an interview, "walk me through your project" is the most common question. Being able to draw this from memory, and say why each piece exists, is the goal of Week 1.

## 2. Cleaning up safely

![What each cleanup command deletes. compose down removes this project's containers and network; down -v also its pgdata; down -v --rmi local also its built image. system prune removes all stopped containers and dangling images. system prune -a removes all unused images including other projects'. volume prune -a removes all unused named volumes, including other projects' databases.](img/day07-cleanup-scope.svg)

**What it is:** Docker resources (containers, networks, volumes, images, build cache) are shared by every project on the machine. Some cleanup commands are scoped to one Compose project; others sweep the whole machine.

> **Real-world analogy:** Docker on your Mac is **a storage room shared with flatmates** (your other projects). `docker compose down -v --rmi local` **clears your own shelf**. `system prune -a` and `volume prune -a` **clear the whole room**, including your flatmates' boxes.

**Why it matters here:** my Mac also has Airflow, a RAG course and other projects, about 68 GB of images and their database volumes (`rag-project_pgdata`, Airflow's Postgres volumes). `docker system prune -a` or `docker volume prune -a` would delete those too.

- **Safe for Day 7:** `docker compose down -v --rmi local`, run from this folder. Only this project's containers, network, `pgdata` volume, and built ingest image.
- **`docker system prune` (no flags)** is fairly safe: stopped containers, unused networks, dangling images, unused build cache. It doesn't touch named volumes or tagged images.
- **Never casually:** `system prune -a` (all unused images, including 11 GB Airflow builds to re-download or rebuild) and `volume prune -a` (other projects' databases).
- **Check first:** `docker system df` shows what's using space; `docker volume ls` shows whose volumes exist.

## 3. The fresh-clone test

**What it is:** clone the repo into a new folder, as a stranger would, and run it with only the README's instructions.

**Why we do it:** rebuilding in my own folder can hide problems: files that exist on my laptop but were never committed (`.env`, a local image, an untracked file). A fresh clone only has what's in git.

> **Real-world analogy:** It's **testing a recipe by handing it to a friend to cook in their kitchen**. If it only works in your kitchen, you forgot to write down an ingredient (a file that was never committed).

**Why it matters:** "works on my machine" is exactly what Docker is supposed to eliminate. If the clone works, anyone (a reviewer, CI on Day 13, a teammate) can run it.

A clone in a different folder is also a different Compose project (the folder name is the project name), so it gets its own containers, network and volume, and doesn't collide with my working copy.

## 4. Leftovers to fix

- `ingest/ingest.py` still has my Day 3 test edits: `print("Hello World")` and the `!` in `loaded ... rows!`.
- `backups/pgdata.tgz` (4.6 MB, the Day 4 volume backup) is committed and pushed. Database files don't belong in git. Untrack it and ignore `backups/`.
- The old `pgdata` volume (Days 4–5) and the hand-built `weather-ingest` image are unused since Compose took over.

## 5. Week 1 self-check questions

Answer each without looking. Links go to the day's notes for checking afterwards.

1. Why did the data vanish when the container was removed? ([Day 1](day-01-containers-and-cli.md))
2. What does `docker ps -a` show that `docker ps` doesn't? ([Day 1](day-01-containers-and-cli.md))
3. If `ENTRYPOINT` is `["python", "ingest.py"]`, what does `docker run ingest --city boston` execute? ([Day 2](day-02-first-dockerfile.md))
4. Why does copying all code before `pip install` make every rebuild slow? ([Day 3](day-03-layers-and-caching.md))
5. When would you use a bind mount instead of a named volume in production? ([Day 4](day-04-volumes-and-bind-mounts.md))
6. What's the difference between `EXPOSE` and `-p`? ([Day 5](day-05-networking.md))
7. Why isn't plain `depends_on` enough to guarantee Postgres is ready? ([Day 6](day-06-docker-compose.md))

## Design decisions (for the README)

My answers, and what to sharpen:

| Decision | My answer | Sharpen it |
| --- | --- | --- |
| slim, not Alpine | Alpine is lighter but lacks packages | The real reason is **musl vs. glibc**: many Python wheels are glibc-only, so on Alpine pip compiles from source (slow, can fail). Measured: 242 MB vs. 122 MB. |
| No `ports:` on Postgres | Containers using it are inside Docker | Say **Compose network** (not "Docker DNS"), and add *why*: a published DB port is an attack surface. |
| Healthcheck + `service_healthy` | Services take time to initialize | Correct. Precisely: without it Compose only knows *started*; the healthcheck defines *ready*. |
| `.env` + `.env.example` | Real values stay local; template is pushed | Correct. Add: `.env` is git-ignored; `.env.example` has placeholders only. |

Two I didn't know:

**Official dbt image + bind mount.** ingest is *my code*, so I build its image (`COPY . .` bakes the code in, edits need a rebuild). dbt is *someone else's tool*: dbt Labs publishes a tested image, so building my own adds a Dockerfile to maintain for the same result. The bind mount supplies my models at run time, so editing a model needs no rebuild (Day 4, `temp_range_c`). Trade-offs: emulated on Apple Silicon; in production, bake the models into an image so what runs is what was tested.

**`ON CONFLICT DO UPDATE` = idempotency.** Every ingest run fetches overlapping hours (the past 7 days), and ingest reruns on every `docker compose up` and before every `docker compose run dbt`. A plain `INSERT` would fail on the `(city, observed_at)` primary key (or, without one, silently duplicate rows and skew the averages). The upsert updates existing rows instead, so one run or ten give the same table. Idempotent jobs make retries safe: a core data-engineering idea.

## What I did

*(Added at the end of the day.)*

## Quiz results

*(Added at the end of the day.)*
