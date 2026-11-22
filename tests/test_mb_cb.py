from services.mb_cb import DEFAULT_WEIGHTS, rank_listings


def _listing(site, price, rating, num_ratings=0, pay_on_delivery=False):
    return {
        "site": site,
        "price": price,
        "rating": rating,
        "num_ratings": num_ratings,
        "pay_on_delivery": pay_on_delivery,
    }


def test_rank_listings_prefers_cheaper_higher_rated():
    listings = [
        {
            "site": "X",
            "price": 30098,
            "rating": 4.7,
            "num_ratings": 10,
            "pay_on_delivery": True,
        },
        {
            "site": "Y",
            "price": 29999,
            "rating": 4.0,
            "num_ratings": 4,
            "pay_on_delivery": False,
        },
    ]

    ranked = rank_listings(listings)

    assert len(ranked) == 2
    assert all("mb_score" in item and "cb_score" in item for item in ranked)
    assert ranked[0]["mb_score"] >= ranked[1]["mb_score"]


def test_scores_never_exceed_100():
    listings = [
        _listing("A", 10000, 5.0, 12000),
        _listing("B", 10001, 4.9, 1),
        _listing("C", 10002, 1.0, 50),
    ]
    ranked = rank_listings(listings, weights={"rating": 1, "trust": 1, "price": 1})
    for item in ranked:
        assert item["mb_score"] <= 100
        assert item["cb_score"] <= 100


def test_bayesian_rating_outranks_bare_perfect_rating():
    """A 5.0 with a single rating ranks below a 4.7 with 12000 ratings."""
    listings = [
        _listing("A", 10000, 5.0, 1),
        _listing("B", 10000, 4.7, 12000),
        _listing("C", 10000, 1.0, 0),
    ]
    ranked = rank_listings(listings)
    assert ranked[0]["site"] == "B"
    assert ranked[1]["site"] == "A"


def test_zero_weights_fall_back_to_defaults():
    listings = [
        _listing("A", 10000, 4.0, 10),
        _listing("B", 11000, 4.5, 100),
    ]
    ranked = rank_listings(listings, weights={"price": 0, "rating": 0, "trust": 0})
    defaulted = rank_listings(listings)
    assert [item["mb_score"] for item in ranked] == [item["mb_score"] for item in defaulted]


def test_custom_weights_override_defaults():
    listings = [
        {"site": "A", "price": 10000, "rating": 4.0, "pay_on_delivery": True},
        {"site": "B", "price": 10000, "rating": 4.0, "pay_on_delivery": False},
    ]
    # Zero trust weight -> identical listings tie on MB (same price/rating)
    ranked = rank_listings(listings, weights={"price": 0.5, "rating": 0.5, "trust": 0.0})
    assert ranked[0]["mb_score"] == ranked[1]["mb_score"]


def test_rank_listings_empty_input():
    assert rank_listings([]) == []


def test_trust_weight_differentiates_pay_on_delivery():
    """Two identical listings except pay_on_delivery: COD one ranks higher."""
    listings = [
        {
            "site": "A",
            "price": 10000,
            "rating": 4.0,
            "pay_on_delivery": False,
        },
        {
            "site": "B",
            "price": 10000,
            "rating": 4.0,
            "pay_on_delivery": True,
        },
    ]
    ranked = rank_listings(listings)
    # Same price & rating, but B has pay_on_delivery -> higher trust -> higher MB
    assert ranked[0]["site"] == "B"
    assert ranked[0]["mb_score"] > ranked[1]["mb_score"]


def test_trust_weight_differentiates_rating_when_no_cod():
    """No pay_on_delivery: higher-rated listing should rank higher on trust."""
    listings = [
        {
            "site": "A",
            "price": 10000,
            "rating": 3.0,
            "pay_on_delivery": False,
        },
        {
            "site": "B",
            "price": 10000,
            "rating": 5.0,
            "pay_on_delivery": False,
        },
    ]
    ranked = rank_listings(listings)
    assert ranked[0]["site"] == "B"
    assert ranked[0]["mb_score"] > ranked[1]["mb_score"]


def test_custom_weights_override_defaults():
    listings = [
        {"site": "A", "price": 10000, "rating": 4.0, "pay_on_delivery": True},
        {"site": "B", "price": 10000, "rating": 4.0, "pay_on_delivery": False},
    ]
    # Zero trust weight -> identical listings tie on MB (same price/rating)
    ranked = rank_listings(listings, weights={"price": 0.5, "rating": 0.5, "trust": 0.0})
    assert ranked[0]["mb_score"] == ranked[1]["mb_score"]
