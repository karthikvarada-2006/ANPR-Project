import traceback
from fastapi.testclient import TestClient
from backend.api.main import app

plates = ["DL03NV2244", "KA53AE1276", "DL05VW4401", "KA50QA9345", "TN11YD7305"]
with TestClient(app) as c:
    for p in plates:
        for url in (f"/api/trajectory/{p}?fuzzy=true",
                    f"/api/trajectory/{p}?fuzzy=false",
                    f"/api/trajectory/{p}/export"):
            try:
                r = c.get(url)
                print(r.status_code, url)
            except Exception:
                print("EXCEPTION", url)
                traceback.print_exc(limit=-6)
