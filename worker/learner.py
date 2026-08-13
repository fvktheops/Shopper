"""
Worker that consumes tracking events from Redis and performs lightweight online clustering (centroid-based)
to learn data patterns over time. It avoids heavy ML libraries and implements incremental centroid updates.
"""
import os
import time
import json
import redis
import numpy as np
from sentence_transformers import SentenceTransformer

REDIS_URL = os.environ.get('REDIS_URL','redis://redis:6379/0')
DATA_DIR = os.environ.get('ML_DATA_DIR','/data')
CENTROIDS_PATH = os.path.join(DATA_DIR,'centroids.npy')
COUNTS_PATH = os.path.join(DATA_DIR,'centroid_counts.json')
PROCESSED_PATH = os.path.join(DATA_DIR,'events_processed.jsonl')
MODEL_NAME = os.environ.get('SENTENCE_MODEL','all-MiniLM-L6-v2')
THRESHOLD = float(os.environ.get('CLUSTER_SIM_THRESHOLD','0.75'))

os.makedirs(DATA_DIR, exist_ok=True)

r = redis.from_url(REDIS_URL, decode_responses=True)
model = SentenceTransformer(MODEL_NAME)

# Load centroids and counts
if os.path.exists(CENTROIDS_PATH):
    centroids = np.load(CENTROIDS_PATH)
else:
    centroids = np.zeros((0, model.get_sentence_embedding_dimension()))

if os.path.exists(COUNTS_PATH):
    with open(COUNTS_PATH,'r') as f: counts = json.load(f)
else:
    counts = []

print('Learner started. Centroids:', centroids.shape[0])

def save_state():
    if centroids.shape[0]>0:
        np.save(CENTROIDS_PATH, centroids)
    with open(COUNTS_PATH,'w') as f: json.dump(counts, f)

# simple cosine similarity

def cos_sim(a,b):
    return float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b)+1e-12))

while True:
    try:
        job = r.brpop('tracking:events', timeout=5)
        if not job:
            time.sleep(0.5)
            continue
        payload = job[1]
        ev = json.loads(payload)
        text = (ev.get('title') or '') + ' ' + (ev.get('path') or '')
        emb = model.encode([text], convert_to_numpy=True)[0]
        emb = emb / np.linalg.norm(emb)
        # find best centroid
        if centroids.shape[0] == 0:
            centroids = np.vstack([centroids, emb])
            counts.append(1)
            cluster_id = 0
            changed = True
        else:
            sims = np.dot(centroids, emb)
            best = int(np.argmax(sims))
            best_sim = sims[best]
            if best_sim < THRESHOLD:
                # create new centroid
                centroids = np.vstack([centroids, emb])
                counts.append(1)
                cluster_id = centroids.shape[0]-1
                changed = True
            else:
                # update centroid by moving average
                n = counts[best]
                new_centroid = (centroids[best]*n + emb) / (n+1)
                new_centroid = new_centroid / np.linalg.norm(new_centroid)
                centroids[best] = new_centroid
                counts[best] = n+1
                cluster_id = best
                changed = True
        # persist state regularly
        try:
            save_state()
            # append processed event
            with open(PROCESSED_PATH,'a') as f:
                f.write(json.dumps({'cluster':cluster_id,'event':ev}) + '\n')
            # publish insight
            r.publish('ml:insights', json.dumps({'type':'cluster_update','cluster':cluster_id,'event':ev}))
        except Exception as e:
            print('persist error', e)
    except Exception as e:
        print('Learner error', e)
        time.sleep(2)
