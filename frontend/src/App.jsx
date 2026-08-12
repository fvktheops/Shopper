import React, { useEffect, useState } from 'react'
import axios from 'axios'

const API = import.meta.env.VITE_API_BASE || 'http://localhost:4000'

export default function App(){
  const [repos, setRepos] = useState([])
  const [name, setName] = useState('')
  const [owner, setOwner] = useState('fvktheops')

  useEffect(()=>{ fetchRepos() }, [])

  async function fetchRepos(){
    try{
      const res = await axios.get(`${API}/api/repos`)
      setRepos(res.data)
    }catch(e){ console.error(e) }
  }

  async function createRepo(){
    if(!name) return alert('Name required')
    try{
      await axios.post(`${API}/api/repos`, { owner, name })
      setName('')
      fetchRepos()
      alert('Repository created')
    }catch(e){
      console.error(e)
      alert(e.response?.data?.error || 'Failed to create')
    }
  }

  return (
    <div style={{fontFamily: 'Inter, system-ui, Arial', padding:24, maxWidth:1100, margin:'0 auto'}}>
      <header style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20}}>
        <h1 style={{margin:0}}>LUVORA</h1>
        <div style={{color:'#666'}}>Public demo - Git-like platform scaffold</div>
      </header>

      <section style={{display:'flex', gap:20}}>
        <div style={{flex:2}}>
          <div style={{background:'#fff', padding:16, borderRadius:8, border:'1px solid #eee'}}>
            <h2>Create repository</h2>
            <div style={{display:'flex', gap:8, marginTop:8}}>
              <input value={owner} onChange={e=>setOwner(e.target.value)} style={{padding:8}} />
              <input value={name} onChange={e=>setName(e.target.value)} placeholder="repo-name" style={{padding:8}} />
              <button onClick={createRepo} style={{padding:'8px 12px'}}>Create</button>
            </div>
          </div>

          <div style={{marginTop:16, background:'#fff', padding:16, borderRadius:8, border:'1px solid #eee'}}>
            <h2>Repositories</h2>
            <ul>
              {repos.map(r=> (
                <li key={`${r.owner}/${r.name}`} style={{padding:'8px 0', borderBottom:'1px solid #f1f1f1'}}>
                  <strong>{r.owner}/{r.name}</strong>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <aside style={{flex:1}}>
          <div style={{background:'#fff', padding:16, borderRadius:8, border:'1px solid #eee'}}>
            <h3>Quick links</h3>
            <ul>
              <li>Issues (TODO)</li>
              <li>Pull requests (TODO)</li>
              <li>Code viewer (TODO)</li>
            </ul>
          </div>
        </aside>
      </section>
    </div>
  )
}
