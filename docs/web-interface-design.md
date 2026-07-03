# Web Interface Design (SPA) — Following IxDF Principles

**Framework**: Svelte 5 + Vite + Tailwind CSS + daisyUI (or shadcn-svelte)  
**Target Users**: Desktop/laptop users who want a richer visual experience, multi-tab use, or occasional access from other devices on the LAN.  
**Design Goals**: Modern chat aesthetics, excellent feedback, accessibility, responsive, calm and focused.

## Overall Layout (IxDF: Visibility + Aesthetic & Minimalist Design)

```
┌─────────────────────────────────────────────────────────────────┐
│ Top Nav: Logo | [Service Status Badge] | Your Avatar + Presence | Settings |
├──────────────────────────────┬──────────────────────────────────┤
│ Sidebar                      │ Main Chat Area                   │
│                              │                                  │
│ 🔍 Search contacts...        │  Chat with Alice Example         │
│                              │  [Online • via XMPP]             │
│ ★ Alice Example     [3]      │                                  │
│    alice@jabber...           │  ┌────────────────────────────┐  │
│    ● Online                  │  │ 09:12  You                  │  │
│                              │  │ Hey, how's the garden?     │  │
│   Bob                        │  └────────────────────────────┘  │
│   Carol               [1]    │                                  │
│                              │  ┌────────────────────────────┐  │
│                              │  │ 09:14  Alice                │  │
│                              │  │ It's coming along! 🌱      │  │
│                              │  └────────────────────────────┘  │
│                              │                                  │
│                              │  [Composer: Type message...] [Send] │
└──────────────────────────────┴──────────────────────────────────┘
```

**IxDF Principles Applied**:
- **Visibility of system status**: Prominent service status badge, per-contact presence, per-message delivery indicators (single/double check, pending animation).
- **Match between system and real world**: Classic modern chat layout with bubbles, avatars (future), timestamps, read receipts.
- **Consistency**: Same mental model as the TUI but richer visuals. Keyboard shortcuts where natural (`Enter` to send, `Esc` to close, etc.).
- **User control & freedom**: Easy contact management, quick switcher (Cmd/Ctrl+K), message actions (copy, delete for self, etc.).
- **Error prevention**: Form validation on add/edit contact, disabled send when disconnected.

## Core Components & Interactions

### 1. Sidebar (Contacts)
- Search input with instant filtering (name, JID, tags).
- Grouped or flat list with visual hierarchy.
- Each row: Avatar placeholder (or initials), name, JID snippet, presence dot + status text, unread badge.
- Click = open chat in main pane (replace or new tab-like if we support multiple later).
- Context menu or hover actions: Edit, Remove, Start direct P2P (future).

### 2. Chat Pane
- **Header**: Large name, JID, presence + transport indicator, quick actions (info, mute, close).
- **Message List**:
  - Virtualized for performance.
  - Bubbles with subtle shadows/borders.
  - Outgoing: right-aligned, primary color accent.
  - Incoming: left-aligned, neutral.
  - Hover shows full timestamp + message actions.
  - Delivery status under outgoing messages (optimistic → sent → delivered).
- **Composer** (bottom, sticky):
  - Growing textarea or contenteditable.
  - Send button (disabled when no connection).
  - Attachment button (future).
  - Emoji / formatting toolbar (light touch).
- **Real-time**:
  - New messages auto-append and scroll (unless user has scrolled up — then show "New messages" button).
  - Typing indicator area (when supported).

### 3. Modals & Overlays
- **Add/Edit Contact Modal**: Clean form with live JID validation, optional direct connection fields, tags input, notes textarea. Clear "Save" and "Cancel".
- **Service Settings / Status Modal**: Connection health, manual reconnect, presence setter, API token management (if used).
- **Help / Shortcuts Modal**: Discoverable list of keyboard commands.

## Responsive & Accessibility (Flexibility + Inclusive Design)

- Desktop-first but collapses sidebar on smaller screens (hamburger or bottom nav).
- Full keyboard navigation support.
- ARIA labels, proper contrast (daisyUI themes help), focus indicators.
- Respects `prefers-reduced-motion`.

## State Management & Feedback (Visibility + Feedback)

- Use Svelte stores + the shared `api.ts` WebSocket client.
- Optimistic updates on send (message appears instantly with "sending" style).
- Push events from service update UI reactively (new message, presence change, connection status).
- Clear loading / empty / error states with helpful copy and actions.

## Keyboard Shortcuts (Efficiency)

| Shortcut       | Action                     |
|----------------|----------------------------|
| `Cmd/Ctrl + K` | Quick contact switcher     |
| `Enter`        | Send message               |
| `Esc`          | Close current chat / modal |
| `?`            | Open help                  |
| `Cmd/Ctrl + ,` | Open settings              |

## Theming & Polish

- Support light/dark/system themes.
- Subtle animations for message arrival and status changes (respect reduced motion).
- Calm color palette focused on readability during long chats.
- Consistent spacing, typography scale, and iconography (use Lucide or Heroicons).

## Error & Disconnected States (Error Prevention + Recovery)

- Global disconnected banner with "Reconnect" button.
- Per-chat "Connection lost — messages will queue" notice.
- Failed sends show retry affordance.
- Invalid form inputs show inline errors with suggestions.

## Future Enhancements (Aligned with Spec)

- Multiple chat tabs or split view
- Message search / jump to date
- Rich media previews (when file transfer added)
- Theming engine shared with TUI where possible
- PWA support for "installable" feel

---

This web interface follows modern chat conventions while staying true to **IxDF principles** of clear feedback, user control, error prevention, and aesthetic minimalism. It complements the text TUI by offering a more visually rich but still focused experience for the same underlying Connection Service.