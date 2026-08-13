// ML panel (vanilla JS) - mount with mountMlPanel(container)
// Usage: include this script and call mountMlPanel(document.getElementById('ml-panel-root'))

function mountMlPanel(root){
  if (!root) return;
  root.innerHTML = '';
  const box = document.createElement('div'); box.className = 'card';
  const h = document.createElement('h3'); h.textContent='ML Suggestions';
  const input = document.createElement('textarea'); input.rows=4; input.placeholder='Paste a code snippet or describe what you want...';
  const actions = document.createElement('div'); actions.style.marginTop='8px';
  const btn = document.createElement('button'); btn.className='btn-cta'; btn.textContent='Suggest';
  const seedBtn = document.createElement('button'); seedBtn.textContent='Seed current repo'; seedBtn.style.marginLeft='8px';
  actions.appendChild(btn); actions.appendChild(seedBtn);
  const out = document.createElement('div'); out.style.marginTop='10px';
  box.appendChild(h); box.appendChild(input); box.appendChild(actions); box.appendChild(out);
  root.appendChild(box);

  btn.addEventListener('click', async ()=>{
    const q = input.value.trim(); if (!q) return alert('Enter a query or code snippet');
    out.innerHTML = 'Loading...';
    try{
      const res = await fetch('/ml/suggest', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({query:q, top_k:6}) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'failed');
      if (!data.results || data.results.length===0){ out.innerHTML = '<div class="muted-small">No matches</div>'; return; }
      out.innerHTML = '';
      data.results.forEach(r=>{
        const item = document.createElement('div'); item.className='repo-item';
        const left = document.createElement('div'); left.innerHTML = `<strong>${r.meta.path}</strong><div class=\"muted-small\">score: ${r.score.toFixed(3)}</div>`;
        item.appendChild(left);
        out.appendChild(item);
      });
    }catch(e){ out.innerHTML = '<div class="muted-small">Error: '+e.message+'</div>'; }
  });

  seedBtn.addEventListener('click', async ()=>{
    if (!confirm('Seed embeddings for the current repository by scanning files on the server? This will only work if the server exposes a seeding endpoint and repo path.')) return;
    try{
      const res = await fetch('/ml/seed', { method:'POST' });
      const data = await res.json();
      alert('Seed started: '+ JSON.stringify(data));
    }catch(e){ alert('Seed request failed: '+e.message); }
  });
}
