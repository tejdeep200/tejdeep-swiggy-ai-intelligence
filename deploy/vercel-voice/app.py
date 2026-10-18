import hmac
import os
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field
from swiggy_platform.speech import synthesize

app = FastAPI()

class Narration(BaseModel):
    text: str = Field(min_length=1, max_length=200)

@app.post("/api/speech")
def speech(request: Narration, authorization: str = Header(default="")):
    token = os.getenv("APP_API_TOKEN", "")
    if not token or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "Unauthorized")
    try:
        audio, name = synthesize(request.text)
        return Response(audio, media_type="audio/wav", headers={"Cache-Control":"no-store", "X-Voice-Name":name})
    except Exception:
        raise HTTPException(503, "Natural voice temporarily unavailable") from None
