import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatAPI } from './api.js';

class MockWebSocket {
  static OPEN = 1;

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.OPEN;
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    this.sent = [];
  }

  send(data) {
    this.sent.push(JSON.parse(data));
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }
}

function connectedApi() {
  const api = new ChatAPI('ws://127.0.0.1:8765/rpc');
  api.ws = new MockWebSocket(api.url);
  api.connected = true;
  return api;
}

describe('ChatAPI', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  it('resolves call results via _handleMessage', async () => {
    const api = connectedApi();
    const resultPromise = api.call('addressbook.list');
    const req = api.ws.sent.at(-1);
    api._handleMessage(
      JSON.stringify({ jsonrpc: '2.0', id: req.id, result: { contacts: [] } }),
    );
    await expect(resultPromise).resolves.toEqual({ contacts: [] });
  });

  it('dispatches push events to handlers', () => {
    const api = connectedApi();
    const events = [];
    api.onEvent((event, params) => events.push({ event, params }));
    api._handleMessage(
      JSON.stringify({ method: 'addressbook.updated', params: { version: 2 } }),
    );
    expect(events[0].event).toBe('addressbook.updated');
    expect(events[0].params.version).toBe(2);
  });

  it('rejects pending calls on connection loss', async () => {
    const api = connectedApi();
    const pending = api.call('system.health');
    api._rejectPending(new Error('Connection closed'));
    await expect(pending).rejects.toThrow('Connection closed');
  });

  it('reports not connected when socket closed', async () => {
    const api = connectedApi();
    api.ws.readyState = 3;
    await expect(api.call('system.health')).rejects.toThrow('Not connected');
  });
});
