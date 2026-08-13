const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

const DATABASE_URL = process.env.DATABASE_URL || 'postgres://luvora:luvora@localhost:5432/luvora';

const pool = new Pool({ connectionString: DATABASE_URL });

async function init() {
  // create tables if not exist
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS ssh_keys (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      title TEXT,
      public_key TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS repos (
      id SERIAL PRIMARY KEY,
      owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      name TEXT NOT NULL,
      repo_path TEXT NOT NULL,
      visibility TEXT DEFAULT 'public',
      created_at TIMESTAMP DEFAULT now(),
      UNIQUE(owner_id, name)
    );
  `);
}

module.exports = {
  query: (text, params) => pool.query(text, params),
  init,
  pool
};
