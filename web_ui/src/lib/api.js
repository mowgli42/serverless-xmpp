export class ChatAPI {
  constructor(url = 'ws://127.0.0.1:8765/rpc', token = '') {
    this.url = url;
    this.token = token;
    this.ws = null;
    this.pending = new Map();
    this.handlers = new Set();
    this.connected = false;
    this.shouldRun = true;
  }

  onEvent(handler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  async connect() {
    while (this.shouldRun) {
      try {
        this.ws = new WebSocket(this.url);
        await new Promise((resolve, reject) => {
          this.ws.onopen = resolve;
          this.ws.onerror = reject;
        });
        if (this.token) {
          await this.call('auth', { token: this.token });
        }
        this.connected = true;
        this.ws.onmessage = (event) => this._handleMessage(event.data);
        this.ws.onclose = () => {
          this.connected = false;
          this._rejectPending(new Error('Connection closed'));
        };
        await new Promise((resolve) => {
          this.ws.onclose = resolve;
        });
      } catch (err) {
        console.warn('API reconnecting...', err);
        this.connected = false;
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
  }

  disconnect() {
    this.shouldRun = false;
    if (this.ws) this.ws.close();
  }

  call(method, params = {}) {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('Not connected'));
        return;
      }
      const id = crypto.randomUUID();
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }));
    });
  }

  _handleMessage(raw) {
    const message = JSON.parse(raw);
    if (message.id && this.pending.has(message.id)) {
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
      return;
    }
    if (message.method) {
      for (const handler of this.handlers) {
        handler(message.method, message.params || {});
      }
    }
  }

  _rejectPending(err) {
    for (const { reject } of this.pending.values()) reject(err);
    this.pending.clear();
  }
}
