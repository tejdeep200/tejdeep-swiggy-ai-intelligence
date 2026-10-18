"""Bounded public smoke test: one greeting and one actual analytics question."""
import json
from pathlib import Path
import sys

import httpx

base = (sys.argv[1] if len(sys.argv) > 1 else "https://tejdeep-swiggy-ai-intelligence.vercel.app").rstrip("/")
checks = []
with httpx.Client(timeout=180) as client:
    page = client.get(base)
    assert page.status_code == 200, f"Website returned {page.status_code}"
    checks.append({"check": "website", "status": page.status_code})
    status = client.get(base + "/api/freshness")
    assert status.status_code == 200, f"Freshness returned {status.status_code}: {status.text[:200]}"
    publication = status.json()
    assert publication.get("row_count", 0) > 0, "No published Snowflake data available"
    checks.append({"check": "snowflake_publication", "rows": publication["row_count"], "ai_scope": publication.get("ai_scope")})
    for question in ("hi", "Compare average restaurant ratings by city and cite relevant listing examples."):
        response = client.post(base + "/api/ask", headers={"Origin": base}, json={"question": question, "history": []})
        assert response.status_code == 200, f"Question returned {response.status_code}: {response.text[:200]}"
        result = response.json()
        if question == "hi":
            assert result["answer"].startswith("Hi!") and result["charts"] == []
        else:
            assert result["charts"] and result["charts"][0]["metric"] == "average_rating"
            assert result["charts"][0]["dataset"], "No actual Snowflake chart rows"
            assert result["sources"], "No cloud RAG sources returned"
        checks.append({"check": question, "status": response.status_code, "charts": len(result["charts"]), "sources": len(result["sources"])})
        print(json.dumps(checks[-1]), flush=True)
destination = Path(__file__).resolve().parents[1] / "runtime/public-verification.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps({"url": base, "checks": checks}, indent=2), encoding="utf-8")
print("All public checks passed.")
