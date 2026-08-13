"""
Simple ML service for embeddings and retrieval (self-hosted, free OSS components).
- Uses sentence-transformers (all-MiniLM-L6-v2) for embeddings.
- Stores a small on-disk index (NPZ) for embeddings and metadata.
- Provides endpoints to enqueue embedding jobs and perform retrieval/suggestion.

This is intentionally lightweight and designed for local / small-team usage.
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
import numpy as np
import os
import json
import uuid
import redis
from typing import List, Dict

DATA_DIR = os.environ.get('ML_DATA_DIR', '/data')
INDEX_PATH = os.path.join(DATA_DIR, 'index.npz')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')

os.makedirs(DATA_DIR, exist_ok=True)

# Simple Redis client for pub/sub or queue
r = redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title='LUVORA ML Service')

# Load model on startup
MODEL_NAME = os.environ.get('SENTENCE_MODEL','all-MiniLM-L6-v2')
model = SentenceTransformer(MODEL_NAME)

# In-memory index cache to avoid reloading often
INDEX = {'embeddings': None, 'meta': []}

def save_index():
    # Save embeddings (2D np array) and meta list to disk
    embs = INDEX['embeddings']
    meta = INDEX['meta']
    if embs is None:
        # write empty
        np.savez_compressed(INDEX_PATH)
        return
    np.savez_compressed(INDEX_PATH, embeddings=embs, meta=np.array([json.dumps(m) for m in meta], dtype=object))

def load_index():
    if not os.path.exists(INDEX_PATH):
        INDEX['embeddings'] = None
        INDEX['meta'] = []
        return
    try:
        data = np.load(INDEX_PATH, allow_pickle=True)
        if 'embeddings' in data:
            INDEX['embeddings'] = data['embeddings']
            meta_raw = data['meta'] if 'meta' in data else []
            INDEX['meta'] = [json.loads(x) for x in meta_raw.tolist()] if len(meta_raw)>0 else []
        else:
            INDEX['embeddings'] = None
            INDEX['meta'] = []
    except Exception as e:
        print('Failed to load index:', e)
        INDEX['embeddings'] = None
        INDEX['meta'] = []

# Initialize index
load_index()

class FileItem(BaseModel):
    path: str
    text: str

class EmbeddingJob(BaseModel):
    job_id: str = None
    items: List[FileItem]

class SuggestRequest(BaseModel):
    query: str
    top_k: int = 5

@app.post('/ml/embeddings/job')
async def enqueue_embedding(job: EmbeddingJob, background: BackgroundTasks):
    # assign job id
    job_id = job.job_id or str(uuid.uuid4())
    payload = {'job_id': job_id, 'items': [{'path':it.path} for it in job.items]}
    # Push job payload to redis list for worker processing; store the full items in a redis key
    try:
        r.set(f'ml:job:{job_id}:items', json.dumps([{'path':it.path,'text':it.text} for it in job.items]))
        r.lpush('ml:jobs', job_id)
        # publish event
        r.publish('ml:events', json.dumps({'type':'job_enqueued','job_id':job_id}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'ok':True, 'job_id':job_id}

@app.post('/ml/embeddings/compute')
async def compute_embeddings_direct(job: EmbeddingJob):
    # synchronous compute (useful for small jobs or testing)
    if not job.items:
        raise HTTPException(status_code=400, detail='no items')
    texts = [it.text for it in job.items]
    embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    # append to index
    if INDEX['embeddings'] is None:
        INDEX['embeddings'] = embs
        INDEX['meta'] = [ {'path':it.path} for it in job.items ]
    else:
        INDEX['embeddings'] = np.vstack([INDEX['embeddings'], embs])
        INDEX['meta'].extend([ {'path':it.path} for it in job.items ])
    save_index()
    r.publish('ml:events', json.dumps({'type':'job_complete','job_id': job.job_id or 'inline'}))
    return {'ok':True, 'added': len(job.items)}

@app.post('/ml/suggest')
async def suggest(req: SuggestRequest):
    # Compute query embedding and return top-k similar items
    if INDEX['embeddings'] is None or len(INDEX['meta'])==0:
        return {'ok':True, 'results': []}
    q_emb = model.encode([req.query], convert_to_numpy=True)[0]
    embs = INDEX['embeddings']
    # cosine similarity
    embs_norm = embs / np.linalg.norm(embs, axis=1, keepdims=True)
    q_norm = q_emb / np.linalg.norm(q_emb)
    sims = np.dot(embs_norm, q_norm)
    idx = np.argsort(-sims)[:req.top_k]
    results = []
    for i in idx:
        results.append({'score': float(sims[i]), 'meta': INDEX['meta'][i]})
    return {'ok':True, 'results': results}

@app.get('/ml/index/status')
async def index_status():
    return {'ok':True, 'count': 0 if INDEX['embeddings'] is None else int(INDEX['embeddings'].shape[0])}

# Simple health
@app.get('/health')
async def health():
    return {'ok':True}
