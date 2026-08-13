"""
Worker that consumes jobs from Redis list 'ml:jobs' and computes embeddings
It loads the same sentence-transformers model as the ml-service and updates the on-disk index.
"""
import os
import time
import json
import redis
import numpy as np
from sentence_transformers import SentenceTransformer

REDIS_URL = os.environ.get('REDIS_URL','redis://redis:6379/0')
DATA_DIR = os.environ.get('ML_DATA_DIR','/data')
INDEX_PATH = os.path.join(DATA_DIR,'index.npz')
MODEL_NAME = os.environ.get('SENTENCE_MODEL','all-MiniLM-L6-v2')

r = redis.from_url(REDIS_URL, decode_responses=True)
model = SentenceTransformer(MODEL_NAME)

# helper to load and save index
def load_index():
    if not os.path.exists(INDEX_PATH):
        return None, []
    try:
        data = np.load(INDEX_PATH, allow_pickle=True)
        if 'embeddings' in data:
            embs = data['embeddings']
            meta_raw = data['meta'] if 'meta' in data else []
            meta = [json.loads(x) for x in meta_raw.tolist()] if len(meta_raw)>0 else []
            return embs, meta
    except Exception as e:
        print('load_index error', e)
    return None, []

def save_index(embs, meta):
    os.makedirs(DATA_DIR, exist_ok=True)
    np.savez_compressed(INDEX_PATH, embeddings=embs, meta=np.array([json.dumps(m) for m in meta], dtype=object))

print('Worker started, waiting for jobs...')
while True:
    try:
        job_id = r.brpop('ml:jobs', timeout=5)
        if not job_id:
            time.sleep(0.5)
            continue
        # brpop returns tuple (key, value)
        job_id = job_id[1]
        print('Got job', job_id)
        items_raw = r.get(f'ml:job:{job_id}:items')
        if not items_raw:
            print('No items for job', job_id)
            r.publish('ml:events', json.dumps({'type':'job_failed','job_id':job_id, 'reason':'no items'}))
            continue
        items = json.loads(items_raw)
        texts = [it['text'] for it in items]
        embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        # load existing index
        old_embs, meta = load_index()
        if old_embs is None:
            new_embs = embs
            new_meta = [ {'path':it['path']} for it in items ]
        else:
            new_embs = np.vstack([old_embs, embs])
            new_meta = meta + [ {'path':it['path']} for it in items ]
        save_index(new_embs, new_meta)
        r.publish('ml:events', json.dumps({'type':'job_complete','job_id':job_id, 'added': len(items)}))
        print('Job complete', job_id)
    except Exception as e:
        print('Worker error', e)
        time.sleep(2)
