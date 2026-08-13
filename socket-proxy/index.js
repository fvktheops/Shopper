const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { createClient } = require('redis');

const REDIS_URL = process.env.REDIS_URL || 'redis://redis:6379';
const PORT = process.env.SOCKET_PORT || 4002;

async function start(){
  const app = express();
  const server = http.createServer(app);
  const io = new Server(server, {
    cors: { origin: '*', methods: ['GET','POST'] }
  });

  // Redis subscriber
  const sub = createClient({ url: REDIS_URL });
  sub.on('error', (err) => console.error('Redis subscriber error', err));
  await sub.connect();

  await sub.subscribe('ml:events', (message) => {
    try{
      const payload = JSON.parse(message);
      // broadcast to all connected clients
      io.emit('ml:event', payload);
    }catch(e){ console.error('Invalid message', e); }
  });

  io.on('connection', (socket) => {
    console.log('client connected', socket.id);
    socket.on('disconnect', ()=>{ console.log('client disconnected', socket.id); });
  });

  server.listen(PORT, ()=> console.log(`socket-proxy listening on ${PORT}`));
}

start().catch(e=>{ console.error(e); process.exit(1); });
