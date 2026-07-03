/** Pure display helpers for the Web SPA (unit-testable). */

const PRESENCE_SORT_ORDER = { available: 0, away: 1, busy: 2, offline: 3 };

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

export function findLocalContact(contacts, localJid) {
  if (!localJid) return null;
  const needle = localJid.toLowerCase();
  return contacts.find((c) => c.jid?.toLowerCase() === needle) || null;
}

export function isTransportConnected(connection) {
  if (!connection?.transports?.length) return false;
  return connection.transports.some((t) => t.state === 'connected');
}

export function isAwaitingConnection(connection) {
  return !isTransportConnected(connection);
}

export function formatLocalIdentity(localJid, localContact = null) {
  if (!localJid) return 'You: …';
  if (localContact) {
    return `You: ${localContact.name} (${localJid})`;
  }
  return `You: ${localJid} · not listed in address book`;
}

export function formatHashCompact(contentHash, shortLen = 12) {
  if (!contentHash) return '';
  const short = contentHash.replace('SHA256:', '').slice(0, shortLen);
  return `Book ${short}…`;
}

export function sortContacts(contacts, presence, mode = 'status') {
  const list = [...contacts];
  if (mode === 'name') {
    return list.sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }));
  }
  return list.sort((a, b) => {
    const aShow = presence[a.id]?.show || 'offline';
    const bShow = presence[b.id]?.show || 'offline';
    const orderDiff = (PRESENCE_SORT_ORDER[aShow] ?? 99) - (PRESENCE_SORT_ORDER[bShow] ?? 99);
    if (orderDiff !== 0) return orderDiff;
    return (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' });
  });
}

export function prepareContactList(contacts, presence, { needle = '', sortMode = 'status' } = {}) {
  const filtered = filterContacts(contacts, needle);
  return sortContacts(filtered, presence, sortMode);
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

export function formatSyncStatusLine(syncStatus) {
  if (!syncStatus) return '';
  if (!syncStatus.secret_configured) {
    return 'Not configured — set addressbook.sync.secret in config';
  }
  const state = syncStatus.enabled ? 'Enabled' : 'Disabled';
  const mode = syncStatus.auto_apply ? 'auto-apply' : 'manual review';
  return `${state} · ${mode} · ${syncStatus.pending_count ?? 0} pending`;
}

export function formatPendingUpdate(update) {
  if (!update) return '';
  return `${update.action || '?'} from ${update.from_jid || '?'} (${update.contact_id || '?'})`;
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
