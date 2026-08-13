#!/usr/bin/env python3
"""Scan a repository directory and submit embeddings job to the ml-service.
Usage: python seed_repo.py /path/to/repo [--ml-url http://localhost:8001]
"""
import sys
import os
import json
import requests
from pathlib import Path

ML_URL = os.environ.get('ML_URL','http://localhost:8001')
API = ML_URL.rstrip('/') + '/ml/embeddings/job'

EXT = {'.py','.js','.ts','.go','.java','.rs','.md','.txt','.yaml','.yml'}


def collect_files(repo_path):
    items = []
    p = Path(repo_path)
    for fp in p.rglob('*'):
        if fp.is_file() and fp.suffix.lower() in EXT:
            size = fp.stat().st_size
            if size > 1024*1024: # skip >1MB
                continue
            text = fp.read_text(errors='ignore')[:10000]
            items.append({'path': str(fp.relative_to(p)), 'text': text})
    return items


def main():
    if len(sys.argv) < 2:
        print('Usage: seed_repo.py /path/to/repo')
        sys.exit(1)
    repo = sys.argv[1]
    items = collect_files(repo)
    if not items:
        print('No files found to seed')
        sys.exit(0)
    payload = {'items': items}
    r = requests.post(API, json=payload)
    print('Status:', r.status_code, r.text)

if __name__ == '__main__':
    main()
