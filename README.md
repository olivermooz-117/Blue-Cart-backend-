# BlueCart Marketplace — Backend

Flask API that searches **Amazon, AliExpress, and eBay**, ranks listings with an MB/CB scoring formula, and stores users + search history in PostgreSQL.

**Live API:** https://blue-cart-backend-ynqy.onrender.com

## Features

- Multi-shop product search (Amazon, AliExpress, eBay)
- Marginal Benefit / Cost-Benefit ranking (price, rating, trust/payment safety)
- User authentication (JWT + bcrypt)
- Search history for logged-in users
- Client-side re-ranking via filter weights
- **Product reviews** per search query (guest or linked to a logged-in user)
- In-memory search-result caching with per-query TTL
- Per-IP rate limiting on the search endpoint

## Backend setup

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit DATABASE_URL etc.

# Recommended (managed schema migrations):
flask --app app db migrate -m "message"   # create a migration for model changes
flask --app app db upgrade                # apply migrations to the database

# Local/dev convenience (creates tables directly, bypasses migrations):
flask --app app init-db

flask --app app run
```

Runs on `http://localhost:5000`. Key endpoints:

- `GET /api/search?q=<query>` — fetch + rank listings for a query (records
  search history if the caller sends a valid JWT). Rate-limited per IP.
- `POST /api/search/filter` — re-rank a given listing set with custom weights.
- `GET /api/search/reviews?q=<query>` — reviews left by previous users.
- `POST /api/search/reviews` — submit a review (`query`, `shop`, `author`,
  `comment`, `rating` 1-5). No login required; a valid JWT attaches `user_id`.
- `POST /api/auth/register`, `POST /api/auth/login` — get a JWT.
- `GET /api/history` — a logged-in user's past searches (JWT required).

Prices are mocked in KES (Ksh).

Run tests with `pytest` from `backend/`.

## Environment variables

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `SECRET_KEY` | yes | Flask secret key |
| `JWT_SECRET_KEY` | yes | JWT signing key |
| `RAPIDAPI_KEY` | yes | Shared RapidAPI key (used when site key unset) |
| `RAPIDAPI_ALIEXPRESS_KEY` | no | Per-site RapidAPI key override (AliExpress) |
| `RAPIDAPI_AMAZON_KEY` | no | Per-site RapidAPI key override (Amazon) |
| `RAPIDAPI_AMAZON_HOST` | no | Default `real-time-amazon-data.p.rapidapi.com` |
| `RAPIDAPI_ALIEXPRESS_HOST` | no | Default `aliexpress-datahub.p.rapidapi.com` |
| `EBAY_CLIENT_ID` | no | eBay OAuth2 client ID (Browse API) |
| `EBAY_CLIENT_SECRET` | no | eBay OAuth2 client secret |
| `USD_TO_KES_RATE` | no | Default `130` |
| `SEARCH_CACHE_TTL_SECONDS` | no | Search-result cache TTL in seconds (default `720` = 12 min) |
| `RATE_LIMIT_REQUESTS` | no | Max search requests per IP per window (default `30`) |
| `RATE_LIMIT_WINDOW_SECONDS` | no | Rate-limit window in seconds (default `60`) |
| `REDIS_URL` | no | Optional Redis URL for shared cache + rate limiting. When unset or Redis is unavailable, the in-memory cache is used. Example: `redis://localhost:6379/0` |

A site with no API key configured, or whose request fails, is simply omitted
from results rather than failing the search — see
`backend/services/crawler.py` for details.

## Data models

- `users` — id, email, password_hash, created_at
- `search_history` — id, user_id (FK), search_query, searched_at
- `reviews` — id, query, shop, author, comment, rating (1-5), user_id (nullable FK), created_at
- `search_cache` — query (PK), results (JSON), fetched_at, expires_at
- `user_preferences` — user_id (PK FK), default_weights (JSON), preferred_shops (JSON), updated_at

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env   # then edit VITE_API_URL if needed
npm run dev
```

Runs on `http://localhost:5173` and talks to the backend via `VITE_API_URL`.

## Notes

- `backend/services/crawler.py` calls real external APIs for 3 sites: Amazon
  and AliExpress via RapidAPI-hosted third-party wrappers, and eBay via its
  official Browse API (OAuth2 client-credentials). A site with no API key
  configured, or whose request fails, is simply omitted from results rather
  than failing the search — see `backend/.env.example` for the required vars.
- `backend/services/mb_cb.py` holds the ranking formula; weights can be
  overridden per-request from the frontend's filter panel. The `trust` weight
  now factors in `pay_on_delivery` plus listing rating so it meaningfully
  differentiates products.
- `backend/services/cache.py` provides search-result caching and per-IP rate
  limiting. It uses an in-memory backend by default; set `REDIS_URL` to use a
  shared Redis backend (install `redis` first: `pip install redis`). Redis is
  optional — the app falls back to in-memory if it isn't available.
- Schema changes are managed with Flask-Migrate. Edit models, then run
  `flask --app app db migrate -m "message"` followed by
  `flask --app app db upgrade`. The `init-db` command (db.create_all) is kept
  for local/dev convenience.
