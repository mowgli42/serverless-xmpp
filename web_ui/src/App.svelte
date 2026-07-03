<script>
  import { onMount } from 'svelte';
  import { ChatAPI } from './lib/api.js';

  let api = $state(new ChatAPI());
  let contacts = $state([]);
  let presence = $state({});
  let selectedId = $state(null);
  let selectedName = $state('');
  let messages = $state([]);
  let draft = $state('');
  let status = $state('connecting');
  let health = $state(null);
  let showSettings = $state(false);
  let newContact = $state({ id: '', jid: '', name: '' });

  onMount(() => {
    api.onEvent(handleEvent);
    api.connect();
    loadContacts();
    const interval = setInterval(refreshStatus, 5000);
    return () => {
      clearInterval(interval);
      api.disconnect();
    };
  });

  async function loadContacts() {
    try {
      const result = await api.call('addressbook.list');
      contacts = result.contacts || [];
      presence = result.presence || {};
      status = 'connected';
    } catch (e) {
      status = `error: ${e.message}`;
    }
  }

  async function refreshStatus() {
    try {
      const conn = await api.call('connection.status');
      const transports = conn.transports || [];
      status = transports[0]?.state || 'unknown';
      health = await api.call('system.health');
    } catch {
      status = 'disconnected';
    }
  }

  async function selectContact(contact) {
    selectedId = contact.id;
    selectedName = contact.name;
    await api.call('chat.start', { contact_id: contact.id });
    const result = await api.call('chat.get_history', { chat_id: contact.id, limit: 100 });
    messages = result.messages || [];
  }

  async function sendMessage() {
    const body = draft.trim();
    if (!body || !selectedId) return;
    draft = '';
    messages = [...messages, { direction: 'out', body, status: 'pending', timestamp: new Date().toISOString() }];
    try {
      const result = await api.call('chat.send_message', { chat_id: selectedId, body });
      messages = messages.slice(0, -1).concat(result.message);
    } catch (e) {
      status = `send failed: ${e.message}`;
    }
  }

  async function addContact() {
    if (!newContact.id || !newContact.jid || !newContact.name) return;
    await api.call('addressbook.add', { contact: newContact });
    newContact = { id: '', jid: '', name: '' };
    await loadContacts();
  }

  async function reconnect() {
    await api.call('connection.reconnect');
    await refreshStatus();
  }

  function handleEvent(event, params) {
    if (event === 'message.received' && params.chat_id === selectedId) {
      messages = [...messages, params.message];
    }
    if (event === 'message.updated' && params.chat_id === selectedId) {
      messages = messages.map((m) => (m.id === params.message.id ? params.message : m));
    }
    if (event === 'presence.updated') {
      presence = { ...presence, [params.contact_id]: { show: params.show, status: params.status } };
    }
    if (event === 'addressbook.updated') {
      loadContacts();
    }
    if (event === 'connection.changed') {
      status = params.state;
    }
  }

  function formatTime(ts) {
    if (!ts) return '';
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function presenceColor(id) {
    const show = presence[id]?.show || 'offline';
    return show === 'available' ? 'bg-emerald-400' : show === 'away' ? 'bg-amber-400' : 'bg-slate-500';
  }
</script>

<div class="flex h-screen">
  <aside class="w-72 border-r border-slate-800 flex flex-col bg-slate-900">
    <header class="p-4 border-b border-slate-800">
      <h1 class="text-lg font-semibold">Serverless XMPP</h1>
      <p class="text-xs text-slate-400">Local service · {status}</p>
    </header>
    <div class="p-3">
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm" placeholder="Search contacts..." />
    </div>
    <ul class="flex-1 overflow-y-auto">
      {#each contacts as contact (contact.id)}
        <li>
          <button
            class="w-full text-left px-4 py-3 hover:bg-slate-800 flex items-center gap-3 {selectedId === contact.id ? 'bg-slate-800' : ''}"
            onclick={() => selectContact(contact)}
          >
            <span class="w-2 h-2 rounded-full {presenceColor(contact.id)}"></span>
            <div>
              <div class="font-medium">{contact.name}</div>
              <div class="text-xs text-slate-400">{contact.jid}</div>
            </div>
          </button>
        </li>
      {/each}
    </ul>
    <div class="p-3 border-t border-slate-800">
      <button class="text-sm text-emerald-400" onclick={() => (showSettings = !showSettings)}>
        {showSettings ? 'Hide settings' : 'Settings & contacts'}
      </button>
    </div>
  </aside>

  <main class="flex-1 flex flex-col">
    {#if selectedId}
      <header class="p-4 border-b border-slate-800">
        <h2 class="text-xl font-semibold">{selectedName}</h2>
      </header>
      <div class="flex-1 overflow-y-auto p-4 space-y-3">
        {#each messages as msg (msg.id || msg.timestamp + msg.body)}
          <div class="flex flex-col {msg.direction === 'out' ? 'items-end' : 'items-start'}">
            <div class={msg.direction === 'out' ? 'bubble-out' : 'bubble-in'}>{msg.body}</div>
            <span class="text-xs text-slate-500 mt-1">
              {formatTime(msg.timestamp)}
              {#if msg.status === 'delivered'} ✓{/if}
              {#if msg.status === 'pending'} …{/if}
            </span>
          </div>
        {/each}
      </div>
      <form class="p-4 border-t border-slate-800 flex gap-2" onsubmit={(e) => { e.preventDefault(); sendMessage(); }}>
        <input
          class="flex-1 rounded-lg bg-slate-800 px-4 py-3"
          bind:value={draft}
          placeholder="Type a message..."
        />
        <button class="rounded-lg bg-emerald-600 px-5 py-3 font-medium hover:bg-emerald-500" type="submit">
          Send
        </button>
      </form>
    {:else}
      <div class="flex-1 grid place-items-center text-slate-400">
        Select a contact to start chatting
      </div>
    {/if}
  </main>

  {#if showSettings}
    <aside class="w-80 border-l border-slate-800 bg-slate-900 p-4 space-y-4 overflow-y-auto">
      <h3 class="font-semibold">Service</h3>
      {#if health}
        <div class="text-sm text-slate-400 space-y-1">
          <p>Uptime: {Math.round(health.uptime_seconds)}s</p>
          <p>Contacts: {health.contact_count}</p>
          <p>Outbox: {health.pending_outbox}</p>
        </div>
      {/if}
      <button class="rounded bg-slate-800 px-3 py-2 text-sm" onclick={reconnect}>Reconnect XMPP</button>

      <h3 class="font-semibold pt-4">Add contact</h3>
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm mb-2" placeholder="id" bind:value={newContact.id} />
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm mb-2" placeholder="jid" bind:value={newContact.jid} />
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm mb-2" placeholder="name" bind:value={newContact.name} />
      <button class="rounded bg-emerald-700 px-3 py-2 text-sm" onclick={addContact}>Add</button>
    </aside>
  {/if}
</div>
