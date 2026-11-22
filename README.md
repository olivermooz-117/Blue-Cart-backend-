# BlueCart Marketplace Backend

Flask API for searching Amazon, AliExpress, and eBay, ranking listings, and
storing users, search history, and product reviews.

## Local setup

Run these commands from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Set `DATABASE_URL` in `.env` to a local PostgreSQL database or a SQLite
database, for example `sqlite:///bluecart.db`. Set local-only values for
`SECRET_KEY` and `JWT_SECRET_KEY` (production requires strong keys). Then
initialize the database and start the API:

```bash
flask --app app db upgrade
flask --app app run
```

The API listens on `http://localhost:5000`. `flask --app app init-db` remains
available for local development, but migrations are preferred.

## API behavior

- `GET /api/search?q=<query>` fetches and ranks marketplace listings. A valid
  JWT records the search in that user's history; missing, invalid, expired,
  revoked, or deleted-user tokens are treated as guest access.
- `POST /api/search/filter` accepts a JSON object containing a listing array
  and optional `weights` object, then returns the re-ranked results. Invalid
  filter payloads receive a `400` response.
- `GET /api/search/reviews?q=<query>` returns reviews for a query.
- `POST /api/search/reviews` creates a review. Login is optional; a valid JWT
  associates the review with the user, and otherwise the supplied guest author
  is used.
- `POST /api/auth/register` and `POST /api/auth/login` issue JWTs.
- `GET /api/history` requires a valid JWT.

Search and review query strings are limited to 255 characters. Marketplace
prices are converted from USD to KES using `USD_TO_KES_RATE`; they are not
mocked.

## Marketplace credentials

Live marketplace results require external API credentials:

- Amazon and AliExpress use third-party RapidAPI wrappers. Set
  `RAPIDAPI_KEY`, or provide the site-specific
  `RAPIDAPI_AMAZON_KEY` and `RAPIDAPI_ALIEXPRESS_KEY` values.
- eBay uses the Browse API and requires `EBAY_CLIENT_ID` and
  `EBAY_CLIENT_SECRET`.

Credentials are optional for starting the API and running tests. A site with
missing credentials or an upstream failure contributes no listings. Tests
mock external HTTP calls and do not send real marketplace requests.

## Cache and rate limits

Search results use `SEARCH_CACHE_TTL_SECONDS` (default 720 seconds). The
application uses Redis when `REDIS_URL` is configured and reachable. If Redis
is unset, unavailable, or returns an error, the application falls back to a
bounded in-memory cache; that fallback is process-local and is not shared
between workers. Redis is installed as a production dependency, but a Redis
server is optional.

`RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` configure the per-IP
limit for `GET /api/search` (defaults: 30 requests per 60 seconds). The other
routes retain their separate endpoint limits. Rate-limit storage is configured
independently with `RATELIMIT_STORAGE_URI` and defaults to `memory://`; setting
`REDIS_URL` alone does not move rate-limit storage to Redis.

`MARKETPLACE_TIMEOUT_SECONDS` (default 10) bounds each upstream HTTP request.
The crawler also retains its 15-second overall collection timeout.

`CORS_ORIGINS` is a comma-separated allowlist. The local frontend origin
`http://localhost:5173` is also allowed.

See [.env.example](./.env.example) for all supported environment variables.

## Production database migrations

Create and review migration revisions in a development environment, commit
them with the release, then back up the production database and apply the
revisions during deployment:

```bash
flask --app app db upgrade
gunicorn app:app
```

For an existing database that predates migrations, first verify that its
schema exactly matches the `0001_baseline` migration. Only then, and after a
verified backup, stamp the baseline and apply later migrations:

```bash
flask --app app db stamp 0001_baseline
flask --app app db upgrade
```

Do not stamp databases with a different schema. Configure production
credentials and deployment hooks in the hosting platform; this repository's
CI workflow tests and validates the code but does not deploy it.
