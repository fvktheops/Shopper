// Tracker snippet to embed in other sites (client-side). Only send telemetry with explicit user consent.
// Usage: include <script src="/static/js/tracker.js"></script> and then call sendTelemetry(payload) after user agrees.

async function sendTelemetry(payload){
  try{
    // minimal payload sanitization/size limits
    const safe = {
      path: payload.path || location.pathname,
      title: (payload.title || document.title || '').slice(0,200),
      referrer: (document.referrer || '').slice(0,200),
      ts: new Date().toISOString()
    };
    navigator.sendBeacon = navigator.sendBeacon || null;
    // Use navigator.sendBeacon when possible to avoid blocking
    const url = (window.__LUVORA_TRACKER_URL__ || '') || '/track';
    const body = JSON.stringify(safe);
    if (navigator.sendBeacon){
      const blob = new Blob([body], {type:'application/json'});
      navigator.sendBeacon(url, blob);
      return true;
    }
    await fetch(url, {method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true});
    return true;
  }catch(e){ console.warn('Telemetry send failed', e); return false; }
}

// Expose to window
window.sendTelemetry = sendTelemetry;
