const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { simpleGit, SimpleGit } = require('simple-git');
const http = require('http');
const { Server } = require('socket.io');

require('dotenv').config();

const PORT = process.env.PORT || 4000;
const REPO_ROOT = process.env.REPO_ROOT || path.join(__dirname, '..', 'data', 'repos');

// ensure repo root exists
fs.mkdirSync(REPO_ROOT, { recursive: true });

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

io.on('connection', (socket) => {
  console.log('socket connected', socket.id);
  socket.on('join_repo', (room) => socket.join(room));
});

app.get('/api/health', (req, res) => res.json({ ok: true }));

// Create a new repository (real git)
app.post('/api/repos', async (req, res) => {
  try {
    const { owner = 'anonymous', name } = req.body;
    if (!name) return res.status(400).json({ error: 'name is required' });

    const ownerDir = path.join(REPO_ROOT, owner);
    const repoDir = path.join(ownerDir, name);

    if (fs.existsSync(repoDir)) return res.status(409).json({ error: 'repo already exists' });

    fs.mkdirSync(repoDir, { recursive: true });

    // Initialize a non-bare git repo for easier work-with-files demonstration
    const git = simpleGit(repoDir);

    await git.init();

    // create a README
    fs.writeFileSync(path.join(repoDir, 'README.md'), `# ${name}\n\nRepository created by LUVORA`);
    await git.add('./*');
    await git.commit('Initial commit from LUVORA scaffold');

    // return repository info
    const url = `/repos/${owner}/${name}`;
    return res.status(201).json({ owner, name, url });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: 'internal' });
  }
});

// list repos
app.get('/api/repos', (req, res) => {
  const owners = fs.readdirSync(REPO_ROOT, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name);
  const result = [];
  owners.forEach(owner => {
    const ownerDir = path.join(REPO_ROOT, owner);
    const repos = fs.readdirSync(ownerDir, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name);
    repos.forEach(r => result.push({ owner, name: r }));
  });
  res.json(result);
});

// simple file viewer (read file)
app.get('/api/repos/:owner/:repo/files/*', (req, res) => {
  const { owner, repo } = req.params;
  const relPath = req.params[0] || '';
  const filePath = path.join(REPO_ROOT, owner, repo, relPath);
  if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'not found' });
  if (fs.statSync(filePath).isDirectory()) return res.status(400).json({ error: 'path is a directory' });
  const content = fs.readFileSync(filePath, 'utf8');
  res.json({ path: relPath, content });
});

server.listen(PORT, () => {
  console.log(`LUVORA backend running on port ${PORT}`);
  console.log(`REPO_ROOT: ${REPO_ROOT}`);
});
