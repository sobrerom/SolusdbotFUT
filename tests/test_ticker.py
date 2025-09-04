import os
os.environ["MOCK_MODE"] = "1"
os.environ["MOCK_DIR"] = "tests/fixtures"

from pionex_api import PionexClient

def test_ticker_mock():
    c = PionexClient("k","s")
    p = c.get_ticker_price("SOLUSDT")
    assert isinstance(p, float)
    assert p > 0
