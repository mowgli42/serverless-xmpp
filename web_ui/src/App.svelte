<script>
  import { onMount } from 'svelte';
  import { ChatAPI } from './lib/api.js';
  import HashGrid from './lib/HashGrid.svelte';
  import {
    buildStatusLine,
    connectionStatusFromError,
    findLocalContact,
    formatHashCompact,
    formatLocalIdentity,
    formatTime,
    isAwaitingConnection,
    prepareContactList,
  } from './lib/display.js';

  let api = $state(new ChatAPI(import.meta.env.VITE_API_URL || undefined));
  let contacts = $state([]);
  let presence = $state({});
  let addressbookStatus = $state(null);
  let selectedId = $state(null);
  let selectedName = $state('');
  let messages = $state([]);
  let draft = $state('');
  let status = $state('connecting');
  let health = $state(null);
  let connectionInfo = $state(null);
  let discoveredPeers = $state([]);
  let contactSearch = $state('');
  let sortMode = $state('status');
  let showSettings = $state(false);
  let sidebarOpen = $state(true);
  let newContact = $state({ id: '', jid: '', name: '', preferred_transport: 'direct-p2p', direct: { host: '127.0.0.1', port: 5224, public_key_fingerprint: '' } });

  let localJid = $derived(connectionInfo?.local_jid || '');
  let localContact = $derived(findLocalContact(contacts, localJid));
  let localIdentity = $derived(formatLocalIdentity(localJid, localContact));
  let awaitingConnection = $derived(isAwaitingConnection(connectionInfo));
  let filteredContacts = $derived(
    prepareContactList(contacts, presence, { needle: contactSearch, sortMode }),
  );

  onMount(() => {
    api.onEvent(handleEvent);
    api.connect();
    waitForService().then(async () => {
      await refreshStatus();
      await loadContacts();
    });
    const interval = setInterval(() => {
      refreshStatus();
      refreshDiscovery();
    }, 5000);
    return () => {
      clearInterval(interval);
      api.disconnect();
    };
  });

  async function waitForService() {
    for (let i = 0; i < 30; i++) {
      if (api.connected) return;
      await new Promise((r) => setTimeout(r, 250));
    }
    throw new Error('Service connection timeout');
  }

  async function loadContacts() {
    try {
      const result = await api.call('addressbook.list');
      contacts = result.contacts || [];
      presence = result.presence || {};
      addressbookStatus = result.status || null;
      status = 'connected';
    } catch (e) {
      status = connectionStatusFromError(e, false);
    }
  }

  async function refreshStatus() {
    try {
      connectionInfo = await api.call('connection.status');
      health = await api.call('system.health');
      status = buildStatusLine(
        connectionInfo.transports || [],
        contacts.length,
        health?.pending_outbox || 0,
      );
    } catch {
      status = 'disconnected';
    }
  }

  async function refreshDiscovery() {
    try {
      const result = await api.call('discovery.list');
      discoveredPeers = result.peers || [];
    } catch {
      discoveredPeers = [];
    }
  }

  async function selectContact(contact) {
    selectedId = contact.id;
    selectedName = contact.name;
    if (window.matchMedia('(max-width: 768px)').matches) {
      sidebarOpen = false;
    }
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
    newContact = { id: '', jid: '', name: '', preferred_transport: 'direct-p2p', direct: { host: '127.0.0.1', port: 5224, public_key_fingerprint: '' } };
    await loadContacts();
  }

  async function applyDiscovery(peer) {
    const match = contacts.find((c) => c.jid === peer.jid);
    if (!match) return;
    await api.call('discovery.apply', { contact_id: match.id });
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
      if (params.content_hash) {
        addressbookStatus = {
          ...(addressbookStatus || {}),
          version: params.version,
          content_hash: params.content_hash,
        };
      }
    }
    if (event === 'discovery.updated') {
      discoveredPeers = params.peers || [];
    }
    if (event === 'connection.changed') {
      status = params.state;
    }
  }

  function presenceDotColor(id) {
    const show = presence[id]?.show || 'offline';
    return show === 'available' ? 'bg-emerald-400' : show === 'away' ? 'bg-amber-400' : 'bg-slate-500';
  }

  function handleComposerKeydown(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendMessage();
    }
  }
</script>

<div class="flex h-screen relative">
  {#if sidebarOpen}
    <button
      class="md:hidden fixed inset-0 bg-black/50 z-10"
      aria-label="Close contacts sidebar"
      onclick={() => (sidebarOpen = false)}
    ></button>
  {/if}

  <aside
    class="w-72 border-r border-slate-800 flex flex-col bg-slate-900 shrink-0
      fixed md:relative inset-y-0 left-0 z-20 transform transition-transform duration-200
      {sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}"
    aria-label="Contacts sidebar"
  >
    <header class="p-4 border-b border-slate-800">
      <h1 class="text-lg font-semibold">Serverless XMPP</h1>
      <p class="text-xs text-emerald-500/80">Local service mode</p>
      <p class="text-xs text-slate-400 truncate" title={status}>{status}</p>
      <p class="text-xs text-slate-200 mt-2 font-medium">{localIdentity}</p>
      {#if addressbookStatus}
        <p class="text-xs text-slate-500 mt-1">
          Address book v{addressbookStatus.version} · {addressbookStatus.contact_count} contacts
        </p>
        {#if awaitingConnection}
          <p class="text-xs text-amber-400/90 mt-1">Awaiting connection — verify book hash</p>
          <HashGrid
            contentHash={addressbookStatus.content_hash}
            hashBlocks={addressbookStatus.hash_blocks}
            grid={8}
          />
        {:else}
          <p class="text-xs text-slate-500 mt-1">{formatHashCompact(addressbookStatus.content_hash)}</p>
        {/if}
      {/if}
    </header>
    <div class="p-3 space-y-2">
      <input
        class="w-full rounded bg-slate-800 px-3 py-2 text-sm"
        placeholder="Search contacts..."
        bind:value={contactSearch}
        aria-label="Search contacts"
      />
      <button
        type="button"
        class="text-xs text-slate-400 hover:text-slate-200"
        onclick={() => (sortMode = sortMode === 'status' ? 'name' : 'status')}
        aria-label="Toggle contact sort order"
      >
        Sort: {sortMode === 'status' ? 'connection status' : 'name'}
      </button>
    </div>
    <ul class="flex-1 overflow-y-auto" role="list">
      {#each filteredContacts as contact (contact.id)}
        <li>
          <button
            class="w-full text-left px-4 py-3 hover:bg-slate-800 flex items-center gap-3 {selectedId === contact.id ? 'bg-slate-800' : ''}"
            onclick={() => selectContact(contact)}
            aria-current={selectedId === contact.id ? 'true' : undefined}
          >
            <span class="w-2 h-2 rounded-full {presenceDotColor(contact.id)}" aria-hidden="true"></span>
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

  <main class="flex-1 flex flex-col min-w-0">
    <header class="p-4 border-b border-slate-800 flex items-center gap-3">
      <button
        class="md:hidden rounded bg-slate-800 px-3 py-2 text-sm"
        onclick={() => (sidebarOpen = !sidebarOpen)}
        aria-expanded={sidebarOpen}
        aria-controls="contacts-sidebar"
      >
        Contacts
      </button>
      {#if selectedId}
        <h2 class="text-xl font-semibold truncate">{selectedName}</h2>
      {/if}
    </header>

    {#if selectedId}
      <div class="flex-1 overflow-y-auto p-4 space-y-3" role="log" aria-live="polite" aria-label="Chat messages">
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
        <textarea
          class="flex-1 rounded-lg bg-slate-800 px-4 py-3 resize-none min-h-[3rem]"
          bind:value={draft}
          placeholder="Type a message... (Ctrl+Enter to send)"
          aria-label="Message composer"
          onkeydown={handleComposerKeydown}
        ></textarea>
        <button class="rounded-lg bg-emerald-600 px-5 py-3 font-medium hover:bg-emerald-500 self-end" type="submit">
          Send
        </button>
      </form>
    {:else}
      <div class="flex-1 grid place-items-center text-slate-400 p-4 text-center">
        Select a contact to start chatting
      </div>
    {/if}
  </main>

  {#if showSettings}
    <aside class="w-full sm:w-80 border-l border-slate-800 bg-slate-900 p-4 space-y-4 overflow-y-auto fixed sm:relative inset-y-0 right-0 z-30" aria-label="Settings panel">
      <div class="flex justify-between items-center sm:hidden">
        <h3 class="font-semibold">Settings</h3>
        <button class="text-sm text-slate-400" onclick={() => (showSettings = false)}>Close</button>
      </div>
      <h3 class="font-semibold hidden sm:block">Address book</h3>
      {#if addressbookStatus}
        <div class="text-sm text-slate-400 space-y-2">
          <p>Version: {addressbookStatus.version}</p>
          <p class="text-xs break-all">{addressbookStatus.content_hash}</p>
          <HashGrid
            contentHash={addressbookStatus.content_hash}
            hashBlocks={addressbookStatus.hash_blocks}
            grid={8}
          />
          <p class="text-xs text-slate-500 break-all">File: {addressbookStatus.primary_path}</p>
          {#if addressbookStatus.warnings?.length}
            <ul class="text-xs text-amber-400/90 space-y-1">
              {#each addressbookStatus.warnings as w}
                <li>• {w}</li>
              {/each}
            </ul>
          {/if}
        </div>
        <button class="rounded bg-slate-800 px-3 py-2 text-sm" onclick={async () => {
          addressbookStatus = await api.call('addressbook.reload');
          await loadContacts();
        }}>Reload from disk</button>
      {/if}

      <h3 class="font-semibold pt-4 hidden sm:block">Service</h3>
      {#if connectionInfo?.transports?.length}
        <ul class="text-sm text-slate-400 space-y-1">
          {#each connectionInfo.transports as t}
            <li>{t.transport}: {t.state}</li>
          {/each}
        </ul>
      {/if}
      {#if connectionInfo?.p2p_fingerprint}
        <p class="text-xs text-slate-500 break-all">P2P fingerprint: {connectionInfo.p2p_fingerprint}</p>
        <p class="text-xs text-slate-500">Listen port: {connectionInfo.p2p_listen_port}</p>
      {/if}
      {#if discoveredPeers.length}
        <div class="pt-2">
          <h4 class="text-sm font-medium text-slate-300">LAN peers (mDNS)</h4>
          <ul class="text-xs text-slate-400 space-y-2 mt-2">
            {#each discoveredPeers as peer}
              <li class="flex flex-col gap-1">
                <span>{peer.jid} — {peer.host}:{peer.port}</span>
                <button class="text-emerald-400 text-left" onclick={() => applyDiscovery(peer)}>Apply to contact</button>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
      {#if health}
        <div class="text-sm text-slate-400 space-y-1 pt-2">
          <p>Uptime: {Math.round(health.uptime_seconds)}s</p>
          <p>Contacts: {health.contact_count}</p>
          <p>Outbox: {health.pending_outbox}</p>
        </div>
      {/if}
      <button class="rounded bg-slate-800 px-3 py-2 text-sm" onclick={reconnect}>Reconnect transports</button>

      <h3 class="font-semibold pt-4">Add contact</h3>
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm mb-2" placeholder="id" bind:value={newContact.id} aria-label="Contact id" />
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm mb-2" placeholder="jid" bind:value={newContact.jid} aria-label="Contact JID" />
      <input class="w-full rounded bg-slate-800 px-3 py-2 text-sm mb-2" placeholder="name" bind:value={newContact.name} aria-label="Contact name" />
      <button class="rounded bg-emerald-700 px-3 py-2 text-sm" onclick={addContact}>Add</button>
    </aside>
  {/if}
</div>
