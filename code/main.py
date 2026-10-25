"""
Main Entry Point for Ghost Data Still Exists Solution.

This script executes the complete deletion-audit pipeline:
1. Loads dataset/deletion_requests.csv (518 requests).
2. Classifies requests (DELETION vs NOT_APPLICABLE).
3. Resolves identities (current and historical).
4. Audits evidence and system records.
5. Formats and writes output.csv at repository root.
"""

import os
import sys
import csv
import json

# Add code directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.identity import IdentityResolver
from core.classifier import RequestClassifier
from core.evidence_indexer import EvidenceIndexer
from core.auditor import Auditor, sort_steps


def main():
    dataset_dir = os.path.join(repo_root, "dataset")
    requests_path = os.path.join(dataset_dir, "deletion_requests.csv")
    output_path = os.path.join(repo_root, "output.csv")

    print("=== Ghost Data Still Exists: Starting Deletion Audit Pipeline ===")
    print(f"Reading requests from: {requests_path}")

    auditor = Auditor(dataset_dir)

    with open(requests_path, mode="r", encoding="utf-8") as f:
        requests = list(csv.DictReader(f))

    print(f"Total evaluation cases to process: {len(requests)}")

    results = []
    na_count = 0
    complete_count = 0
    incomplete_count = 0

    for req in requests:
        res = auditor.audit_case(req)
        status = res["deletion_status"]
        if status == "NOT_APPLICABLE":
            na_count += 1
        elif status == "COMPLETE":
            complete_count += 1
        else:
            incomplete_count += 1
        results.append(res)

    # Sort rows by case_id strictly as required
    results.sort(key=lambda r: r["case_id"])

    # Write root output.csv with exact header: case_id,deletion_status,steps_json
    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\nWrote {len(results)} rows to {output_path}")
    print(f"Summary:")
    print(f"  COMPLETE: {complete_count}")
    print(f"  INCOMPLETE: {incomplete_count}")
    print(f"  NOT_APPLICABLE: {na_count}")
    print("=== Execution finished successfully! ===")


if __name__ == "__main__":
    main()
