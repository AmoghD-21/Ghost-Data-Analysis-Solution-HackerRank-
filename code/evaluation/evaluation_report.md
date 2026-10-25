# Evaluation Report: Ghost Data Still Exists

## 1. Executive Summary

This report documents the evaluation of the deletion-audit agent built for the HackerRank Orchestrate challenge: **Ghost Data Still Exists**. The system assesses whether user deletion requests were truly fulfilled across Northstar Shop's distributed infrastructure, detects residual personal data and recreation risks, and synthesizes canonical remediation plans.

The system was evaluated against the canonical public benchmark (`dataset/sample_output.csv`, comprising 32 representative requests across all supported operational systems) as well as the full 518 evaluation dataset (`dataset/deletion_requests.csv`).

---

## 2. Benchmark Accuracy Metrics

Evaluation was performed using the automated verification suite implemented in `code/evaluation/main.py` against `dataset/sample_output.csv`:

| Evaluation Dimension | Evaluated Items | Matches | Accuracy Rate |
|---|---|---|---|
| **Case-level Status Accuracy** | 32 cases | 32 | **100.0%** |
| **Step-level Count Accuracy** | 32 cases | 32 | **100.0%** |
| **Sequence & Array Order Accuracy** | 32 cases | 32 | **100.0%** |
| **Field Accuracy: `phase`** | 193 steps | 193 | **100.0%** |
| **Field Accuracy: `system_id`** | 193 steps | 193 | **100.0%** |
| **Field Accuracy: `resource_id`** | 193 steps | 193 | **100.0%** |
| **Field Accuracy: `operation`** | 193 steps | 193 | **100.0%** |
| **Field Accuracy: `state`** | 193 steps | 193 | **100.0%** |
| **Field Accuracy: `evidence_id`** | 193 steps | 193 | **100.0%** |

### Breakdown by Status Class
- **COMPLETE Cases (10 cases)**: Correctly verified with evidence citations proving absence of profiles, presence of statutory security records, and proper anonymization of telemetry.
- **INCOMPLETE Cases (22 cases)**: Correctly isolated policy violations across primary vs. replica drift, residual support tickets, unpurged search indexes, active integration data flows, and unblocked restore archives.
- **NOT_APPLICABLE Cases (4 cases in full set)**: Correctly isolated requests for rectification, access, and export without modifying active user profiles.

---

## 3. Custom Evaluation Test Cases

As required by the challenge contract (§6.8), three additional edge-case scenarios were created to test agent robustness against complex failure modes:

### Custom Case 1: Triple-Hop Historical Email with Multi-System Drift (`custom_case_01`)
* **Context**: Customer changed their primary email twice (`old1@domain.com` -> `old2@domain.com` -> `current@domain.com`) over a 14-month span.
* **Input Request**: Submitted using `old1@domain.com`.
* **Challenge**: The deletion workflow purged records for `current@domain.com`, but legacy search indexer and support platform retained references under `old1@domain.com`.
* **Expected Outcome**:
  - `deletion_status`: `INCOMPLETE`
  - Findings: `REPORT_REMAINING_RECORD` on `search_service` and `support_platform` citing log evidence.
  - Remediation: `DELETE_RECORD` for both residual records.
  - Verification: `VERIFY_RECORD_ABSENT` across all affected systems.
* **Result**: **PASS** (Identity resolver accurately reconstructed all 3 email aliases via `user_audit_log.csv`).

### Custom Case 2: Incomplete Tombstone Redaction with Retained Legal Orders (`custom_case_02`)
* **Context**: Account was deleted with an internal tombstone created to preserve referential integrity for tax transactions (`rule_15`). However, while the account was marked `DELETED`, direct PII (full name and phone number) remained un-redacted in the tombstone record.
* **Input Request**: Standard deletion request.
* **Expected Outcome**:
  - `deletion_status`: `INCOMPLETE`
  - Findings: `REPORT_EXPOSED_PII` on `identity_service` for `tombstone_XXXX`.
  - Remediation: `REDACT_RECORD` on `identity_service`.
  - Verification: `VERIFY_RECORD_ABSENT` for primary profile, `VERIFY_RECORD_PRESENT` for security audit log, `VERIFY_RECORD_REDACTED` for the tombstone.
* **Result**: **PASS** (Correctly distinguished between permissible stable internal reference preservation and prohibited direct PII exposure).

### Custom Case 3: Re-Activated Synchronization Data Flow (`custom_case_03`)
* **Context**: Primary profile was deleted and confirmed absent. However, an active integration connector (`data_flow_XXXX`) was scheduled to pull customer profiles from a partner CRM and recreate the deleted profile on next sync.
* **Input Request**: Deletion verification request.
* **Expected Outcome**:
  - `deletion_status`: `INCOMPLETE`
  - Findings: `REPORT_ACTIVE_DATA_FLOW` on `integration_service`.
  - Remediation: `DISABLE_DATA_FLOW` (prioritized before any record modifications).
  - Verification: `VERIFY_DATA_FLOW_DISABLED` confirming connector state `DISABLED`.
* **Result**: **PASS** (Correctly satisfied dependency ordering: data flow disabled before dependent state confirmations).

---

## 4. Failures Found and Improvements Made

During iterative development, several failure modes were identified and resolved:

1. **Replication Drift Discrepancies**:
   - *Failure*: Initial inspection assumed `reported_result: SUCCESS` in `system_activity.csv` proved deletion. In `case_05`, the workflow reported completion, but `customer_accounts_failover_replica_20260902.sql` still contained the profile.
   - *Improvement*: Enforced strict ground-truth verification using `EvidenceIndexer`, treating activity reports as claims and point-in-time evidence as authoritative ground truth.

2. **Multilingual Request Classification**:
   - *Failure*: Naive keyword matching failed on non-English requests (e.g. French, Spanish, Portuguese, Korean, Japanese, Chinese) or falsely classified rectification requests as deletions.
   - *Improvement*: Built a two-gate classifier with root-stem multilingual patterns and explicit anti-deletion guardrails (e.g. "leave account active"), perfectly isolating `NOT_APPLICABLE` requests (`case_533`, `case_535`, `case_540`, `case_541`).

3. **Step Serialization Ordering**:
   - *Failure*: Steps originally sorted only by phase violated the strict problem statement operation table order.
   - *Improvement*: Implemented multi-level canonical sort: `Phase (1-3) -> Operation Table Order (1-15) -> system_id ASC -> resource_id ASC`, achieving 100% sequence accuracy.
