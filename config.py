import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt")
    # Some hosted Postgres providers (e.g. Render, Heroku-style) hand out
    # "postgres://" URLs, which SQLAlchemy 1.4+ rejects — normalize to
    # "postgresql://".
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bluecart"
    ).replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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

    # Per-IP rate limiting on the search endpoint.
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

    # Optional Redis URL for shared search-result caching and rate limiting.
    # When unset (or Redis is unavailable), the in-memory cache is used.
    REDIS_URL = os.environ.get("REDIS_URL", "")

    # Site-level defaults for `pay_on_delivery` (cash on delivery). None of the
    # upstream marketplace APIs reliably expose payment methods, so these are
    # conservative, operator-overridable defaults rather than live data.
    # Set e.g. PAY_ON_DELIVERY_ALIEXPRESS=true in the environment to flip a site.
    PAY_ON_DELIVERY_DEFAULTS = {
        "Amazon": os.environ.get("PAY_ON_DELIVERY_AMAZON", "false").lower() == "true",
        "AliExpress": os.environ.get("PAY_ON_DELIVERY_ALIEXPRESS", "false").lower() == "true",
        "eBay": os.environ.get("PAY_ON_DELIVERY_EBAY", "false").lower() == "true",
    }
