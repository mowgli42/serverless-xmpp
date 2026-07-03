"""Local address book management."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from xmpp_p2p_chat.common.addressbook_hash import (
    compute_content_hash,
    hash_block_colors,
    hash_hex,
)
from xmpp_p2p_chat.common.models import AddressBookStatus, Contact

logger = logging.getLogger(__name__)

META_FILENAME = ".addressbook-meta.json"


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
        self._version: int = 0
        self._content_hash: str = ""
        self._modified_at: datetime | None = None
        self._loaded_at: datetime | None = None
        self._bundled_source: str | None = None
        self._fragment_files: list[str] = []

    @property
    def contacts(self) -> list[Contact]:
        return sorted(self._contacts.values(), key=lambda c: c.name.lower())

    @property
    def content_hash(self) -> str:
        return self._content_hash

    @property
    def version(self) -> int:
        return self._version

    def process_startup(self, bundled_path: Path | None = None, import_if_empty: bool = True) -> None:
        """Load address book from disk; optionally seed from a bundled distribution file."""
        self.load()
        if import_if_empty and not self._contacts and bundled_path and bundled_path.exists():
            self._import_bundled(bundled_path)
            self.load()
        self._save_meta()
        logger.info(
            "Address book ready: v%d · %d contacts · %s",
            self._version,
            len(self._contacts),
            self._content_hash[:24] + "…",
        )

    def _import_bundled(self, bundled_path: Path) -> None:
        try:
            raw = json.loads(bundled_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self.warnings.append(f"Bundled address book unreadable: {exc}")
            logger.error("Failed to read bundled address book %s: %s", bundled_path, exc)
            return
        if not isinstance(raw, list):
            self.warnings.append("Bundled address book must be a JSON array")
            return
        self.primary_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self.primary_path, raw)
        self._bundled_source = str(bundled_path)
        logger.info("Imported bundled address book from %s", bundled_path)

    def load(self) -> None:
        self._contacts.clear()
        self.warnings.clear()
        self._fragment_files.clear()
        self._loaded_at = datetime.now(UTC)

        had_primary = self.primary_path.exists()
        if had_primary:
            self._load_file(self.primary_path, source="primary")
            if self.primary_path.exists():
                self._modified_at = datetime.fromtimestamp(
                    self.primary_path.stat().st_mtime, tz=UTC
                )
        else:
            self.primary_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self.primary_path, [])
            logger.info("Created empty address book at %s", self.primary_path)

        if self.fragments_dir.exists():
            for fragment in sorted(self.fragments_dir.glob("*.json")):
                self._fragment_files.append(fragment.name)
                self._load_file(fragment, source=fragment.name)

        self._recompute_hash()
        self._load_meta()
        self._check_p2p_fingerprints()
        logger.info("Loaded %d contacts (%d warnings)", len(self._contacts), len(self.warnings))

    def reload(self) -> None:
        """Re-read address book files from disk (e.g. after external edit)."""
        self.load()
        self._save_meta()
        self._notify()

    def status(self) -> AddressBookStatus:
        return AddressBookStatus(
            version=self._version,
            content_hash=self._content_hash,
            contact_count=len(self._contacts),
            primary_path=str(self.primary_path),
            fragments_dir=str(self.fragments_dir),
            fragment_files=list(self._fragment_files),
            loaded_at=self._loaded_at or datetime.now(UTC),
            modified_at=self._modified_at,
            warnings=list(self.warnings),
            hash_blocks=hash_block_colors(self._content_hash),
            bundled_source=self._bundled_source,
        )

    def _meta_path(self) -> Path:
        return self.primary_path.parent / META_FILENAME

    def _load_meta(self) -> None:
        path = self._meta_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._version = int(data.get("version", 0))
            stored_hash = data.get("content_hash", "")
            if stored_hash and stored_hash != self._content_hash:
                self._version += 1
                logger.info("Address book hash changed since last run (v%d)", self._version)
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    def _save_meta(self) -> None:
        path = self._meta_path()
        payload = {
            "version": self._version,
            "content_hash": self._content_hash,
            "contact_count": len(self._contacts),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _recompute_hash(self) -> None:
        payload = [c.model_dump(mode="json") for c in self.contacts]
        self._content_hash = compute_content_hash(payload)

    def _check_p2p_fingerprints(self) -> None:
        for contact in self._contacts.values():
            uses_p2p = contact.preferred_transport == "direct-p2p" or contact.direct is not None
            if not uses_p2p or not contact.direct:
                continue
            fp = (contact.direct.public_key_fingerprint or "").strip()
            if not fp:
                self.warnings.append(
                    f"Contact '{contact.name}' ({contact.id}) is direct-p2p but missing "
                    "public_key_fingerprint — set it after exchanging certs (see docs/p2p-serverless.md)"
                )
            elif fp.upper().startswith("REPLACE"):
                self.warnings.append(
                    f"Contact '{contact.name}' ({contact.id}) still has a placeholder fingerprint"
                )

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
        self._modified_at = datetime.now(UTC)
        self._recompute_hash()
        self._version += 1
        self._save_meta()

    def _atomic_write(self, path: Path, payload: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)

    def _notify(self) -> None:
        if self.on_updated:
            self.on_updated()

    def verify_hash(self, expected: str) -> bool:
        return hash_hex(self._content_hash) == hash_hex(expected)
