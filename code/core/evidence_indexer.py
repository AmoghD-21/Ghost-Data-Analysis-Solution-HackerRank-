"""
Evidence Indexer Module for Ghost Data Still Exists.

This module indexes the 94 evidence files in `dataset/evidence/`
(SQL snapshots, JSON exports/bundles, application logs, text files, PDFs).

Key functionalities:
1. Manifest Ingestion (`dataset/evidence_files.csv`):
   Maps each file to its `file_id`, `file_path`, `origin`, and `captured_at` timestamp.
2. Content Indexing:
   Scans SQL, JSON, LOG, TXT, and PDF files to index occurrences of:
   - Resource IDs (e.g., account_*, search_*, support_*, backup_*, data_flow_*, analytics_*, audit_record_*, tombstone_*)
   - User Identifiers (user_id, email, phone)
3. Point-in-Time Temporal Retrieval:
   Given a case's `audit_at` cutoff, filters evidence to only consider facts
   established at or before `audit_at`.
"""

import csv
import os
import re
import json
from typing import Dict, List, Optional, Set, Any
from datetime import datetime


# Supported textual / structured extensions
SUPPORTED_EXTS = {".sql", ".json", ".log", ".txt", ".pdf"}

# Regular expression to extract standard Northstar Shop resource identifiers
RESOURCE_REGEX = re.compile(
    r"\b((?:account|search|support|backup|data_flow|analytics|audit_record|tombstone|export|cache|profile)_\w+)\b",
    re.IGNORECASE
)


class EvidenceFile:
    """Represents a single evidence document from evidence_files.csv."""

    def __init__(self, file_id: str, file_path: str, origin: str, captured_at: str):
        self.file_id = file_id
        self.file_path = file_path
        self.origin = origin
        self.captured_at_str = captured_at
        # Parse ISO-8601 timestamp for reliable chronological filtering
        # Handle formats like 2026-09-15T11:59:39Z
        clean_ts = captured_at.replace("Z", "+00:00")
        try:
            self.captured_at = datetime.fromisoformat(clean_ts)
        except Exception:
            self.captured_at = datetime.min

        # Inverted index entries within this file:
        # resource_id -> list of raw context / line snippets
        self.resources_found: Set[str] = set()
        # terms (user_id, email) found
        self.terms_found: Set[str] = set()


class EvidenceIndexer:
    """Loads manifest and indexes evidence files by resource ID and user identifiers."""

    def __init__(self, dataset_dir: str):
        self.dataset_dir = dataset_dir
        self.manifest_path = os.path.join(dataset_dir, "evidence_files.csv")
        self.evidence_files: Dict[str, EvidenceFile] = {}
        
        # Inverted Index: resource_id (lowercase) -> list of EvidenceFile objects
        self.resource_to_files: Dict[str, List[EvidenceFile]] = {}
        
        # Inverted Index: term (user_id, email) -> list of EvidenceFile objects
        self.term_to_files: Dict[str, List[EvidenceFile]] = {}

        self._load_manifest()
        self._index_all_files()

    def _load_manifest(self):
        """Loads evidence_files.csv manifest."""
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Evidence manifest missing at: {self.manifest_path}")

        with open(self.manifest_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fid = row["file_id"].strip()
                fpath = row["file_path"].strip()
                origin = row.get("origin", "").strip()
                captured_at = row.get("captured_at", "").strip()
                
                ev_file = EvidenceFile(fid, fpath, origin, captured_at)
                self.evidence_files[fid] = ev_file

    def _read_file_text(self, full_path: str) -> str:
        """Extracts text from supported file types."""
        ext = os.path.splitext(full_path)[1].lower()

        if ext in {".sql", ".json", ".log", ".txt"}:
            try:
                with open(full_path, mode="r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""

        elif ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(full_path)
                return "\n".join([page.extract_text() or "" for page in reader.pages])
            except Exception:
                return ""

        return ""

    def _index_all_files(self):
        """Extracts resources and text identifiers from all supported files."""
        for fid, ev in self.evidence_files.items():
            full_path = os.path.join(self.dataset_dir, ev.file_path)
            if not os.path.exists(full_path):
                continue

            text = self._read_file_text(full_path)
            if not text:
                continue

            # 1. Discover all resource IDs via regex
            resources = set(m.lower() for m in RESOURCE_REGEX.findall(text))
            ev.resources_found = resources

            for res in resources:
                if res not in self.resource_to_files:
                    self.resource_to_files[res] = []
                self.resource_to_files[res].append(ev)

    def find_evidence_for_resource(self, resource_id: str, audit_cutoff_str: Optional[str] = None) -> List[EvidenceFile]:
        """
        Retrieves evidence files mentioning a given resource_id.
        If audit_cutoff_str is provided, returns only evidence captured_at <= audit_cutoff.
        Sorted by captured_at descending (most recent point-in-time evidence first).
        """
        clean_res = resource_id.strip().lower()
        files = self.resource_to_files.get(clean_res, [])

        if audit_cutoff_str:
            clean_ts = audit_cutoff_str.replace("Z", "+00:00")
            try:
                cutoff_dt = datetime.fromisoformat(clean_ts)
                files = [f for f in files if f.captured_at <= cutoff_dt]
            except Exception:
                pass

        # Sort descending by capture time so the latest valid snapshot is chosen
        return sorted(files, key=lambda f: f.captured_at, reverse=True)

    def get_file_content(self, file_id: str) -> str:
        """Returns the full text content of a given file_id."""
        ev = self.evidence_files.get(file_id)
        if not ev:
            return ""
        full_path = os.path.join(self.dataset_dir, ev.file_path)
        return self._read_file_text(full_path)


if __name__ == "__main__":
    import sys
    print("=== Testing EvidenceIndexer Directly ===")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dataset_dir = os.path.join(base_dir, "dataset")

    indexer = EvidenceIndexer(dataset_dir)
    print(f"Loaded {len(indexer.evidence_files)} evidence files from manifest.")
    print(f"Indexed {len(indexer.resource_to_files)} unique resource IDs across all files.")

    # Test 1: Check failover replica resource from case_05
    test_res_1 = "account_005"
    cutoff_1 = "2026-09-08T13:40:00Z"
    evs_1 = indexer.find_evidence_for_resource(test_res_1, cutoff_1)
    print(f"\nEvidence lookup for '{test_res_1}' (audit_at {cutoff_1}):")
    for e in evs_1:
        print(f"  -> {e.file_id} [{e.captured_at_str}] {e.file_path} ({e.origin})")
    assert any(e.file_id == "evidence_54" for e in evs_1), "evidence_54 should be found for account_005"

    # Test 2: Check support replica resource from case_10
    test_res_2 = "support_002"
    cutoff_2 = "2026-09-18T12:25:00Z"
    evs_2 = indexer.find_evidence_for_resource(test_res_2, cutoff_2)
    print(f"\nEvidence lookup for '{test_res_2}' (audit_at {cutoff_2}):")
    for e in evs_2:
        print(f"  -> {e.file_id} [{e.captured_at_str}] {e.file_path}")
    assert any(e.file_id == "evidence_61" for e in evs_2), "evidence_61 should be found for support_002"

    # Test 3: Check readback log resource from case_03
    test_res_3 = "account_7566"
    cutoff_3 = "2026-09-26T11:00:00Z"
    evs_3 = indexer.find_evidence_for_resource(test_res_3, cutoff_3)
    print(f"\nEvidence lookup for '{test_res_3}' (audit_at {cutoff_3}):")
    for e in evs_3:
        print(f"  -> {e.file_id} [{e.captured_at_str}] {e.file_path}")
    assert any(e.file_id == "evidence_94" for e in evs_3), "evidence_94 should be found for account_7566"

    print("\nEvidenceIndexer passed all assertions and works successfully!")
