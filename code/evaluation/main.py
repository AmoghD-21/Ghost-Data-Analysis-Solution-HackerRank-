"""
Benchmark Evaluation Module for Ghost Data Still Exists.

This module evaluates predicted output against canonical answers (e.g. dataset/sample_output.csv).
Metrics evaluated:
1. Case-level Deletion Status Accuracy (COMPLETE / INCOMPLETE / NOT_APPLICABLE).
2. Step-level Count & Match Accuracy.
3. Field-level Accuracy across:
   - phase
   - system_id
   - resource_id
   - operation
   - state
   - evidence_id
4. Sequence & Canonical Ordering Accuracy.
"""

import json
import csv
import os
from typing import Dict, List, Any, Tuple


class BenchmarkEvaluator:
    """Computes evaluation accuracy against ground-truth sample outputs."""

    def __init__(self, ground_truth_csv_path: str):
        self.ground_truth_csv_path = ground_truth_csv_path
        self.ground_truth: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.ground_truth_csv_path):
            raise FileNotFoundError(f"Ground truth file missing: {self.ground_truth_csv_path}")

        with open(self.ground_truth_csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row["case_id"]
                status = row["deletion_status"]
                steps = json.loads(row["steps_json"])
                self.ground_truth[cid] = (status, steps)

    def evaluate_predictions(self, predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a list of prediction dictionaries:
        [{'case_id': '...', 'deletion_status': '...', 'steps_json': '...'}]
        """
        total_cases = len(predictions)
        status_matches = 0
        total_steps_truth = 0
        total_steps_pred = 0
        step_count_matches = 0

        field_matches = {
            "phase": 0,
            "system_id": 0,
            "resource_id": 0,
            "operation": 0,
            "state": 0,
            "evidence_id": 0
        }
        total_compared_steps = 0
        sequence_matches = 0

        for pred in predictions:
            cid = pred["case_id"]
            if cid not in self.ground_truth:
                continue

            truth_status, truth_steps = self.ground_truth[cid]
            pred_status = pred["deletion_status"]
            pred_steps = json.loads(pred["steps_json"]) if isinstance(pred["steps_json"], str) else pred["steps_json"]

            # 1. Status Match
            if pred_status == truth_status:
                status_matches += 1

            # 2. Step Count Match
            total_steps_truth += len(truth_steps)
            total_steps_pred += len(pred_steps)
            if len(pred_steps) == len(truth_steps):
                step_count_matches += 1

            # 3. Field & Sequence evaluation
            seq_ok = (len(pred_steps) == len(truth_steps))
            for i in range(min(len(pred_steps), len(truth_steps))):
                total_compared_steps += 1
                ps = pred_steps[i]
                ts = truth_steps[i]

                step_equal = True
                for field in field_matches.keys():
                    if ps.get(field) == ts.get(field):
                        field_matches[field] += 1
                    else:
                        step_equal = False

                if not step_equal:
                    seq_ok = False

            if seq_ok and len(truth_steps) > 0:
                sequence_matches += 1

        eval_cases_count = len([p for p in predictions if p["case_id"] in self.ground_truth])
        status_accuracy = (status_matches / eval_cases_count) if eval_cases_count else 0.0
        step_count_accuracy = (step_count_matches / eval_cases_count) if eval_cases_count else 0.0
        sequence_accuracy = (sequence_matches / eval_cases_count) if eval_cases_count else 0.0

        field_accuracies = {}
        for f, cnt in field_matches.items():
            field_accuracies[f] = (cnt / total_compared_steps) if total_compared_steps else 0.0

        return {
            "evaluated_cases": eval_cases_count,
            "status_matches": status_matches,
            "status_accuracy": status_accuracy,
            "step_count_accuracy": step_count_accuracy,
            "sequence_accuracy": sequence_accuracy,
            "field_accuracies": field_accuracies,
            "total_steps_ground_truth": total_steps_truth,
            "total_steps_predicted": total_steps_pred
        }


if __name__ == "__main__":
    import sys
    print("=== Testing BenchmarkEvaluator Directly ===")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sample_out_path = os.path.join(base_dir, "dataset", "sample_output.csv")

    evaluator = BenchmarkEvaluator(sample_out_path)
    print(f"Loaded {len(evaluator.ground_truth)} benchmark ground truth answers.")

    # Self-test: evaluating sample_output against itself must give 100% across all metrics
    with open(sample_out_path, mode="r", encoding="utf-8") as f:
        self_preds = list(csv.DictReader(f))

    metrics = evaluator.evaluate_predictions(self_preds)
    print("\nSelf-Evaluation Test Results:")
    print(f"  Status Accuracy: {metrics['status_accuracy'] * 100:.2f}%")
    print(f"  Step Count Accuracy: {metrics['step_count_accuracy'] * 100:.2f}%")
    print(f"  Sequence Accuracy: {metrics['sequence_accuracy'] * 100:.2f}%")
    print(f"  Field Accuracies: {metrics['field_accuracies']}")

    assert metrics['status_accuracy'] == 1.0
    assert metrics['sequence_accuracy'] == 1.0
    print("\nBenchmarkEvaluator verified and ready!")
