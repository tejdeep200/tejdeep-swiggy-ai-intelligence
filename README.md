# Swiggy AI Intelligence

Public frontend: https://tejdeep-swiggy-ai-intelligence.vercel.app

Cloud API health: https://tejdeep-swiggy-api.vercel.app/health

The frontend and API are deployed with owner-approved server-side secrets.
Public greeting, Snowflake chart and vector-grounded answer checks pass. The
local Docker application remains configured separately.

The existing Snowflake RAW loader and `swiggy_dbt` project feed an independent
FastAPI/LangGraph API and Next.js website. No generated business data is used.

## Run

Keep credentials in ignored `airflow/.env`. Existing values are preserved. Use
`.env.example` for additional settings. `scripts/setup_airflow.py` initializes
Airflow secrets only when the environment file does not already exist.

```powershell
docker compose --env-file airflow/.env up -d --build
docker compose --env-file airflow/.env exec scheduler airflow dags list-import-errors
docker compose --env-file airflow/.env exec scheduler airflow dags unpause swiggy_ai_end_to_end_pipeline
docker compose --env-file airflow/.env exec scheduler airflow dags trigger swiggy_ai_end_to_end_pipeline
```

Website: http://localhost:3000. API health: http://localhost:8000/health.
Airflow: http://localhost:8081 (`admin`; private password in `airflow/.env`).
Keep the legacy `swiggy_batch` DAG paused when using the new DAG to avoid
simultaneous writes to the same dbt models. Stop with `docker compose --env-file
airflow/.env down`; omit `--volumes` to preserve metadata and vector storage.

For development without application containers:

```powershell
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd frontend
npm.cmd ci --cache ../.npm-cache
npm.cmd run build
cd ..
.venv\Scripts\python.exe scripts/run_local.py
```

The API token remains on the Next.js server. Services bind to localhost;
end-user authentication must be added before exposing this development setup
publicly. Browser code never receives Groq, Snowflake, Entra, or Airflow secrets.

## Pipeline and publication

`swiggy_ai_end_to_end_pipeline` validates configured source stages, reuses the
existing temporary-table COPY/deduplication/MERGE loader, validates RAW, runs dbt
staging and marts, preserves snapshots and runs all dbt tests. There is no
intermediate model directory in this project. Source checks and ingestion use
Snowflake storage integrations, avoiding a second set of cloud credentials.
The Amazon, Azure and Snowflake Airflow providers are installed for extensions.
Cosmos is not required; dbt remains in its existing isolated virtual environment.

Each run creates a separate zero-copy curated snapshot. A failed run cannot
replace the API's last published snapshot. The pipeline hashes listing contents,
caches Groq outputs by hash/model/prompt version, generates local MiniLM
embeddings, caches unchanged vectors and creates a publication-specific Chroma
collection. Removed listings are absent from the next collection; old
publications and collections are retained. Do not delete historical snapshots
or collections while clients may still use them. The warehouse publication
record is inserted only after quality, AI and vector counts pass and any
configured Power BI refresh completes.

**Initial AI/RAG coverage is deliberately capped at 20 listings**, ordered by
restaurant ID. Charts query all published curated listings. `AI_RECORD_LIMIT=20`
sets this representative test scope; `AI_BATCH_SIZE=8` and
`GROQ_MIN_REQUEST_INTERVAL_SECONDS=3` bound request pressure. Cached matching
records incur no repeat LLM calls. Increasing the limit is an explicit scaling
decision; zero means all records and should not be used on a free tier. Records
outside the scope are not represented as enriched. API responses expose
`ai_row_count`, `row_count`, and `ai_scope`, and answers state RAG coverage.

Groq retries are finite (SDK backoff, at most six SDK retries per request), with
three Airflow task retries and exponential backoff. The enrichment and embedding
pools each have one slot. Structured completion/failure events and task durations
are available in Airflow logs/UI. A failure webhook is opt-in.

`SWIGGY_SCHEDULE` defaults to `@daily`; an empty value is manual-only. Airflow's
authenticated API/UI can trigger an external event run. Browser routes do not
expose DAG execution. `catchup=False`; explicit historical/manual runs are
supported, but current-stage ingestion does not reconstruct a point-in-time
cloud source unless the stage contents themselves are versioned. Exact identical
source rows are deduplicated; conflicting versions of a key block ingestion.
The existing loader preserves target records missing from current files.

`SOURCE_MAX_AGE_HOURS` optionally rejects old file modification times. Published
freshness means processing/publication time, not the age of the underlying
historical listing dataset. No transaction or real-time claims are made.

For an initial curated-only publication before the AI DAG finishes, run
`scripts/bootstrap_publication.py`; it runs the existing dbt tests, validates and
clones curated tables, and explicitly marks AI/RAG unavailable. The full DAG
replaces this baseline after its own checks pass.

## Analytics and voice

LangGraph plans a validated metric/dimension request, executes parameterized
Snowflake SQL against allowlisted snapshot tables, retrieves real listing
documents and asks Groq for a grounded explanation. Follow-up context is bounded.
Supported metrics: listing count, average rating, average listing price and
vegetarian share, grouped by city, area, restaurant or cuisines. Cuisines are
listing-level combinations; they are not individual-cuisine attribution.

Revenue, order volume, delivery performance, reviews, sentiment and churn are
absent from this Swiggy dataset and are explicitly rejected. Average listing
price is not revenue. Recharts renders actual returned SQL results; these are
not Power BI visuals. The microphone records on user action, transcribes through
Groq Whisper and fills the question field; submit with Ask Swiggy. Natural female
narration uses Groq Hannah, then self-hosted Kokoro Heart if unavailable, then an
available female browser voice. Short summaries are capped at 200 characters.
Stop voice cancels pending audio and switches to charts only; Play summary resumes
narration. Charts only / Show analysis toggles the written detail. Kokoro downloads
its model to temporary storage on first use, so cold starts can take longer.
On Vercel, deploy `deploy/vercel-voice` separately using
`scripts/prepare_vercel_voice.py`; configure its Groq key and application token
with `scripts/configure_vercel_env.py voice`. Set the frontend server-only
`SPEECH_URL` to that service URL. This isolates voice model storage from RAG.
Hardware microphone/speaker verification requires an interactive browser session.

## Power BI

`config/powerbi_reports.json` is an empty authorized catalog until real workspace
permissions and report IDs are supplied. Dynamic charts work without it. Example
catalog entry (replace every placeholder with authorized values):

```json
{
  "key": "restaurant-performance",
  "title": "Restaurant Performance",
  "workspace_id": "WORKSPACE_UUID",
  "report_id": "REPORT_UUID",
  "dataset_id": "DATASET_UUID",
  "mode": "Import",
  "metrics": ["restaurant_count", "average_rating"],
  "pages": [{"name": "ReportSection", "title": "Overview"}],
  "visuals": [{"name": "visualName", "page": "ReportSection", "title": "Coverage"}],
  "filter_targets": {"city": {"table": "DIM_RESTAURANTS", "column": "CITY_NAME"}}
}
```

Store entries in a JSON array. Configure `POWERBI_TENANT_ID`, `POWERBI_CLIENT_ID`
and `POWERBI_CLIENT_SECRET`. The service principal needs tenant embedding
permission, workspace access and appropriate Power BI capacity. Embed tokens are
server-generated for allowlisted reports with read permission. Catalog pages,
visuals, a city filter, native report filters/slicers and error states are wired.
Configure date/category slicers in the actual report only if its data supports
them. Import refreshes are polled to completion before publication; DirectQuery
skips Import refresh and relies on validated source readiness. This code does
not create or retarget a semantic model; configure its Snowflake source separately.
Refresh timestamps are included in publication `powerbi_status`.

## Checks

```powershell
.venv\Scripts\python.exe -m pytest airflow/tests -q
.venv\Scripts\python.exe scripts/check_services.py
docker compose --env-file airflow/.env exec scheduler airflow dags list-import-errors
```

Implementation is shared in `swiggy_platform/` rather than duplicated under each
Airflow include directory. `airflow/include/README.md` maps those responsibilities.
Runtime logs, generated profiles, node modules and environment files are ignored.

References: [Airflow Task SDK](https://airflow.apache.org/docs/task-sdk/stable/),
[Groq speech API](https://console.groq.com/docs/speech-to-text),
[Power BI embedding](https://learn.microsoft.com/en-us/power-bi/developer/embedded/generate-embed-token).

## Verified local result

- Production website build passed; website and API are running in Docker.
- 21 automated tests and all 21 existing dbt tests passed.
- The end-to-end Airflow run passed all 22 tasks using the verified Azure stage.
- Published analytics cover 140,657 real listings; AI enrichment and RAG cover
  the explicitly bounded 20-listing sample.
- A real website analytics request returned HTTP 200 and Snowflake chart rows.
- A real website RAG request returned HTTP 200, one chart and four source listings.
- Public Vercel smoke checks passed for site loading, published Snowflake data,
  a greeting without charts, and a ratings chart with four cloud RAG sources.
- AWS stage access is blocked by Snowflake integration permissions (error 3167).
- Power BI embedding cannot be validated without authorized catalog entries and
  Entra/workspace/capacity configuration.
- Microphone capture, browser speech playback and mouth synchronization require
  an interactive browser/device test. A workstation synthetic-speech probe was
  unavailable; no successful hardware voice test is claimed.

Greetings return conversational replies without querying Snowflake or creating
charts. Analytics questions select their own metrics, grouping, filters and
dashboard title; broad overviews can include several charts. Dashboard summary
cards describe the returned groups rather than always showing a global count.

## Vercel deployment

The frontend is the `frontend/` project. `scripts/prepare_vercel_backend.py`
stages the existing FastAPI/shared code with the lightweight dependencies in
`deploy/vercel-backend/`. The Vercel backend uses FastEmbed's ONNX MiniLM encoder
and reads a durable 20-record vector mirror from Snowflake; the local pipeline
continues to use ChromaDB and now synchronizes that mirror before publication.
This removes the public app's dependency on a laptop-hosted vector service.

`scripts/setup_cloud_reader.py` grants a dedicated `SWIGGY_APP_READER` role
read access to publication metadata, mirrored vectors and immutable snapshots.
The cloud runtime does not receive ACCOUNTADMIN privileges. Encrypted private
key material can be supplied through `SNOWFLAKE_PRIVATE_KEY_BASE64`, with its
passphrase in a separate server-side secret. No credential values belong in Git.
`scripts/configure_vercel_env.py` sends owner-approved values over stdin to
Vercel Secret environment variables. Redeploy after changing environment values.

Airflow still runs in the local Docker installation: public queries can read
the latest successful publication while that machine is off, but new scheduled
ingestion requires the Airflow host to be running. A sleeping/unavailable
warehouse or exhausted API/hosting quotas can still delay or block requests.

Run `python scripts/check_public_site.py` for the bounded public smoke check.
The model cache uses `/tmp` so Hugging Face downloads work on Vercel's otherwise
read-only runtime filesystem. Model weights may be downloaded on a cold start.
