"""
ML service with FAISS-backed index, WebSocket event broadcast, admin authentication, and real-time /track endpoint.
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
import os
import json
import uuid
import redis
import threading
import asyncio
from typing import List
import time
import subprocess
import jwt
from datetime import datetime, timedelta

DATA_DIR = os.environ.get('ML_DATA_DIR', '/data')
INDEX_FAISS = os.path.join(DATA_DIR, 'faiss_index.bin')
INDEX_META = os.path.join(DATA_DIR, 'faiss_meta.json')
INDEX_NPZ = os.path.join(DATA_DIR, 'index.npz')
JOBS_LOG = os.path.join(DATA_DIR, 'jobs.jsonl')
CLICK_LOG = os.path.join(DATA_DIR, 'clicks.jsonl')
TRACK_LOG = os.path.join(DATA_DIR, 'tracking_events.jsonl')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
JWT_SECRET = os.environ.get('JWT_SECRET','change_this_secret')
JWT_ALGO = 'HS256'
ADMIN_USER = os.environ.get('ADMIN_USER','admin')
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD','password')
os.makedirs(DATA_DIR, exist_ok=True)

r = redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title='LUVORA ML Service (FAISS-enabled, Admin, Real-time)')

MODEL_NAME = os.environ.get('SENTENCE_MODEL','all-MiniLM-L6-v2')
model = SentenceTransformer(MODEL_NAME)

# Try to import FAISS
try:
    import faiss
    HAS_FAISS = True
except Exception as e:
    HAS_FAISS = False
    faiss = None

# In-memory placeholders
FAISS_INDEX = None
META = []
INDEX_LOCK = threading.Lock()

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        to_remove = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                to_remove.append(connection)
        for c in to_remove:
            self.disconnect(c)

manager = ConnectionManager()

# Helpers for FAISS/NPZ

def load_index():
    global FAISS_INDEX, META
    with INDEX_LOCK:
        if HAS_FAISS and os.path.exists(INDEX_FAISS):
            try:
                FAISS_INDEX = faiss.read_index(INDEX_FAISS)
                if os.path.exists(INDEX_META):
                    with open(INDEX_META,'r') as f:
                        META = json.load(f)
                else:
                    META = []
                print('Loaded FAISS index with', FAISS_INDEX.ntotal, 'vectors')
                return
            except Exception as e:
                print('Failed loading FAISS index:', e)
        # Fallback to NPZ
        if os.path.exists(INDEX_NPZ):
            try:
                data = np.load(INDEX_NPZ, allow_pickle=True)
                if 'embeddings' in data:
                    embeddings = data['embeddings']
                    META = [json.loads(x) for x in data['meta'].tolist()] if 'meta' in data else []
                    if HAS_FAISS:
                        d = embeddings.shape[1]
                        idx = faiss.IndexFlatIP(d)
                        # normalize
                        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                        emb_norm = embeddings / np.maximum(norms, 1e-12)
                        idx.add(emb_norm.astype('float32'))
                        FAISS_INDEX = idx
                        # write faiss index & meta
                        try:
                            faiss.write_index(FAISS_INDEX, INDEX_FAISS)
                            with open(INDEX_META,'w') as f:
                                json.dump(META, f)
                            print('Migrated NPZ to FAISS index')
                        except Exception as e:
                            print('Failed to write FAISS during migration:', e)
                        return
                    else:
                        # keep NPZ in memory
                        FAISS_INDEX = None
                        META = META
                        return
            except Exception as e:
                print('Failed loading NPZ index:', e)
        # No index present
        FAISS_INDEX = None
        META = []
        print('No index found; starting empty')

def save_faiss_index(index, meta):
    with INDEX_LOCK:
        try:
            faiss.write_index(index, INDEX_FAISS)
            with open(INDEX_META,'w') as f:
                json.dump(meta, f)
            return True
        except Exception as e:
            print('Failed to save FAISS index:', e)
            return False

def save_npz(embs, meta):
    with INDEX_LOCK:
        try:
            np.savez_compressed(INDEX_NPZ, embeddings=embs, meta=np.array([json.dumps(m) for m in meta], dtype=object))
            return True
        except Exception as e:
            print('Failed to save NPZ:', e)
            return False

# Load index on startup
load_index()

# Background thread to subscribe to Redis and broadcast via WebSocket

def redis_listener_loop():
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe('ml:events')
    pubsub.subscribe('ml:insights')
    print('Redis listener subscribed to ml:events and ml:insights')
    for message in pubsub.listen():
        try:
            data = message['data']
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            # schedule broadcast in event loop
            asyncio.get_event_loop().call_soon_threadsafe(asyncio.create_task, manager.broadcast(data))
        except Exception as e:
            print('Error handling redis message:', e)

listener_thread = threading.Thread(target=redis_listener_loop, daemon=True)
listener_thread.start()

# JWT helpers

def create_token(username: str):
    exp = datetime.utcnow() + timedelta(hours=12)
    payload = {'sub': username, 'exp': exp.timestamp()}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str):
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return data
    except Exception:
        return None

async def get_current_user(request: Request):
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Unauthorized')
    token = auth.split(' ',1)[1]
    data = decode_token(token)
    if not data:
        raise HTTPException(status_code=401, detail='Invalid token')
    return data.get('sub')

# API models
class FileItem(BaseModel):
    path: str
    text: str

class EmbeddingJob(BaseModel):
    job_id: str = None
    items: List[FileItem]

class SuggestRequest(BaseModel):
    query: str
    top_k: int = 5

class LoginRequest(BaseModel):
    username: str
    password: str

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive; client may send pings
    except WebSocketDisconnect:
        manager.disconnect(ws)

@app.post('/auth/login')
async def login(req: LoginRequest):
    if req.username == ADMIN_USER and req.password == ADMIN_PASS:
        token = create_token(req.username)
        return {'ok':True, 'token': token}
    raise HTTPException(status_code=401, detail='Invalid credentials')

@app.post('/ml/embeddings/job')
async def enqueue_embedding(job: EmbeddingJob):
    job_id = job.job_id or str(uuid.uuid4())
    payload = {'job_id': job_id, 'items': [{'path':it.path} for it in job.items]}
    try:
        r.set(f'ml:job:{job_id}:items', json.dumps([{'path':it.path,'text':it.text} for it in job.items]))
        r.lpush('ml:jobs', job_id)
        # log job
        with open(JOBS_LOG,'a') as f:
            f.write(json.dumps({'ts': time.time(), 'job_id':job_id, 'type':'enqueue', 'items': len(job.items)}) + '\n')
        r.publish('ml:events', json.dumps({'type':'job_enqueued','job_id':job_id}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'ok':True, 'job_id':job_id}

@app.post('/ml/embeddings/compute')
async def compute_embeddings_direct(job: EmbeddingJob):
    if not job.items:
        raise HTTPException(status_code=400, detail='no items')
    texts = [it.text for it in job.items]
    embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    # If FAISS available, merge into index
    if HAS_FAISS:
        with INDEX_LOCK:
            if FAISS_INDEX is None:
                d = embs.shape[1]
                FAISS_INDEX_local = faiss.IndexFlatIP(d)
                # normalize
                norms = np.linalg.norm(embs, axis=1, keepdims=True)
                emb_norm = embs / np.maximum(norms, 1e-12)
                FAISS_INDEX_local.add(emb_norm.astype('float32'))
                # set global
                global FAISS_INDEX, META
                FAISS_INDEX = FAISS_INDEX_local
                META = [ {'path':it.path} for it in job.items ]
            else:
                norms = np.linalg.norm(embs, axis=1, keepdims=True)
                emb_norm = embs / np.maximum(norms, 1e-12)
                FAISS_INDEX.add(emb_norm.astype('float32'))
                META.extend([ {'path':it.path} for it in job.items ])
            save_faiss_index(FAISS_INDEX, META)
    else:
        # NPZ fallback
        if os.path.exists(INDEX_NPZ):
            data = np.load(INDEX_NPZ, allow_pickle=True)
            existing = data['embeddings'] if 'embeddings' in data else None
            meta_raw = data['meta'] if 'meta' in data else np.array([])
            meta_list = [json.loads(x) for x in meta_raw.tolist()] if len(meta_raw)>0 else []
            if existing is None:
                new_embs = embs
                new_meta = [ {'path':it.path} for it in job.items ]
            else:
                new_embs = np.vstack([existing, embs])
                new_meta = meta_list + [ {'path':it.path} for it in job.items ]
            save_npz(new_embs, new_meta)
        else:
            save_npz(embs, [ {'path':it.path} for it in job.items ])
    r.publish('ml:events', json.dumps({'type':'job_complete','job_id': job.job_id or 'inline'}))
    # log job complete
    with open(JOBS_LOG,'a') as f:
        f.write(json.dumps({'ts': time.time(), 'job_id': job.job_id or 'inline', 'type':'complete', 'added': len(job.items)}) + '\n')
    return {'ok':True, 'added': len(job.items)}

@app.post('/ml/suggest')
async def suggest(req: SuggestRequest):
    # If FAISS present, use it
    if HAS_FAISS and FAISS_INDEX is not None:
        q_emb = model.encode([req.query], convert_to_numpy=True)[0]
        q_norm = q_emb / np.linalg.norm(q_emb)
        with INDEX_LOCK:
            D, I = FAISS_INDEX.search(np.array([q_norm.astype('float32')]), req.top_k)
            results = []
            for score, idx in zip(D[0].tolist(), I[0].tolist()):
                if idx < 0 or idx >= len(META): continue
                results.append({'score': float(score), 'meta': META[idx]})
        # simple boosting by centroid similarity (learned pattern)
        centroid_boost = 1.0
        if len(META) > 0:
            try:
                centroid_path = os.path.join(DATA_DIR,'centroid.npy')
                if os.path.exists(centroid_path):
                    centroid = np.load(centroid_path)
                    centroid = centroid / np.linalg.norm(centroid)
                    boost = float(np.dot(q_norm, centroid))
                    centroid_boost = 1.0 + 0.2 * boost
            except Exception:
                centroid_boost = 1.0
        for r in results:
            r['score'] = r['score'] * centroid_boost
        return {'ok':True, 'results': results}
    # NPZ fallback
    if os.path.exists(INDEX_NPZ):
        data = np.load(INDEX_NPZ, allow_pickle=True)
        embs = data['embeddings'] if 'embeddings' in data else None
        meta_raw = data['meta'] if 'meta' in data else np.array([])
        if embs is None:
            return {'ok':True, 'results': []}
        q_emb = model.encode([req.query], convert_to_numpy=True)[0]
        embs_norm = embs / np.linalg.norm(embs, axis=1, keepdims=True)
        q_norm = q_emb / np.linalg.norm(q_emb)
        sims = np.dot(embs_norm, q_norm)
        idx = np.argsort(-sims)[:req.top_k]
        results = []
        for i in idx:
            results.append({'score': float(sims[i]), 'meta': json.loads(meta_raw[i])})
        return {'ok':True, 'results': results}
    return {'ok':True, 'results': []}

@app.post('/ml/event/click')
async def log_click(payload: dict):
    try:
        entry = {'ts': time.time(), 'payload': payload}
        with open(CLICK_LOG,'a') as f:
            f.write(json.dumps(entry) + '\n')
        # publish for retraining pipeline
        r.publish('ml:events', json.dumps({'type':'click_logged','payload': payload}))
        return {'ok':True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/track')
async def track_event(request: Request):
    """Receive telemetry from tracker snippet (beacon or fetch) and enqueue for learner.
    Publishes an immediate insight for real-time dashboards.
    """
    try:
        data = await request.json()
    except Exception:
        # fallback to raw body
        try:
            body = await request.body()
            data = json.loads(body.decode('utf-8') or '{}')
        except Exception:
            data = {}
    # sanitize and limit sizes
    ev = {
        'path': (data.get('path') or '')[:200],
        'title': (data.get('title') or '')[:200],
        'referrer': (data.get('referrer') or '')[:200],
        'ts': data.get('ts') or time.time()
    }
    try:
        # enqueue for learner
        r.lpush('tracking:events', json.dumps(ev))
        # persist
        with open(TRACK_LOG,'a') as f:
            f.write(json.dumps(ev) + '\n')
        # publish immediate insight for realtime dashboards
        r.publish('ml:insights', json.dumps({'type':'event_received','event':ev}))
        return {'ok':True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/ml/index/status')
async def index_status():
    if HAS_FAISS and FAISS_INDEX is not None:
        return {'ok':True, 'count': int(FAISS_INDEX.ntotal)}
    if os.path.exists(INDEX_NPZ):
        data = np.load(INDEX_NPZ, allow_pickle=True)
        if 'embeddings' in data:
            return {'ok':True, 'count': int(data['embeddings'].shape[0])}
    return {'ok':True, 'count': 0}

@app.get('/ml/admin/jobs')
async def get_jobs(user: str = Depends(get_current_user)):
    # return last 500 jobs from log
    if not os.path.exists(JOBS_LOG):
        return {'ok':True, 'jobs': []}
    jobs = []
    with open(JOBS_LOG,'r') as f:
        for line in f:
            try:
                jobs.append(json.loads(line))
            except:
                continue
    return {'ok':True, 'jobs': jobs[-500:]}

@app.post('/ml/admin/rebuild-index')
async def rebuild_index(background: BackgroundTasks, user: str = Depends(get_current_user)):
    # Trigger background training script that builds a persistent FAISS index and swaps atomically
    try:
        def run_training():
            script = os.path.join(os.getcwd(),'scripts','train_and_swap.py')
            cmd = ['python3', script, '--data-dir', DATA_DIR]
            subprocess.call(cmd)
            # publish event
            r.publish('ml:insights', json.dumps({'type':'rebuild_complete','ts':time.time()}))
        background.add_task(run_training)
        return {'ok':True, 'message':'rebuild started'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/health')
async def health():
    return {'ok':True}
