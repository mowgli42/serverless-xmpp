"""Local address book management."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from xmpp_p2p_chat.common.models import Contact

logger = logging.getLogger(__name__)


class AddressBookError(Exception):
    pass


class AddressBookManager:
    def __init__(
        self,
        primary_path: Path,
        fragments_dir: Path | None = None,
        on_updated: Callable[[], None] | None = None,
    ) -> None:
        self.primary_path = primary_path
        self.fragments_dir = fragments_dir or primary_path.parent / "addressbooks.d"
        self.on_updated = on_updated
        self._contacts: dict[str, Contact] = {}
        self.warnings: list[str] = []

    @property
    def contacts(self) -> list[Contact]:
        return sorted(self._contacts.values(), key=lambda c: c.name.lower())

    def load(self) -> None:
        self._contacts.clear()
        self.warnings.clear()

        if self.primary_path.exists():
            self._load_file(self.primary_path, source="primary")
        else:
            self.primary_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self.primary_path, [])
            logger.info("Created empty address book at %s", self.primary_path)

        if self.fragments_dir.exists():
            for fragment in sorted(self.fragments_dir.glob("*.json")):
                self._load_file(fragment, source=fragment.name)

        logger.info("Loaded %d contacts (%d warnings)", len(self._contacts), len(self.warnings))

    def _load_file(self, path: Path, source: str) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            bad_path = path.with_suffix(path.suffix + ".bad")
            shutil.move(str(path), str(bad_path))
            msg = f"Malformed JSON in {source}; quarantined to {bad_path.name}: {exc}"
            self.warnings.append(msg)
            logger.error(msg)
            return

        if not isinstance(raw, list):
            self.warnings.append(f"{source}: expected JSON array, got {type(raw).__name__}")
            return

        for idx, entry in enumerate(raw):
            try:
                contact = Contact.model_validate(entry)
                if contact.id in self._contacts:
                    msg = f"Duplicate contact id '{contact.id}' in {source}; skipping"
                    self.warnings.append(msg)
                    logger.warning(msg)
                    continue
                self._contacts[contact.id] = contact
            except Exception as exc:  # noqa: BLE001 - collect all bad entries
                msg = f"{source}[{idx}]: invalid contact: {exc}"
                self.warnings.append(msg)
                logger.warning(msg)

    def list(self) -> list[Contact]:
        return self.contacts

    def get(self, contact_id: str) -> Contact | None:
        return self._contacts.get(contact_id)

    def add(self, contact: Contact) -> Contact:
        if contact.id in self._contacts:
            raise AddressBookError(f"Contact id already exists: {contact.id}")
        now = datetime.now(UTC)
        contact.created_at = now
        contact.updated_at = now
        self._contacts[contact.id] = contact
        self._persist()
        self._notify()
        return contact

    def update(self, contact_id: str, partial: dict) -> Contact:
        existing = self._contacts.get(contact_id)
        if not existing:
            raise AddressBookError(f"Contact not found: {contact_id}")
        data = existing.model_dump()
        data.update(partial)
        data["id"] = contact_id
        data["updated_at"] = datetime.now(UTC)
        updated = Contact.model_validate(data)
        self._contacts[contact_id] = updated
        self._persist()
        self._notify()
        return updated

    def remove(self, contact_id: str) -> None:
        if contact_id not in self._contacts:
            raise AddressBookError(f"Contact not found: {contact_id}")
        del self._contacts[contact_id]
        self._persist()
        self._notify()

    def _persist(self) -> None:
        payload = [c.model_dump(mode="json") for c in self.contacts]
        self._atomic_write(self.primary_path, payload)

    def _atomic_write(self, path: Path, payload: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)

    def _notify(self) -> None:
        if self.on_updated:
            self.on_updated()
