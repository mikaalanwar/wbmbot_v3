from wbmbot_v3.utility import eligibility


class DummyElement:
    def __init__(self, text: str):
        self.text = text


class DummyFlat:
    def __init__(self, *, wbs=False, total_rent="600 €", size="60 m²", rooms="2"):
        self.title = "Test Flat"
        self.wbs = wbs
        self.total_rent = total_rent
        self.size = size
        self.rooms = rooms


class DummyUser:
    def __init__(self, *, exclude=None, wbs=False, rent="700", size="50", rooms="1"):
        self.exclude = exclude or []
        self.wbs = wbs
        self.flat_rent_below = rent
        self.flat_size_above = size
        self.flat_rooms_above = rooms


def test_evaluate_flat_eligibility_returns_exclude_reason():
    allowed, reason = eligibility.evaluate_flat_eligibility(
        DummyElement("Contains WBS keyword"),
        DummyFlat(),
        DummyUser(exclude=["wbs"]),
    )

    assert allowed is False
    assert reason == "it contains exclude keyword(s) --> wbs"


def test_evaluate_flat_eligibility_returns_threshold_reason():
    allowed, reason = eligibility.evaluate_flat_eligibility(
        DummyElement("Regular listing"),
        DummyFlat(total_rent="900 €", size="40 m²", rooms="1"),
        DummyUser(rent="800", size="50", rooms="2"),
    )

    assert allowed is False
    assert "rent doesn't match our criteria" in reason


def test_evaluate_flat_eligibility_returns_allowed_when_matching():
    allowed, reason = eligibility.evaluate_flat_eligibility(
        DummyElement("Regular listing"),
        DummyFlat(),
        DummyUser(),
    )

    assert allowed is True
    assert reason is None
