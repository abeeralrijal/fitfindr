from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("sneakers", size="9", max_price=None)
    assert all("9" in item["size"].lower() for item in results)


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = suggest_outfit(new_item, get_example_wardrobe())
    assert isinstance(outfit, str)
    assert outfit.strip() != ""


def test_suggest_outfit_empty_wardrobe_does_not_crash():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = suggest_outfit(new_item, get_empty_wardrobe())
    assert isinstance(outfit, str)
    assert outfit.strip() != ""


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_create_fit_card_valid_outfit():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = "Pair it with baggy jeans and chunky sneakers."
    card = create_fit_card(outfit, new_item)
    assert isinstance(card, str)
    assert card.strip() != ""


def test_create_fit_card_empty_outfit_returns_message_not_exception():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    card = create_fit_card("", new_item)
    assert isinstance(card, str)
    assert card.strip() != ""


def test_create_fit_card_whitespace_outfit_returns_message_not_exception():
    new_item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    card = create_fit_card("   ", new_item)
    assert isinstance(card, str)
    assert card.strip() != ""
