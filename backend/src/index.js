const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');
const http = require('http');
const { Server } = require('socket.io');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const cookieParser = require('cookie-parser');

require('dotenv').config();

const db = require('./db');

const PORT = process.env.PORT || 4000;
const REPO_ROOT = process.env.REPO_ROOT || path.join(__dirname, '..', '..', 'data', 'repos');
const JWT_SECRET = process.env.JWT_SECRET || 'dev_secret_change_me';

fs.mkdirSync(REPO_ROOT, { recursive: true });

const app = express();
app.use(cors({ origin: true, credentials: true }));
app.use(express.json());
app.use(cookieParser());

const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

io.on('connection', (socket) => {
  console.log('socket connected', socket.id);
  socket.on('join_repo', (room) => socket.join(room));
});

async function createBareRepo(repoDir) {
  return new Promise((resolve, reject) => {
    // git init --bare
    exec(`git init --bare "${repoDir}"`, (err, stdout, stderr) => {
      if (err) return reject(err);
      resolve({ stdout, stderr });
    });
  });
}

// auth helpers
function signToken(user) {
  return jwt.sign({ id: user.id, username: user.username }, JWT_SECRET, { expiresIn: '7d' });
}

async function requireAuth(req, res, next) {
  try {
    const token = req.cookies.token;
    if (!token) return res.status(401).json({ error: 'unauthenticated' });
    const data = jwt.verify(token, JWT_SECRET);
    const r = await db.query('SELECT id, username, email FROM users WHERE id=$1', [data.id]);
    if (r.rowCount === 0) return res.status(401).json({ error: 'invalid token' });
    req.user = r.rows[0];
    next();
  } catch (err) {
    console.error(err);
    return res.status(401).json({ error: 'unauthenticated' });
  }
}

app.get('/api/health', (req, res) => res.json({ ok: true }));

// register
app.post('/api/auth/register', async (req, res) => {
  try {
    const { username, email, password } = req.body;
    if (!username || !email || !password) return res.status(400).json({ error: 'missing fields' });
    const hash = await bcrypt.hash(password, 10);
    const result = await db.query('INSERT INTO users (username, email, password_hash) VALUES ($1,$2,$3) RETURNING id, username, email', [username, email, hash]);
    const user = result.rows[0];
    const token = signToken(user);
    res.cookie('token', token, { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax' });
    res.json({ user });
  } catch (err) {
    console.error(err);
    if (err.code === '23505') return res.status(409).json({ error: 'user exists' });
    res.status(500).json({ error: 'internal' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) return res.status(400).json({ error: 'missing' });
    const r = await db.query('SELECT id, username, email, password_hash FROM users WHERE email=$1', [email]);
    if (r.rowCount === 0) return res.status(401).json({ error: 'invalid credentials' });
    const user = r.rows[0];
    const ok = await bcrypt.compare(password, user.password_hash);
    if (!ok) return res.status(401).json({ error: 'invalid credentials' });
    const token = signToken(user);
    res.cookie('token', token, { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax' });
    res.json({ user: { id: user.id, username: user.username, email: user.email } });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'internal' });
  }
});

app.post('/api/auth/logout', (req, res) => {
  res.clearCookie('token');
  res.json({ ok: true });
});

app.get('/api/auth/me', requireAuth, (req, res) => {
  res.json({ user: req.user });
});

// SSH key management
app.post('/api/keys', requireAuth, async (req, res) => {
  try {
    const { title, public_key } = req.body;
    if (!public_key) return res.status(400).json({ error: 'public_key required' });
    const r = await db.query('INSERT INTO ssh_keys (user_id, title, public_key) VALUES ($1,$2,$3) RETURNING id, title, public_key', [req.user.id, title || null, public_key]);
    res.status(201).json(r.rows[0]);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'internal' });
  }
});

// Create repository (bare) - requires auth
app.post('/api/repos', requireAuth, async (req, res) => {
  try {
    const { name, visibility = 'public' } = req.body;
    if (!name) return res.status(400).json({ error: 'name required' });
    const owner = req.user.username;
    const ownerDir = path.join(REPO_ROOT, owner);
    const repoDir = path.join(ownerDir, `${name}.git`); // bare repo named name.git

    if (fs.existsSync(repoDir)) return res.status(409).json({ error: 'repo exists' });

    fs.mkdirSync(ownerDir, { recursive: true });

    await createBareRepo(repoDir);

    // write a README commit into a temp repo and push to bare repo to create initial commit
    const tmpDir = path.join('/tmp', `init-${Date.now()}-${Math.random().toString(36).slice(2,8)}`);
    fs.mkdirSync(tmpDir, { recursive: true });
    fs.writeFileSync(path.join(tmpDir, 'README.md'), `# ${name}\n\nCreated on LUVORA by ${owner}`);
    await new Promise((resolve, reject) => {
      exec(`git init && git add README.md && git commit -m "Initial commit" && git remote add origin "${repoDir}" && git push origin master`, { cwd: tmpDir }, (err, stdout, stderr) => {
        // ignore errors in environments where git user is not set
        resolve({ stdout, stderr, err });
      });
    });

    // store in db
    const r = await db.query('INSERT INTO repos (owner_id, name, repo_path, visibility) VALUES ($1,$2,$3,$4) RETURNING id, name, repo_path', [req.user.id, name, repoDir, visibility]);

    io.to(`repo:${owner}/${name}`).emit('repo:created', { owner, name });

    res.status(201).json({ owner, name, id: r.rows[0].id });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'internal' });
  }
});

// list repos from db
app.get('/api/repos', async (req, res) => {
  try {
    const r = await db.query('SELECT r.id, r.name, r.repo_path, r.visibility, u.username AS owner FROM repos r JOIN users u ON u.id = r.owner_id ORDER BY r.created_at DESC');
    res.json(r.rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'internal' });
  }
});

// file viewer - read from bare repo by showing blob using git --no-pager show
app.get('/api/repos/:owner/:repo/README', async (req, res) => {
  try {
    const { owner, repo } = req.params;
    const repoPath = path.join(REPO_ROOT, owner, `${repo}.git`);
    if (!fs.existsSync(repoPath)) return res.status(404).json({ error: 'repo not found' });
    // show last commit README
    exec(`git --git-dir="${repoPath}" --no-pager show master:README.md`, (err, stdout, stderr) => {
      if (err) return res.status(404).json({ error: 'file not found' });
      res.json({ content: stdout });
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'internal' });
  }
});

(async function main(){
  await db.init();
  server.listen(PORT, () => {
    console.log(`LUVORA backend running on port ${PORT}`);
    console.log(`REPO_ROOT: ${REPO_ROOT}`);
  });
})();
