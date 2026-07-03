"""Signed address book updates over XMPP (urn:serverless-xmpp:addressbook:1)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from slixmpp.stanza import Iq
from slixmpp.xmlstream import ElementBase, register_stanza_plugin

from xmpp_p2p_chat.common.config import AddressBookSyncConfig
from xmpp_p2p_chat.common.models import AddressBookSyncPending, AddressBookSyncStatus, Contact
from xmpp_p2p_chat.connection_service.addressbook import AddressBookError, AddressBookManager
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager

logger = logging.getLogger(__name__)

SYNC_NAMESPACE = "urn:serverless-xmpp:addressbook:1"


class AddressBookUpdate(ElementBase):
    name = "update"
    namespace = SYNC_NAMESPACE
    plugin_attrib = "addressbook_update"
    interfaces = set()
    sub_interfaces = {"payload"}


register_stanza_plugin(Iq, AddressBookUpdate)


SendIqFn = Callable[[str, dict], Awaitable[None]]
PushFn = Callable[[str, dict], None]


class AddressBookSyncService:
    def __init__(
        self,
        addressbook: AddressBookManager,
        persistence: PersistenceManager,
        config: AddressBookSyncConfig,
        on_push: PushFn,
    ) -> None:
        self.addressbook = addressbook
        self.persistence = persistence
        self.config = config
        self.on_push = on_push
        self._send_iq: SendIqFn | None = None

    def set_send_iq(self, sender: SendIqFn) -> None:
        self._send_iq = sender

    def configure(self, *, enabled: bool | None = None, auto_apply: bool | None = None) -> None:
        if enabled is not None:
            self.config.enabled = enabled
        if auto_apply is not None:
            self.config.auto_apply = auto_apply

    async def status(self) -> AddressBookSyncStatus:
        pending = 0
        try:
            pending = len(await self.persistence.list_sync_pending())
        except RuntimeError:
            pass
        return AddressBookSyncStatus(
            enabled=self.config.enabled,
            auto_apply=self.config.auto_apply,
            pending_count=pending,
            secret_configured=bool(self.config.secret),
        )

    def _require_secret(self) -> bytes:
        if not self.config.secret:
            raise ValueError("Address book sync secret not configured")
        return self.config.secret.encode("utf-8")

    def sign_payload(self, payload: dict[str, Any]) -> str:
        body = {k: v for k, v in payload.items() if k != "signature"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = hmac.new(self._require_secret(), canonical.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(digest).decode("ascii")

    def verify_payload(self, payload: dict[str, Any]) -> bool:
        if not self.config.secret:
            return False
        signature = payload.get("signature")
        if not signature:
            return False
        expected = self.sign_payload(payload)
        return hmac.compare_digest(expected, signature)

    def build_update_payload(
        self,
        *,
        action: str,
        contact: Contact | None = None,
        contact_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": action,
            "version": self.addressbook.version,
            "content_hash": self.addressbook.content_hash,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if contact is not None:
            payload["contact"] = contact.model_dump(mode="json")
            payload["contact_id"] = contact.id
        elif contact_id:
            payload["contact_id"] = contact_id
        payload["signature"] = self.sign_payload(payload)
        return payload

    async def handle_inbound_iq(self, iq: Iq) -> None:
        if not self.config.enabled:
            return
        update = iq["addressbook_update"]
        if not update or not update["payload"]:
            return
        from_jid = str(iq["from"].bare).lower()
        trusted = any(c.jid.lower() == from_jid for c in self.addressbook.contacts)
        if not trusted:
            logger.warning("Rejected address book sync from untrusted JID: %s", from_jid)
            return

        try:
            raw = base64.b64decode(update["payload"])
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as exc:
            logger.warning("Invalid sync payload from %s: %s", from_jid, exc)
            return

        if not self.verify_payload(payload):
            logger.warning("Invalid sync signature from %s", from_jid)
            return

        if not self._timestamp_valid(payload.get("timestamp", "")):
            logger.warning("Stale sync update from %s", from_jid)
            return

        if self.config.auto_apply:
            await self._apply_payload(from_jid, payload)
            return

        pending_id = str(uuid4())
        await self.persistence.save_sync_pending(
            pending_id,
            from_jid=from_jid,
            action=str(payload.get("action", "")),
            contact_id=str(payload.get("contact_id", "")),
            payload=payload,
        )
        self.on_push(
            "addressbook.sync_pending",
            {"id": pending_id, "from_jid": from_jid, "action": payload.get("action")},
        )

    def _timestamp_valid(self, ts: str) -> bool:
        try:
            when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            delta = abs((datetime.now(UTC) - when).total_seconds())
            return delta <= self.config.max_timestamp_skew_seconds
        except ValueError:
            return False

    async def _apply_payload(self, from_jid: str, payload: dict[str, Any]) -> None:
        action = payload.get("action")
        contact_id = payload.get("contact_id")
        try:
            if action == "add" and payload.get("contact"):
                contact = Contact.model_validate(payload["contact"])
                if self.addressbook.get(contact.id):
                    self.addressbook.update(contact.id, contact.model_dump(mode="json"))
                else:
                    self.addressbook.add(contact)
            elif action == "update" and payload.get("contact"):
                contact = Contact.model_validate(payload["contact"])
                self.addressbook.update(contact.id, contact.model_dump(mode="json"))
            elif action == "remove" and contact_id:
                if self.addressbook.get(contact_id):
                    self.addressbook.remove(contact_id)
            else:
                logger.warning("Unsupported sync action %s from %s", action, from_jid)
        except (AddressBookError, ValueError) as exc:
            logger.warning("Failed to apply sync from %s: %s", from_jid, exc)

    async def apply_pending(self, pending_id: str) -> bool:
        row = await self.persistence.get_sync_pending(pending_id)
        if not row:
            return False
        await self._apply_payload(row.from_jid, row.payload)
        await self.persistence.delete_sync_pending(pending_id)
        return True

    async def reject_pending(self, pending_id: str) -> bool:
        row = await self.persistence.get_sync_pending(pending_id)
        if not row:
            return False
        await self.persistence.delete_sync_pending(pending_id)
        return True

    async def get_pending_updates(self) -> list[AddressBookSyncPending]:
        return await self.persistence.list_sync_pending()

    async def sync_now(self, contact_ids: list[str] | None = None) -> dict[str, Any]:
        if not self.config.enabled:
            raise ValueError("Address book sync is disabled")
        if not self._send_iq:
            raise RuntimeError("XMPP transport not available for sync")
        targets = [
            c
            for c in self.addressbook.contacts
            if c.preferred_transport == "xmpp-server" or c.xmpp_server
        ]
        if contact_ids:
            allowed = set(contact_ids)
            targets = [c for c in targets if c.id in allowed]
        sent = 0
        payload = self.build_update_payload(
            action="update",
            contact=None,
            contact_id="__book_meta__",
        )
        payload["action"] = "announce"
        payload["signature"] = self.sign_payload(payload)
        for contact in targets:
            await self._send_iq(contact.jid, payload)
            sent += 1
        return {"sent": sent, "version": self.addressbook.version}

    async def broadcast_mutation(
        self, *, action: str, contact: Contact | None = None, contact_id: str | None = None
    ) -> None:
        if not self.config.enabled or not self._send_iq:
            return
        payload = self.build_update_payload(action=action, contact=contact, contact_id=contact_id)
        for peer in self.addressbook.contacts:
            if peer.jid == (contact.jid if contact else ""):
                continue
            if peer.preferred_transport != "xmpp-server" and not peer.xmpp_server:
                continue
            try:
                await self._send_iq(peer.jid, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sync push to %s failed: %s", peer.jid, exc)
