import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from swiggy_platform import analytics, pipeline, powerbi


def test_sql_filters_are_bound_not_interpolated():
    sql, params = analytics.compile_sql({"city": "Mumbai'; DROP TABLE x;--"}, "SNAP_A1")
    assert "DROP" not in sql
    assert params == ["%Mumbai'; DROP TABLE x;--%"]
    assert "COUNT(*)" in sql and "SNAP_A1.DIM_RESTAURANTS" in sql


@pytest.mark.parametrize("plan", [{"metric": "revenue"}, {"dimension": "city;DROP"}, {"limit": 9999}])
def test_unsupported_sql_plan_rejected(plan):
    with pytest.raises(ValidationError):
        analytics.compile_sql(plan, "SNAP_A1")


def test_snapshot_identifier_cannot_inject():
    with pytest.raises(ValueError):
        analytics.compile_sql({}, "bad;DROP")


def test_content_hash_is_stable_and_detects_changes():
    assert pipeline.content_hash({"a": 1, "b": 2}) == pipeline.content_hash({"b": 2, "a": 1})
    assert pipeline.content_hash({"a": 1}) != pipeline.content_hash({"a": 2})


def test_source_validation_blocks_missing_and_empty_files():
    with pytest.raises(ValueError):
        pipeline.validate_files([])
    with pytest.raises(ValueError):
        pipeline.validate_files([{"configured": True, "files": [{"name": "cities.csv", "size": 0}]}])
    files = [{"name": t + ".csv", "size": 42} for t in ("cities", "cuisines", "restaurants", "restaurant_cuisines")]
    assert pipeline.validate_files([{"configured": True, "files": files}]) == {"files": 4}


def test_adls_directory_markers_are_not_source_files(monkeypatch):
    monkeypatch.setattr(pipeline, "query", lambda *args: [
        {"name": "raw/restaurants", "size": 0},
        {"name": "raw/restaurants_1.csv", "size": 12},
    ])
    assert pipeline.check_stage("SWIGGY.RAW.STAGE")["files"] == [{"name": "raw/restaurants_1.csv", "size": 12}]


def test_quality_failure_does_not_publish(monkeypatch):
    collection = Mock()
    collection.count.return_value = 4
    client = Mock()
    client.get_collection.return_value = collection
    monkeypatch.setattr(pipeline, "chroma", lambda: client)
    monkeypatch.setattr(pipeline, "query", lambda *a: [{"n": 5}])
    with pytest.raises(ValueError):
        pipeline.validate_index({"collection": "snap_a", "schema": "SNAP_A", "rows": 5})


def test_unsupported_metric_has_no_query_or_retrieval(monkeypatch):
    monkeypatch.setattr(analytics, "latest_publication", lambda: {"snapshot_schema": "SNAP_A"})
    query = Mock(side_effect=AssertionError("Must not execute SQL"))
    monkeypatch.setattr(analytics, "query", query)
    state = {"plan": {"supported": False, "limitation": "No revenue dataset"}}
    assert analytics.query_node(state)["charts"] == []
    assert analytics.rag_node(state)["sources"] == []


def test_embed_only_accepts_catalog_reports(monkeypatch):
    monkeypatch.setattr(powerbi, "catalog", lambda: [])
    with pytest.raises(ValueError):
        powerbi.embed("invented-report")


def test_api_requires_application_token(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    monkeypatch.setenv("APP_API_TOKEN", "local-test-token")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/freshness").status_code == 401
    assert client.get("/api/reports", headers={"Authorization": "Bearer local-test-token"}).status_code == 200


def test_langgraph_orchestration_with_supported_results(monkeypatch):
    monkeypatch.setattr(analytics, "plan_node", lambda s: {"plan": {"supported": True}})
    monkeypatch.setattr(analytics, "query_node", lambda s: {"charts": [{"dataset": [{"dimension": "City", "value": 2}]}]})
    monkeypatch.setattr(analytics, "rag_node", lambda s: {"sources": []})
    monkeypatch.setattr(analytics, "explain_node", lambda s: {"answer": "Two listings", "reports": []})
    result = analytics.build_graph().invoke({"question": "Compare cities"})
    assert result["answer"] == "Two listings"
    assert result["charts"][0]["dataset"][0]["value"] == 2


def test_retry_reuses_completed_llm_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "query", lambda *args: [])
    monkeypatch.setattr(pipeline, "llm", lambda *args, **kwargs: calls.append(args))
    assert pipeline.enrich({"schema": "SNAP_A"}) == {"schema": "SNAP_A"}
    assert calls == []


@pytest.mark.parametrize("greeting", ["hi", "hii", "Hello!", "hey swiggy"])
def test_greetings_do_not_query_warehouse_or_call_llm(monkeypatch, greeting):
    fail = Mock(side_effect=AssertionError("Greeting must not request analytics"))
    monkeypatch.setattr(analytics, "llm", fail)
    monkeypatch.setattr(analytics, "query", fail)
    monkeypatch.setattr(analytics, "latest_publication", fail)
    result = analytics.build_graph().invoke({"question": greeting, "history": []})
    assert result["answer"].startswith("Hi!")
    assert result["charts"] == []
    assert result["publication"] is None


def test_dashboard_uses_requested_metrics_and_city_filter(monkeypatch):
    monkeypatch.setattr(analytics, "latest_publication", lambda: {"snapshot_schema": "SNAP_A"})
    statements = []
    def run(sql, params):
        statements.append((sql, params))
        return [{"dimension": "Mumbai", "value": 4}]
    monkeypatch.setattr(analytics, "query", run)
    result = analytics.query_node({"plan": {"metric": "average_rating", "metrics": ["average_rating", "average_price"], "city": "Mumbai"}})
    assert [c["metric"] for c in result["charts"]] == ["average_rating", "average_price"]
    assert "AVG(RATING)" in statements[0][0]
    assert "AVG(AVERAGE_PRICE)" in statements[1][0]
    assert all(params == ["%Mumbai%"] for _, params in statements)


def test_unsupported_question_bypasses_warehouse(monkeypatch):
    monkeypatch.setattr(analytics, "plan_node", lambda s: {"plan": {"intent": "unsupported", "supported": False, "limitation": "Revenue is unavailable."}})
    monkeypatch.setattr(analytics, "query_node", Mock(side_effect=AssertionError("No warehouse query expected")))
    result = analytics.build_graph().invoke({"question": "Revenue?"})
    assert result["answer"] == "Revenue is unavailable."
    assert not result["charts"]


def test_cloud_encoder_uses_writable_serverless_caches(monkeypatch):
    import os
    import sys
    from types import SimpleNamespace
    from swiggy_platform import cloud_rag
    for name in ("HF_HOME", "HF_HUB_CACHE", "HF_XET_CACHE", "XDG_CACHE_HOME", "HF_HUB_DISABLE_XET"):
        monkeypatch.setenv(name, "/read-only/cache")
    def create_encoder(**kwargs):
        assert all(os.environ[name].startswith("/tmp/") for name in ("HF_HOME", "HF_HUB_CACHE", "HF_XET_CACHE", "XDG_CACHE_HOME"))
        assert os.environ["HF_HUB_DISABLE_XET"] == "1"
        assert kwargs["cache_dir"].startswith("/tmp/")
        return "encoder"
    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=create_encoder))
    cloud_rag.encoder.cache_clear()
    try:
        assert cloud_rag.encoder() == "encoder"
    finally:
        cloud_rag.encoder.cache_clear()


def test_natural_voice_is_authenticated_bounded_and_returns_audio(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    from swiggy_platform import config
    from swiggy_platform import speech
    monkeypatch.setattr(speech, "_groq_blocked_until", 0)
    monkeypatch.setenv("APP_API_TOKEN", "voice-test-token")
    client = TestClient(app)
    groq = Mock()
    groq.with_options.return_value.audio.speech.create.return_value.content = b"RIFFtest-audio"
    monkeypatch.setattr(config, "groq_client", lambda: groq)
    assert client.post("/api/speech", json={"text": "Hello"}).status_code == 401
    headers = {"Authorization": "Bearer voice-test-token"}
    assert client.post("/api/speech", headers=headers, json={"text": "x" * 201}).status_code == 422
    response = client.post("/api/speech", headers=headers, json={"text": "Hello"})
    assert response.status_code == 200 and response.content.startswith(b"RIFF")
    assert response.headers["content-type"] == "audio/wav"
    assert groq.with_options.return_value.audio.speech.create.call_args.kwargs["voice"] == "hannah"


def test_natural_female_voice_survives_provider_terms_block(monkeypatch):
    from swiggy_platform import config, speech
    monkeypatch.setattr(speech, "_groq_blocked_until", 0)
    groq = Mock()
    groq.with_options.return_value.audio.speech.create.side_effect = RuntimeError("model_terms_required")
    monkeypatch.setattr(config, "groq_client", lambda: groq)
    monkeypatch.setattr(speech, "kokoro_audio", lambda text: b"RIFFnatural-female-audio")
    assert speech.synthesize("Hello") == (b"RIFFnatural-female-audio", "Heart")
    assert speech.synthesize("Hello again")[1] == "Heart"
    assert groq.with_options.return_value.audio.speech.create.call_count == 1


@pytest.mark.parametrize("question", ["Explain the charts", "explain this report", "Explain the current dashboard charts and their values"])
def test_explanation_retains_dashboard_metrics_filters_and_reports(monkeypatch, question):
    previous = analytics.Plan(metric="average_rating", metrics=["average_rating", "average_price"], city="Mumbai", sort_direction="asc", limit=5).model_dump()
    monkeypatch.setattr(analytics, "latest_publication", lambda: {"snapshot_schema":"SNAP_A", "freshness":"fresh", "ai_scope":"20 listings", "rag_ready":False})
    statements=[]
    monkeypatch.setattr(analytics, "query", lambda sql, params: statements.append((sql, params)) or [{"dimension":"Mumbai", "value":4}])
    monkeypatch.setattr(analytics, "catalog", lambda:[{"key":"ratings", "title":"Ratings report", "metrics":["average_rating"]}])
    calls=[]
    def explain(messages, **kwargs):
        calls.append(messages)
        assert 'Mumbai' in messages[-1]['content']
        assert 'average_price' in messages[-1]['content']
        return 'Mumbai has an average rating of 4 in the displayed chart.'
    monkeypatch.setattr(analytics, "llm", explain)
    result=analytics.build_graph().invoke({"question":question,"dashboard_context":previous})
    assert len(calls)==1
    assert [c['metric'] for c in result['charts']]==['average_rating','average_price']
    assert all(p==['%Mumbai%'] and 'ASC' in sql and 'LIMIT 5' in sql for sql,p in statements)
    assert result['reports'][0]['key']=='ratings'
    assert result['dashboard_context']==previous


def test_explanation_without_dashboard_asks_for_chart(monkeypatch):
    monkeypatch.setattr(analytics,'llm',lambda *a,**k:analytics.Plan(intent='explain').model_dump_json())
    monkeypatch.setattr(analytics,'query',Mock(side_effect=AssertionError('No chart to query')))
    result=analytics.build_graph().invoke({'question':'Explain the chart'})
    assert 'create a chart first' in result['answer']
    assert result['charts']==[]
