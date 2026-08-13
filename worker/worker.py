"""
Worker that consumes jobs from Redis list 'ml:jobs' and computes embeddings
Now updates FAISS index (if available) or NPZ fallback. Also computes centroid (repo-level) as a simple learned pattern and saves it.
"""
import os
import time
import json
import redis
import numpy as np
from sentence_transformers import SentenceTransformer

REDIS_URL = os.environ.get('REDIS_URL','redis://redis:6379/0')
DATA_DIR = os.environ.get('ML_DATA_DIR','/data')
NPZ_PATH = os.path.join(DATA_DIR,'index.npz')
FAISS_PATH = os.path.join(DATA_DIR,'faiss_index.bin')
META_PATH = os.path.join(DATA_DIR,'faiss_meta.json')
CENTROID_PATH = os.path.join(DATA_DIR,'centroid.npy')
MODEL_NAME = os.environ.get('SENTENCE_MODEL','all-MiniLM-L6-v2')

r = redis.from_url(REDIS_URL, decode_responses=True)
model = SentenceTransformer(MODEL_NAME)

try:
    import faiss
    HAS_FAISS = True
except Exception as e:
    HAS_FAISS = False

# helper to load and save index

def load_npz():
    if not os.path.exists(NPZ_PATH):
        return None, []
    try:
        data = np.load(NPZ_PATH, allow_pickle=True)
        embs = data['embeddings'] if 'embeddings' in data else None
        meta_raw = data['meta'] if 'meta' in data else np.array([])
        meta = [json.loads(x) for x in meta_raw.tolist()] if len(meta_raw)>0 else []
        return embs, meta
    except Exception as e:
        print('load_npz error', e)
    return None, []


def save_npz(embs, meta):
    os.makedirs(DATA_DIR, exist_ok=True)
    np.savez_compressed(NPZ_PATH, embeddings=embs, meta=np.array([json.dumps(m) for m in meta], dtype=object))


def load_faiss():
    if not HAS_FAISS or not os.path.exists(FAISS_PATH):
        return None, []
    try:
        idx = faiss.read_index(FAISS_PATH)
        with open(META_PATH,'r') as f:
            meta = json.load(f)
        return idx, meta
    except Exception as e:
        print('load_faiss error', e)
    return None, []


def save_faiss(index, meta):
    try:
        faiss.write_index(index, FAISS_PATH)
        with open(META_PATH,'w') as f:
            json.dump(meta, f)
        return True
    except Exception as e:
        print('save_faiss error', e)
        return False


print('Worker started, waiting for jobs...')
while True:
    try:
        job = r.brpop('ml:jobs', timeout=5)
        if not job:
            time.sleep(0.5)
            continue
        job_id = job[1]
        print('Got job', job_id)
        items_raw = r.get(f'ml:job:{job_id}:items')
        if not items_raw:
            print('No items for job', job_id)
            r.publish('ml:events', json.dumps({'type':'job_failed','job_id':job_id, 'reason':'no items'}))
            continue
        items = json.loads(items_raw)
        texts = [it['text'] for it in items]
        embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        # normalize embeddings for FAISS (IP)
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        emb_norm = embs / np.maximum(norms, 1e-12)

        if HAS_FAISS:
            idx, meta = load_faiss()
            if idx is None:
                d = emb_norm.shape[1]
                idx = faiss.IndexFlatIP(d)
                idx.add(emb_norm.astype('float32'))
                meta = [ {'path':it['path']} for it in items ]
            else:
                # append
                idx.add(emb_norm.astype('float32'))
                meta.extend([ {'path':it['path']} for it in items ])
            save_faiss(idx, meta)
        else:
            existing, meta = load_npz()
            if existing is None:
                new_embs = embs
                meta = [ {'path':it['path']} for it in items ]
            else:
                new_embs = np.vstack([existing, embs])
                meta.extend([ {'path':it['path']} for it in items ])
            save_npz(new_embs, meta)

        # compute centroid (simple learned pattern)
        try:
            # load all embeddings (from FAISS or NPZ)
            if HAS_FAISS and os.path.exists(FAISS_PATH):
                idx, meta = load_faiss()
                # retrieve vectors by searching for all (hack: cannot read raw vectors easily) - instead recompute from NPZ if present
                if os.path.exists(NPZ_PATH):
                    data = np.load(NPZ_PATH, allow_pickle=True)
                    if 'embeddings' in data:
                        all_embs = data['embeddings']
                        centroid = np.mean(all_embs, axis=0)
                        np.save(CENTROID_PATH, centroid)
                else:
                    # fallback: use new batch centroid
                    centroid = np.mean(emb_norm, axis=0)
                    np.save(CENTROID_PATH, centroid)
            else:
                data = np.load(NPZ_PATH, allow_pickle=True)
                if 'embeddings' in data:
                    all_embs = data['embeddings']
                    centroid = np.mean(all_embs, axis=0)
                    np.save(CENTROID_PATH, centroid)
        except Exception as e:
            print('centroid update failed', e)

        r.publish('ml:events', json.dumps({'type':'job_complete','job_id':job_id, 'added': len(items)}))
        print('Job complete', job_id)
    except Exception as e:
        print('Worker error', e)
        time.sleep(2)
