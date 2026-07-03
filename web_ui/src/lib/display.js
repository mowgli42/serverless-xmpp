/** Pure display helpers for the Web SPA (unit-testable). */

export function filterContacts(contacts, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return contacts;
  return contacts.filter(
    (c) =>
      c.name?.toLowerCase().includes(q) ||
      c.jid?.toLowerCase().includes(q) ||
      c.id?.toLowerCase().includes(q),
  );
}

export function presenceColor(show) {
  if (show === 'available') return 'text-green-400';
  if (show === 'away') return 'text-yellow-400';
  if (show === 'busy') return 'text-orange-400';
  return 'text-slate-500';
}

export function formatTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return String(ts).slice(0, 5);
  }
}

export function buildStatusLine(transports = [], contactCount = 0, outbox = 0) {
  const base = transports.map((t) => `${t.transport}:${t.state}`).join(' · ') || 'unknown';
  let line = `${base} · ${contactCount} contacts`;
  if (outbox > 0) line += ` · outbox ${outbox}`;
  return line;
}

export function connectionStatusFromError(error, connected) {
  if (connected) return 'connected';
  if (!error) return 'connecting';
  return `error: ${error.message || error}`;
}

export function hashCells(contentHash = '', hashBlocks = [], grid = 8) {
  const hex = contentHash.startsWith('SHA256:') ? contentHash.slice(7) : contentHash;
  const palette = [
    '#1e1e2e', '#45475a', '#585b70', '#6c7086',
    '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
    '#94e2d5', '#89b4fa', '#cba6f7', '#f5c2e7',
    '#b4befe', '#74c7ec', '#89dceb', '#a6adc8',
  ];
  if (hashBlocks.length >= grid * grid) {
    return hashBlocks.slice(0, grid * grid);
  }
  return hex
    .split('')
    .map((ch) => palette[parseInt(ch, 16)] || '#45475a')
    .slice(0, grid * grid);
}
