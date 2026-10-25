"""
Identity Resolution Engine for Ghost Data Still Exists.

This module loads current user identities (dataset/user_identities.csv) and
historical identity audit records (dataset/user_audit_log.csv).
It reconstructs the full set of current and historical identifiers for any user,
allowing incoming deletion requests (whether referencing current or old email)
to be matched to the correct stable user_id and all historical identifiers.
"""

import csv
import os
from typing import Dict, List, Optional, Set, Any


class UserIdentity:
    """Stores all current and historical attributes of an identity."""

    def __init__(self, user_id: str, name: str, current_email: str, current_phone: str, current_hash: str):
        self.user_id = user_id
        self.name = name
        self.current_email = current_email
        self.current_phone = current_phone
        self.current_hash = current_hash

        # Sets containing all current + historical variations
        self.emails: Set[str] = set()
        self.phones: Set[str] = set()
        self.email_hashes: Set[str] = set()

        if current_email:
            self.emails.add(current_email.strip().lower())
        if current_phone:
            self.phones.add(current_phone.strip())
        if current_hash:
            self.email_hashes.add(current_hash.strip().lower())

        # Audit events tracking history
        self.history_records: List[Dict[str, str]] = []

    def add_audit_record(self, record: Dict[str, str]):
        """Adds a historical change record and records prior attribute values."""
        self.history_records.append(record)
        field = record.get("field_name", "").strip()
        old_val = record.get("old_value", "").strip()
        new_val = record.get("new_value", "").strip()

        if field == "email":
            if old_val:
                self.emails.add(old_val.lower())
            if new_val:
                self.emails.add(new_val.lower())
        elif field == "phone":
            if old_val:
                self.phones.add(old_val)
            if new_val:
                self.phones.add(new_val)
        elif field == "email_hash":
            if old_val:
                self.email_hashes.add(old_val.lower())
            if new_val:
                self.email_hashes.add(new_val.lower())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "current_email": self.current_email,
            "current_phone": self.current_phone,
            "current_hash": self.current_hash,
            "all_emails": sorted(list(self.emails)),
            "all_phones": sorted(list(self.phones)),
            "all_email_hashes": sorted(list(self.email_hashes)),
            "history_count": len(self.history_records),
        }


class IdentityResolver:
    """Manages identity resolution across current snapshot and historical audit logs."""

    def __init__(self, identities_csv_path: str, audit_log_csv_path: str):
        self.identities_csv_path = identities_csv_path
        self.audit_log_csv_path = audit_log_csv_path

        # Primary user storage: user_id -> UserIdentity
        self.users_by_id: Dict[str, UserIdentity] = {}

        # Lookup indexes: email (current or historical) -> user_id
        self.email_to_user_id: Dict[str, str] = {}
        # phone (current or historical) -> user_id
        self.phone_to_user_id: Dict[str, str] = {}
        # email_hash (current or historical) -> user_id
        self.hash_to_user_id: Dict[str, str] = {}

        self._load()

    def _load(self):
        """Loads and indexes user identities and audit log entries."""
        if not os.path.exists(self.identities_csv_path):
            raise FileNotFoundError(f"Identities CSV not found at: {self.identities_csv_path}")

        # 1. Load current identities
        with open(self.identities_csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"].strip()
                name = row.get("name", "").strip()
                email = row.get("email", "").strip()
                phone = row.get("phone", "").strip()
                email_hash = row.get("email_hash", "").strip()

                user = UserIdentity(
                    user_id=uid,
                    name=name,
                    current_email=email,
                    current_phone=phone,
                    current_hash=email_hash
                )
                self.users_by_id[uid] = user

        # 2. Load historical audit logs and attach to users
        if os.path.exists(self.audit_log_csv_path):
            with open(self.audit_log_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = row["user_id"].strip()
                    if uid in self.users_by_id:
                        self.users_by_id[uid].add_audit_record(row)

        # 3. Build fast bidirectional indexes
        for uid, user in self.users_by_id.items():
            for em in user.emails:
                self.email_to_user_id[em] = uid
            for ph in user.phones:
                self.phone_to_user_id[ph] = uid
            for h in user.email_hashes:
                self.hash_to_user_id[h] = uid

    def resolve_by_email(self, email: str) -> Optional[UserIdentity]:
        """Resolves an email (current or historical) to its UserIdentity."""
        if not email:
            return None
        cleaned_email = email.strip().lower()
        uid = self.email_to_user_id.get(cleaned_email)
        if uid:
            return self.users_by_id.get(uid)
        return None

    def get_by_user_id(self, user_id: str) -> Optional[UserIdentity]:
        """Gets UserIdentity by stable user_id."""
        return self.users_by_id.get(user_id)


if __name__ == "__main__":
    import sys
    print("=== Testing IdentityResolver Directly ===")

    # Determine default paths relative to repo root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    identities_csv = os.path.join(base_dir, "dataset", "user_identities.csv")
    audit_log_csv = os.path.join(base_dir, "dataset", "user_audit_log.csv")

    resolver = IdentityResolver(identities_csv, audit_log_csv)
    print(f"Loaded {len(resolver.users_by_id)} users into memory.")
    print(f"Indexed {len(resolver.email_to_user_id)} total unique email addresses.\n")

    # Example 1: Look up a user with current email (case_01)
    sample_email_1 = "amina.elmasri@gmail.com"
    user_1 = resolver.resolve_by_email(sample_email_1)
    if user_1:
        print(f"Lookup for '{sample_email_1}':")
        print(f"  User ID: {user_1.user_id}")
        print(f"  Name: {user_1.name}")
        print(f"  Current Email: {user_1.current_email}")
        print(f"  All Emails on file: {user_1.emails}")
        print(f"  All Phone numbers: {user_1.phones}\n")

    # Example 2: Look up a user using an OLD / HISTORICAL email (case_10)
    sample_email_2 = "nadia.ionescu@yahoo.com"
    user_2 = resolver.resolve_by_email(sample_email_2)
    if user_2:
        print(f"Lookup for HISTORICAL email '{sample_email_2}':")
        print(f"  Resolved User ID: {user_2.user_id}")
        print(f"  Name: {user_2.name}")
        print(f"  Current Active Email: {user_2.current_email}")
        print(f"  All Historical & Current Emails: {user_2.emails}")
        print(f"  History record count: {len(user_2.history_records)}\n")

    print("IdentityResolver works successfully when run directly!")
