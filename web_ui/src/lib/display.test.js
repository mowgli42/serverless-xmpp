import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  filterContacts,
  presenceColor,
  formatTime,
  buildStatusLine,
  connectionStatusFromError,
  hashCells,
  findLocalContact,
  formatLocalIdentity,
  formatHashCompact,
  isAwaitingConnection,
  isTransportConnected,
  sortContacts,
  prepareContactList,
} from './display.js';

describe('filterContacts', () => {
  const contacts = [
    { id: 'bob', name: 'Bob', jid: 'bob@p2p.local' },
    { id: 'carol', name: 'Carol', jid: 'carol@p2p.local' },
  ];

  it('returns all when query empty', () => {
    expect(filterContacts(contacts, '')).toHaveLength(2);
  });

  it('filters by jid substring', () => {
    expect(filterContacts(contacts, 'carol@')).toHaveLength(1);
  });
});

describe('presenceColor', () => {
  it('maps available to green', () => {
    expect(presenceColor('available')).toContain('green');
  });

  it('maps offline to slate', () => {
    expect(presenceColor('offline')).toContain('slate');
  });
});

describe('formatTime', () => {
  it('formats ISO timestamp', () => {
    const t = formatTime('2026-07-03T14:30:00Z');
    expect(t).toMatch(/\d/);
  });
});

describe('buildStatusLine', () => {
  it('includes transport and contact count', () => {
    const line = buildStatusLine([{ transport: 'direct-p2p', state: 'connected' }], 3, 0);
    expect(line).toContain('direct-p2p:connected');
    expect(line).toContain('3 contacts');
  });

  it('shows outbox when pending', () => {
    const line = buildStatusLine([], 1, 5);
    expect(line).toContain('outbox 5');
  });
});

describe('connectionStatusFromError', () => {
  it('returns connected when api connected', () => {
    expect(connectionStatusFromError(null, true)).toBe('connected');
  });

  it('returns error string on failure', () => {
    expect(connectionStatusFromError(new Error('timeout'), false)).toBe('error: timeout');
  });
});

describe('hashCells', () => {
  it('uses hash blocks when provided', () => {
    const blocks = Array.from({ length: 64 }, (_, i) => `#${i.toString(16).padStart(6, '0')}`);
    expect(hashCells('', blocks, 8)).toHaveLength(64);
  });

  it('derives from hex when blocks missing', () => {
    const cells = hashCells('SHA256:' + 'a'.repeat(64), [], 8);
    expect(cells).toHaveLength(64);
  });
});

describe('connection-aware display', () => {
  const contacts = [
    { id: 'bob', name: 'Bob', jid: 'bob@p2p.local' },
    { id: 'carol', name: 'Carol', jid: 'carol@p2p.local' },
  ];
  const presence = {
    bob: { show: 'available' },
    carol: { show: 'offline' },
  };

  it('finds local contact by jid', () => {
    expect(findLocalContact(contacts, 'bob@p2p.local')?.name).toBe('Bob');
  });

  it('formats local identity', () => {
    expect(formatLocalIdentity('bob@p2p.local', contacts[0])).toContain('Bob');
    expect(formatLocalIdentity('ghost@p2p.local')).toContain('not listed');
  });

  it('detects awaiting connection', () => {
    expect(isAwaitingConnection({ transports: [{ state: 'connecting' }] })).toBe(true);
    expect(isTransportConnected({ transports: [{ state: 'connected' }] })).toBe(true);
  });

  it('sorts by status then name', () => {
    const ordered = sortContacts(contacts, presence, 'status');
    expect(ordered[0].id).toBe('bob');
  });

  it('prepares filtered sorted list', () => {
    const list = prepareContactList(contacts, presence, { needle: 'car', sortMode: 'name' });
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe('carol');
  });

  it('formats compact hash', () => {
    expect(formatHashCompact('SHA256:' + 'ab'.repeat(32))).toContain('Book abababababab');
  });
});
