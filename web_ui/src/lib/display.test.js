import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  filterContacts,
  presenceColor,
  formatTime,
  buildStatusLine,
  connectionStatusFromError,
  hashCells,
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
