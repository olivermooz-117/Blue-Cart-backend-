"""Marginal Benefit (MB%) / Cost-Benefit (CB) scoring for product listings.

MB% (0-100) is a weighted composite of price and rating (cheaper/higher-rated
= closer to 100), plus a small bonus for "pay after delivery" since it lowers
the buyer's risk. Delivery cost isn't part of the score — none of the
upstream marketplace APIs reliably expose it, so factoring it in would just
be ranking on noise.

Ratings are Bayesian-adjusted before scoring so a 5.0 with a single review
does not outrank a 4.7 with thousands:

    adjusted = (v * R + m * C) / (v + m)

where R is the listing rating, v is its review count (num_ratings, or
UNKNOWN_COUNT_ASSUMED when the count is unknown but the rating is positive,
or 0 when the rating is 0), m is PRIOR_COUNT and C is the mean rating of
listings that carry a positive rating (DEFAULT_MEAN_RATING when none do).
Adjusted ratings are min-max normalised instead of the raw ones.

CB (0-100) is MB per unit of price, normalised across the current result
set — it surfaces the best value-for-money option, which can differ from the
highest MB% listing if that listing also costs much more.

Both scores are relative to the current search results, not an absolute
scale, so callers (e.g. a filter panel on the frontend) can re-rank the same
data by changing the weights.

Weights are normalised per call: negatives are clamped to 0 and each weight
is divided by the sum so MB% always stays within 0..100. If all weights are
0, DEFAULT_WEIGHTS are used.

Trust is currently constant across listings because none of the upstream
marketplace APIs reliably report pay-on-delivery; it only reflects the
configured per-site default.
"""

DEFAULT_WEIGHTS = {
    "price": 0.5,
    "rating": 0.35,
    "trust": 0.15,
}

PRIOR_COUNT = 25
UNKNOWN_COUNT_ASSUMED = 10
DEFAULT_MEAN_RATING = 3.5


def _normalize(values, reverse=False):
    """Scale a list of numbers to 0-1. `reverse=True` means lower is better."""
    low, high = min(values), max(values)
    if high == low:
        return [1.0 for _ in values]
    scaled = [(v - low) / (high - low) for v in values]
    return [1 - s for s in scaled] if reverse else scaled


def _bayesian_adjusted_rating(rating, num_ratings, mean_rating):
    """Shrink a listing's rating toward the mean by its evidence count."""
    if rating > 0 and num_ratings > 0:
        v = num_ratings
    elif rating > 0:
        v = UNKNOWN_COUNT_ASSUMED
    else:
        v = 0
    return (v * rating + PRIOR_COUNT * mean_rating) / (v + PRIOR_COUNT)


def _normalise_weights(weights):
    """Clamp weights to >= 0 and scale so they sum to 1.

    Falls back to DEFAULT_WEIGHTS when the sum is 0.
    """
    cleaned = {}
    for key, default in DEFAULT_WEIGHTS.items():
        value = weights.get(key, default) if isinstance(weights, dict) else default
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = default
        cleaned[key] = max(0.0, value)
    total = sum(cleaned.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: value / total for key, value in cleaned.items()}


def rank_listings(listings, weights=None):
    """Attach `mb_score`/`cb_score` to each listing, sorted best MB% first."""
    if not listings:
        return []

    weights = _normalise_weights(weights)

    price_scores = _normalize([l["price"] for l in listings], reverse=True)

    positive_ratings = [l["rating"] for l in listings if l.get("rating", 0) > 0]
    mean_rating = (
        sum(positive_ratings) / len(positive_ratings) if positive_ratings else DEFAULT_MEAN_RATING
    )
    adjusted_ratings = [
        _bayesian_adjusted_rating(l.get("rating", 0), l.get("num_ratings", 0), mean_rating)
        for l in listings
    ]
    rating_scores = _normalize(adjusted_ratings)

    mb_raw = []
    for listing, price_score, rating_score in zip(listings, price_scores, rating_scores):
        # Trust = pay-on-delivery bonus plus a smaller component from the
        # normalised rating, so a highly-rated listing without COD still
        # edges a poorly-rated one with it.
        pay_bonus = 1.0 if listing.get("pay_on_delivery") else 0.0
        trust_score = 0.6 * pay_bonus + 0.4 * rating_score
        mb_raw.append(
            min(
                1.0,
                weights["price"] * price_score
                + weights["rating"] * rating_score
                + weights["trust"] * trust_score,
            )
        )

    cb_raw = [mb / listing["price"] for listing, mb in zip(listings, mb_raw)]
    cb_scores = _normalize(cb_raw)

    ranked = [
        {**listing, "mb_score": round(mb * 100, 1), "cb_score": round(cb * 100, 1)}
        for listing, mb, cb in zip(listings, mb_raw, cb_scores)
    ]

    ranked.sort(key=lambda item: item["mb_score"], reverse=True)
    return ranked
