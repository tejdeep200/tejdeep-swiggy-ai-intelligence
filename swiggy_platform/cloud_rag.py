"""Cloud retrieval mirrors the bounded Chroma index into durable Snowflake storage."""
import json
import os
from functools import lru_cache

from .config import database, query

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def mirror_collection(collection_name, client=None):
    from .pipeline import chroma
    client = client or chroma()
    collection = client.get_collection(collection_name)
    query(f"""CREATE TABLE IF NOT EXISTS {database()}.AI.RAG_VECTORS (
        COLLECTION VARCHAR, RESTAURANT_ID VARCHAR, DOCUMENT VARCHAR, EMBEDDING ARRAY, MODEL VARCHAR)""")
    for offset in range(0, collection.count(), 128):
        data = collection.get(limit=128, offset=offset, include=["documents", "embeddings"])
        records = [{"id": rid, "document": doc, "embedding": list(map(float, vector))}
                   for rid, doc, vector in zip(data["ids"], data["documents"], data["embeddings"])]
        query(f"""MERGE INTO {database()}.AI.RAG_VECTORS t USING (
            SELECT %s COLLECTION, value:id::VARCHAR RESTAURANT_ID,
                value:document::VARCHAR DOCUMENT, value:embedding::ARRAY EMBEDDING, %s MODEL
            FROM TABLE(FLATTEN(INPUT=>PARSE_JSON(%s)))) s
            ON t.COLLECTION=s.COLLECTION AND t.RESTAURANT_ID=s.RESTAURANT_ID
            WHEN MATCHED THEN UPDATE SET DOCUMENT=s.DOCUMENT, EMBEDDING=s.EMBEDDING, MODEL=s.MODEL
            WHEN NOT MATCHED THEN INSERT (COLLECTION,RESTAURANT_ID,DOCUMENT,EMBEDDING,MODEL)
            VALUES(s.COLLECTION,s.RESTAURANT_ID,s.DOCUMENT,s.EMBEDDING,s.MODEL)""",
              (collection_name, MODEL, json.dumps(records)))
    count = query(f"SELECT COUNT(*) n FROM {database()}.AI.RAG_VECTORS WHERE COLLECTION=%s", (collection_name,))[0]["n"]
    if count != collection.count():
        raise ValueError("Cloud vector mirror count disagrees with Chroma")
    return count


@lru_cache(maxsize=1)
def encoder():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL, cache_dir=os.getenv("FASTEMBED_CACHE_PATH", "/tmp/swiggy_embeddings"), threads=2)


def retrieve(question, publication):
    vector = next(encoder().embed([question])).tolist()
    rows = query(f"""SELECT RESTAURANT_ID, DOCUMENT,
        1 - VECTOR_COSINE_SIMILARITY(EMBEDDING::VECTOR(FLOAT,384),
            PARSE_JSON(%s)::VECTOR(FLOAT,384)) DISTANCE
        FROM {database()}.AI.RAG_VECTORS WHERE COLLECTION=%s AND MODEL=%s
        ORDER BY DISTANCE ASC LIMIT 4""", (json.dumps(vector), publication["collection"], MODEL))
    return [{"id": r["restaurant_id"], "listing": json.loads(r["document"]), "distance": r["distance"]} for r in rows]
