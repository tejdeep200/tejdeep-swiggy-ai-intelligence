import logging
import os
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from swiggy_platform.config import load_env

load_env()
app = FastAPI(title="Swiggy AI Intelligence")
LOG = logging.getLogger(__name__)


def authorize(authorization: str = Header(default="")):
    expected = os.getenv("APP_API_TOKEN", "")
    if not expected or not secrets.compare_digest(authorization, "Bearer " + expected):
        raise HTTPException(401, "An application access token is required")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=6)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/freshness", dependencies=[Depends(authorize)])
def freshness():
    from swiggy_platform.pipeline import latest_publication
    try:
        return jsonable_encoder(latest_publication())
    except Exception:
        LOG.warning("Publication status unavailable", exc_info=False)
        return {"freshness": "unavailable", "ai_ready": False, "rag_ready": False,
                "message": "No verified publication available. Check the pipeline and warehouse connection."}


@app.post("/api/ask", dependencies=[Depends(authorize)])
def ask(request: Question):
    from swiggy_platform.analytics import build_graph
    try:
        result = build_graph().invoke({"question": request.question, "history": [m.model_dump() for m in request.history]})
        return jsonable_encoder({k: result.get(k) for k in ("answer", "charts", "reports", "sources", "publication", "dashboard_title")})
    except Exception as exc:
        LOG.error("Analytics request failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Analytics unavailable. Verify Groq, the published Snowflake snapshot and the RAG service.") from None


@app.post("/api/transcribe", dependencies=[Depends(authorize)])
async def transcribe(audio: UploadFile = File(...)):
    from starlette.concurrency import run_in_threadpool
    from swiggy_platform.config import groq_client
    data = await audio.read(20 * 1024 * 1024 + 1)
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Audio must be between 1 byte and 20 MB")
    try:
        result = await run_in_threadpool(lambda: groq_client().audio.transcriptions.create(
            file=("question.webm", data), model="whisper-large-v3-turbo"))
        return {"text": result.text}
    except Exception:
        raise HTTPException(502, "Speech transcription unavailable") from None


@app.get("/api/reports", dependencies=[Depends(authorize)])
def reports():
    from swiggy_platform.powerbi import catalog
    return [{"key": r["key"], "title": r["title"], "metrics": r.get("metrics", [])} for r in catalog()]


@app.get("/api/reports/{key}/embed", dependencies=[Depends(authorize)])
def report_embed(key: str):
    from swiggy_platform.powerbi import embed
    try:
        return embed(key)
    except ValueError:
        raise HTTPException(404, "Report not in catalog") from None
    except Exception:
        raise HTTPException(503, "Power BI embedding requires workspace, service principal and capacity configuration") from None
