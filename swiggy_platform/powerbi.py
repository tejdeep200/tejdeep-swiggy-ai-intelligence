"""Only configured report IDs can be embedded or refreshed."""
import json
import os
import time
from pathlib import Path

import httpx

from .config import ROOT


def catalog():
    return json.loads(Path(os.getenv("POWERBI_CATALOG_PATH", str(ROOT / "config/powerbi_reports.json"))).read_text())


def report_by_key(key):
    for report in catalog():
        if report["key"] == key:
            return report
    raise ValueError("Report is not in the authorized catalog")


def access_token():
    tenant = os.environ["POWERBI_TENANT_ID"]
    import uuid
    uuid.UUID(tenant)
    response = httpx.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data={
        "grant_type": "client_credentials", "client_id": os.environ["POWERBI_CLIENT_ID"],
        "client_secret": os.environ["POWERBI_CLIENT_SECRET"],
        "scope": "https://analysis.windows.net/powerbi/api/.default",
    }, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def request(method, path, **kwargs):
    token = access_token()
    for attempt in range(5):
        response = httpx.request(method, "https://api.powerbi.com/v1.0/myorg/" + path,
                                headers={"Authorization": "Bearer " + token}, timeout=60, **kwargs)
        if response.status_code not in (429, 502, 503, 504):
            response.raise_for_status()
            return response
        time.sleep(min(float(response.headers.get("Retry-After", 2 ** attempt)), 60))
    response.raise_for_status()


def embed(key):
    report = report_by_key(key)
    path = f"groups/{report['workspace_id']}/reports/{report['report_id']}"
    metadata = request("GET", path).json()
    token = request("POST", path + "/GenerateToken", json={"accessLevel": "View", "allowSaveAs": False}).json()
    return {"id": report["report_id"], "embedUrl": metadata["embedUrl"],
            "accessToken": token["token"], "expiration": token["expiration"],
            "pages": report.get("pages", []), "visuals": report.get("visuals", []),
            "filter_targets": report.get("filter_targets", {})}


def refresh_all():
    results = []
    for report in catalog():
        if report.get("mode", "Import") == "DirectQuery":
            results.append({"key": report["key"], "mode": "DirectQuery", "status": "source_validated"})
            continue
        path = f"groups/{report['workspace_id']}/datasets/{report['dataset_id']}/refreshes"
        # Reattach to an active refresh after task retries rather than submitting twice.
        before = request("GET", path, params={"$top": 1}).json().get("value", [])
        active = before and before[0].get("status") in ("Unknown", "InProgress")
        previous = before[0].get("requestId") if before else None
        if not active:
            request("POST", path, json={"notifyOption": "NoNotification"})
        deadline = time.monotonic() + int(os.getenv("POWERBI_REFRESH_TIMEOUT", "1800"))
        while time.monotonic() < deadline:
            rows = request("GET", path, params={"$top": 1}).json().get("value", [])
            if rows and (active or rows[0].get("requestId") != previous):
                status = rows[0].get("status")
                if status == "Completed":
                    results.append({"key": report["key"], "status": status, "last_refresh": rows[0].get("endTime")})
                    break
                if status in ("Failed", "Cancelled", "Disabled"):
                    raise RuntimeError("Power BI refresh failed for " + report["key"])
            time.sleep(15)
        else:
            raise TimeoutError("Power BI refresh did not complete")
    return results
