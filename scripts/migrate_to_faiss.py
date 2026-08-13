#!/usr/bin/env python3
"""Prototype FAISS migration script.
- Loads existing NPZ index at ml-data/index.npz
- Builds a FAISS index (IndexFlatIP over normalized vectors)
- Writes out faiss_index.bin and meta.json alongside the NPZ

Notes:
- Ensure faiss is installed in the environment (pip install faiss-cpu) - platform-dependent package names may vary.
- This is a prototype; for production, configure sharding, persistent storage, and backups.
"""
import os
import sys
import json

try:
    import faiss
except Exception as e:
    print('faiss not available. Install faiss-cpu or faiss-gpu to use this script.')
    print('Error:', e)
    sys.exit(1)

import numpy as np

DATA_DIR = os.environ.get('ML_DATA_DIR','ml-data')
NPZ_PATH = os.path.join(DATA_DIR,'index.npz')
OUT_INDEX = os.path.join(DATA_DIR,'faiss_index.bin')
OUT_META = os.path.join(DATA_DIR,'faiss_meta.json')

if not os.path.exists(NPZ_PATH):
    print('No NPZ index found at', NPZ_PATH)
    sys.exit(1)

arr = np.load(NPZ_PATH, allow_pickle=True)
if 'embeddings' not in arr:
    print('No embeddings found in NPZ')
    sys.exit(1)

embs = arr['embeddings']
meta_raw = arr['meta'] if 'meta' in arr else np.array([])
meta = [json.loads(x) for x in meta_raw.tolist()] if len(meta_raw)>0 else []

# Normalize embeddings for inner product similarity
norms = np.linalg.norm(embs, axis=1, keepdims=True)
embs_norm = embs / np.maximum(norms, 1e-12)

d = embs_norm.shape[1]
index = faiss.IndexFlatIP(d)
index.add(embs_norm.astype('float32'))
faiss.write_index(index, OUT_INDEX)

with open(OUT_META, 'w') as f:
    json.dump(meta, f)

print('FAISS index written to', OUT_INDEX)
print('Meta written to', OUT_META)
