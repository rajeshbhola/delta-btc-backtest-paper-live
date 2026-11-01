from datetime import datetime, timezone
from quality_lab.delta_rest import DeltaPublicClient, pages


def d(t): return datetime.fromisoformat(t.replace("Z", "+00:00"))

def test_page_boundary_2000():
    data = list(pages(d("2026-10-31T00:00:00Z"), d("2026-11-02T00:00:00Z"), "1m"))
    assert len(data) == 2
    assert (data[0][1] - data[0][0]) // 60 + 1 == 2000
    assert data[1][0] == data[0][1] + 60
    assert sum((b-a)//60+1 for a,b in data) == 2880


class FakeResponse:
    status_code = 200
    headers = {}
    def raise_for_status(self): pass
    def json(self):
        return {"success":True,"result":[{"time":1793440800,"open":10,"high":11,"low":9,"close":10.5,"volume":3}]}

class FakeSession:
    def get(self, *_args, **kwargs):
        assert kwargs["params"]["symbol"] == "BTCUSD"
        return FakeResponse()


def test_readonly_delta_response():
    client = DeltaPublicClient(session=FakeSession(), pause=0)
    assert client.get("5m", 1793440800, 1793441100)[0]["timestamp_utc"].endswith("Z")
