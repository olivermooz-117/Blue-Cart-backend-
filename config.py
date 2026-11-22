import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(raw):
    """Normalise hosted-provider Postgres URLs to the psycopg2 dialect.

    Render/Heroku-style ``postgres://`` URLs (and bare ``postgresql://``
    without a driver) both become ``postgresql+psycopg2://`` so SQLAlchemy
    2.x can connect with the psycopg2 driver.
    """
    if not raw:
        return raw
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


_raw_database_url = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bluecart"
)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(_raw_database_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Different RapidAPI accounts can be subscribed to different listings, so
    # each site's key defaults to the shared RAPIDAPI_KEY but can be
    # overridden independently if e.g. Amazon and AliExpress come from
    # separate accounts.
    RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
    RAPIDAPI_AMAZON_KEY = os.environ.get("RAPIDAPI_AMAZON_KEY", "") or RAPIDAPI_KEY
    RAPIDAPI_ALIEXPRESS_KEY = os.environ.get("RAPIDAPI_ALIEXPRESS_KEY", "") or RAPIDAPI_KEY
    RAPIDAPI_AMAZON_HOST = os.environ.get(
        "RAPIDAPI_AMAZON_HOST", "real-time-amazon-data.p.rapidapi.com"
    )
    RAPIDAPI_ALIEXPRESS_HOST = os.environ.get(
        "RAPIDAPI_ALIEXPRESS_HOST", "aliexpress-datahub.p.rapidapi.com"
    )

    EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "")
    EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "")

    # No live FX API configured — fixed approximate rate, update as needed.
    USD_TO_KES_RATE = float(os.environ.get("USD_TO_KES_RATE", "130"))

    # Search-result cache TTL (seconds), within the 10-15 minute window.
    SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("SEARCH_CACHE_TTL_SECONDS", "720"))

    # Timeout for an individual marketplace HTTP request. The crawler also
    # applies an overall timeout while collecting the concurrent site results.
    MARKETPLACE_TIMEOUT_SECONDS = int(
        os.environ.get("MARKETPLACE_TIMEOUT_SECONDS", "10")
    )

    # Per-IP rate limiting on the search endpoint.
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

    # Rate limiter storage backend (memory:// by default).
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI") or "memory://"

    # JWT access token lifetime (seconds from env, default 24 hours).
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", "86400"))
    )

    # Optional Redis URL for shared search-result caching and rate limiting.
    # When unset (or Redis is unavailable), the in-memory cache is used.
    REDIS_URL = os.environ.get("REDIS_URL", "")

    # Allowed CORS origins (comma separated).
    CORS_ORIGINS = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,https://blue-cart-frontend.vercel.app"
    )

    # Site-level defaults for `pay_on_delivery` (cash on delivery). None of the
    # upstream marketplace APIs reliably expose payment methods, so these are
    # conservative, operator-overridable defaults rather than live data.
    PAY_ON_DELIVERY_DEFAULTS = {
        "Amazon": os.environ.get("PAY_ON_DELIVERY_AMAZON", "false").lower() == "true",
        "AliExpress": os.environ.get("PAY_ON_DELIVERY_ALIEXPRESS", "false").lower() == "true",
        "eBay": os.environ.get("PAY_ON_DELIVERY_EBAY", "false").lower() == "true",
    }


if os.environ.get("FLASK_ENV") == "production":
    _missing = [
        name
        for name in ("SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL")
        if not os.environ.get(name)
    ]
    if _missing:
        raise RuntimeError(
            "Production requires SECRET_KEY, JWT_SECRET_KEY and DATABASE_URL: "
            f"missing {', '.join(_missing)}"
        )
    for name in ("SECRET_KEY", "JWT_SECRET_KEY"):
        value = os.environ.get(name, "")
        if len(value) < 32:
            raise RuntimeError(
                f"Production {name} must be at least 32 characters long"
            )
