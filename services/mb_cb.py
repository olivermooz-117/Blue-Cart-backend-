"""Marginal Benefit (MB%) / Cost-Benefit (CB) scoring for product listings.

MB% (0-100) is a weighted composite of price, rating and delivery cost
(cheaper/higher-rated/cheaper-delivery = closer to 100), plus a small bonus
for "pay after delivery" since it lowers the buyer's risk.

CB (0-100) is MB per unit of total spend (price + delivery), normalized
across the current result set — it surfaces the best value-for-money option,
which can differ from the highest MB% listing if that listing also costs
much more.

Both scores are relative to the current search results, not an absolute
scale, so callers (e.g. a filter panel on the frontend) can re-rank the same
data by changing the weights.
"""

DEFAULT_WEIGHTS = {
    "price": 0.4,
    "rating": 0.35,
    "delivery_cost": 0.15,
    "trust": 0.10,
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
    delivery_scores = _normalize([l["delivery_cost"] for l in listings], reverse=True)

    mb_raw = []
    for listing, price_score, rating_score, delivery_score in zip(
        listings, price_scores, rating_scores, delivery_scores
    ):
        trust_score = 1.0 if listing.get("pay_on_delivery") else 0.5
        mb_raw.append(
            weights["price"] * price_score
            + weights["rating"] * rating_score
            + weights["delivery_cost"] * delivery_score
            + weights["trust"] * trust_score
        )

    cb_raw = [
        mb / (listing["price"] + listing["delivery_cost"])
        for listing, mb in zip(listings, mb_raw)
    ]
    cb_scores = _normalize(cb_raw)

    ranked = [
        {**listing, "mb_score": round(mb * 100, 1), "cb_score": round(cb * 100, 1)}
        for listing, mb, cb in zip(listings, mb_raw, cb_scores)
    ]

    ranked.sort(key=lambda item: item["mb_score"], reverse=True)
    return ranked