from services.mb_cb import rank_listings


def test_rank_listings_prefers_cheaper_higher_rated():
    listings = [
        {
            "site": "X",
            "price": 30098,
            "delivery_cost": 200,
            "rating": 4.7,
            "num_ratings": 10,
            "pay_on_delivery": True,
        },
        {
            "site": "Y",
            "price": 29999,
            "delivery_cost": 150,
            "rating": 4.0,
            "num_ratings": 4,
            "pay_on_delivery": False,
        },
    ]

    ranked = rank_listings(listings)

    assert len(ranked) == 2
    assert all("mb_score" in item and "cb_score" in item for item in ranked)
    assert ranked[0]["mb_score"] >= ranked[1]["mb_score"]


def test_rank_listings_empty_input():
    assert rank_listings([]) == []