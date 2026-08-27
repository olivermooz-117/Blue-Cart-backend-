"""Marginal Benefit (MB%) / Cost-Benefit (CB) scoring for product listings.

MB% (0-100) is a weighted composite of price and rating (cheaper/higher-rated
= closer to 100), plus a small bonus for "pay after delivery" since it lowers
the buyer's risk. Delivery cost isn't part of the score — none of the
upstream marketplace APIs reliably expose it, so factoring it in would just
be ranking on noise.

CB (0-100) is MB per unit of price, normalized across the current result
set — it surfaces the best value-for-money option, which can differ from the
highest MB% listing if that listing also costs much more.

Both scores are relative to the current search results, not an absolute
scale, so callers (e.g. a filter panel on the frontend) can re-rank the same
data by changing the weights.
"""

DEFAULT_WEIGHTS = {
    "price": 0.5,
    "rating": 0.35,
    "trust": 0.15,
}


def _normalize(values, reverse=False):
    """Scale a list of numbers to 0-1. `reverse=True` means lower is better."""
    low, high = min(values), max(values)
    if high == low:
        return [1.0 for _ in values]
    scaled = [(v - low) / (high - low) for v in values]
    return [1 - s for s in scaled] if reverse else scaled


def rank_listings(listings, weights=None):
    """Attach `mb_score`/`cb_score` to each listing, sorted best MB% first."""
    if not listings:
        return []

    weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    price_scores = _normalize([l["price"] for l in listings], reverse=True)
    rating_scores = _normalize([l["rating"] for l in listings])

    mb_raw = []
    for listing, price_score, rating_score in zip(listings, price_scores, rating_scores):
        trust_score = 1.0 if listing.get("pay_on_delivery") else 0.5
        mb_raw.append(
            weights["price"] * price_score
            + weights["rating"] * rating_score
            + weights["trust"] * trust_score
        )

    cb_raw = [mb / listing["price"] for listing, mb in zip(listings, mb_raw)]
    cb_scores = _normalize(cb_raw)

    ranked = [
        {**listing, "mb_score": round(mb * 100, 1), "cb_score": round(cb * 100, 1)}
        for listing, mb, cb in zip(listings, mb_raw, cb_scores)
    ]

    ranked.sort(key=lambda item: item["mb_score"], reverse=True)
    return ranked