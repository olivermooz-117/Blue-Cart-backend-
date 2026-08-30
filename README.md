# BlueCart Marketplace

Compares the marginal benefit (MB) and cost-benefit (CB) of buying a product
across multiple e-shops — not just price, but rating, delivery cost, and
payment mode too.

## Structure

- `backend/` — Flask API: fetches/mocks listings per e-shop, scores and ranks
  them, and stores users/search history/reviews in PostgreSQL.
- `frontend/` — React (Vite) + Redux Toolkit app: `components/` for reusable
  UI pieces, `pages/` for screens, `store/` for Redux slices. Routes: `/`
  (landing), `/search?q=` (results + filters + reviews), `/auth`
  (sign in/up), `/history` (a logged-in user's past searches).

## Backend setup

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit DATABASE_URL etc.
flask --app app init-db   # creates tables in Postgres
flask --app app run
```

Runs on `http://localhost:5000`. Key endpoints:

- `GET /api/search?q=<query>` — fetch + rank listings for a query (records
  search history if the caller sends a valid JWT).
- `POST /api/search/filter` — re-rank a given listing set with custom weights.
- `GET /api/search/reviews?q=<query>` — reviews left by previous users.
- `POST /api/search/reviews` — submit a review (`query`, `shop`, `author`,
  `comment`, `rating`). No login required.
- `POST /api/auth/register`, `POST /api/auth/login` — get a JWT.
- `GET /api/history` — a logged-in user's past searches (JWT required).

Prices are mocked in KES (Ksh).

Run tests with `pytest` from `backend/`.

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
  overridden per-request from the frontend's filter panel.
