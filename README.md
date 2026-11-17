# Review Analyzer

Analysis of online reviews of companies and their branches. The user picks a company or a branch and gets a dashboard with the overall rating, a comparison of sources (Google Maps, Firmy.cz), sentiment over time, review topics, an explanation of drops and suggestions for improvement.

The project is still in the design phase.

- [High-level specification](docs/specification.md)
- [Agentic development: rules and checks](docs/agentic-development.md)
- [Git conventions and rules](docs/agents/git.md)

## Run locally

The real backend and the web run on your laptop with your own keys. No Cloud Tasks and no cloud database: Runs go through an in-process queue and the data live in PostgreSQL in Docker. Messages wait in memory, so a Run that is queued when you stop the backend is lost; start it again from the web. Runs are handled one at a time, and a failing Run is tried again up to 5 times, 5 seconds apart, before it is given up (it then keeps its last status until you start it again).

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Docker, Node.js (for the web).

**Keys and settings:** copy the template and fill it in. `.env` is never committed.

```bash
cp .env.example .env
```

- `DATABASE_URL`: set it to `postgresql://review_analyzer:review_analyzer@localhost:5433/review_analyzer`, which matches `docker-compose.yml`.
- `GOOGLE_PLACES_API_KEY`, `ANTHROPIC_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`: your own keys.
- `DEMO_TOKENS`: any string you choose; it is the access token for the web.
- Delete the five lines `CLOUD_TASKS_PROJECT`, `CLOUD_TASKS_LOCATION`, `CLOUD_TASKS_QUEUE`, `WORKER_URL` and `WORKER_SERVICE_ACCOUNT`. With none set, the local queue is used; with only some set, the backend refuses to start.
- Add the line `WORKER_AUTH_DISABLED=true`: the worker app is not used locally, and without its Cloud Tasks audience the backend refuses to start unless the check is switched off this way.

**Commands** (in this order, the first three in the repo root):

```bash
make db
```

```bash
make migrate
```

```bash
make run-api
```

```bash
cd web && npm install && npm run dev
```

`make db` starts PostgreSQL and waits until it is ready. `make migrate` applies the migrations from `app/storage/migrations` (the backend also applies them on start, so it is safe to skip). `make run-api` starts the backend on port 8000; the web dev server proxies `/api` to it.

**Where to open the app:** `http://localhost:5173/?token=<one value of DEMO_TOKENS>`. The token is kept for the tab and removed from the address bar.

**What costs money:** every Run calls paid services with your keys: Apify (scraping the Reviews), the model provider (classification, Taxonomy and insights) and Google Places (search). Set spending limits at each provider first and try a branch with few Reviews. Langfuse and PostgreSQL in Docker cost nothing here. The cost of a Run is shown in the app and is recorded in the Call log.

**As one container** (what Cloud Run will run): `docker build -t review-analyzer .`, then `docker run --rm -p 8080:8080 --add-host host.docker.internal:host-gateway --env-file .env review-analyzer`. In `.env` point `DATABASE_URL` at `host.docker.internal:5433` and set `WORKER_AUTH_DISABLED=true`. Open `http://localhost:8080/?token=<one value of DEMO_TOKENS>`: the web is served from `/`, the API from `/api`, `/admin/*` and `/tasks/run` reach the backend.

To stop and clean up: `docker compose down` (add `-v` to delete the local data).

![Architecture](docs/images/architecture.png)
