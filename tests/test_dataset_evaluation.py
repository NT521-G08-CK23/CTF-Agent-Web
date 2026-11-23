from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from dataset_evaluation.catalog import (
    ChallengeCatalog,
    ChallengeNotFoundError,
    ManifestValidationError,
    parse_public_manifest,
)
from dataset_evaluation.exports import (
    export_aggregate_json,
    export_records_csv,
    export_records_json,
)
from dataset_evaluation.metrics import aggregate_records
from dataset_evaluation.results import normalize_baseline_log
from dataset_evaluation.runtime import ChallengeRuntimeAdapter, OwnedResourceRegistry
from dataset_evaluation.verification import verify_flag_exact


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dataset" / "manifests" / "nyu-ctf-bench-v20250206-pilots.public.json"
EXPECTED_IDS = {
    "2015q-rev-wyvern",
    "2016q-cry-sleeping_guard",
    "2016q-pwn-warmup",
}


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_pinned_public_manifest_has_exactly_the_three_pilots(self) -> None:
        identity, challenges = parse_public_manifest(self.payload)
        self.assertEqual(identity.source_tag, "v20250206")
        self.assertEqual(identity.source_commit, "1dc13a0dc41a71504f727649679e2b5a6d0cb1b1")
        self.assertEqual(identity.development_challenge_count, 57)
        self.assertEqual({challenge.id for challenge in challenges}, EXPECTED_IDS)

    def test_manifest_schema_rejects_private_fields(self) -> None:
        altered = json.loads(json.dumps(self.payload))
        altered["challenges"][0]["flag"] = "synthetic-test-only"
        with self.assertRaises(ManifestValidationError):
            parse_public_manifest(altered)

    def test_catalog_is_allow_listed_and_handles_missing_id(self) -> None:
        catalog = ChallengeCatalog.from_file(MANIFEST)
        public_entry = catalog.get("2016q-pwn-warmup").as_dict()
        self.assertEqual(set(public_entry), {"id", "name", "category", "description", "agent_files"})
        self.assertTrue(catalog.is_agent_file_allowed("2016q-pwn-warmup", "warmup.c"))
        self.assertFalse(catalog.is_agent_file_allowed("2016q-pwn-warmup", "compose.yaml"))
        with self.assertRaises(ChallengeNotFoundError):
            catalog.get("not-a-pilot")


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ChallengeCatalog.from_file(MANIFEST)

    def test_unavailable_runtime_does_not_start_a_challenge(self) -> None:
        adapter = ChallengeRuntimeAdapter(self.catalog)
        result = adapter.prepare("2016q-cry-sleeping_guard", run_id="synthetic-run")
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.error_code, "runtime_unavailable")
        self.assertEqual(adapter.status("synthetic-run").state, "unavailable")
        self.assertEqual(adapter.cleanup("synthetic-run").state, "cleaned")

    def test_cleanup_registry_lists_only_module_owned_resources_for_one_run(self) -> None:
        registry = OwnedResourceRegistry()
        registry.register("run-one", "ctf-eval-run-one-network")
        registry.register("run-two", "ctf-eval-run-two-container")
        self.assertEqual(
            [resource.resource_id for resource in registry.cleanup_candidates("run-one")],
            ["ctf-eval-run-one-network"],
        )
        with self.assertRaises(ValueError):
            registry.register("run-one", "unrelated-container")
        registry.mark_cleaned("run-one")
        self.assertEqual(registry.cleanup_candidates("run-one"), ())


class VerificationAndResultsTests(unittest.TestCase):
    def test_exact_trusted_checker_accepts_only_identical_synthetic_value(self) -> None:
        expected = "SYNTHETIC_EXPECTED_VALUE_NOT_A_REAL_FLAG"
        self.assertTrue(verify_flag_exact(expected, expected).matched)
        self.assertFalse(verify_flag_exact(expected + " ", expected).matched)
        self.assertFalse(verify_flag_exact("", "").matched)
        self.assertFalse(verify_flag_exact(None, expected).matched)

    def test_agent_solved_claim_is_not_success_without_trusted_verification(self) -> None:
        record = normalize_baseline_log(
            {"solved": True, "rounds": 2, "cost": 0.03},
            run_id="synthetic-unverified",
            challenge_id="2015q-rev-wyvern",
            dataset_version="v20250206",
        )
        self.assertEqual(record.status, "unverified")
        self.assertIsNone(record.success)

    def test_malformed_log_is_safe_and_error_is_redacted(self) -> None:
        record = normalize_baseline_log(
            {
                "rounds": "not-a-number",
                "runtime": {"tools": "unknown"},
                "error": "timeout while handling FLAG{SYNTHETIC_TEST_ONLY}; api_key=demo-secret",
            },
            run_id="synthetic-malformed",
            challenge_id="2016q-cry-sleeping_guard",
            dataset_version="v20250206",
            category="crypto",
        )
        self.assertEqual(record.status, "error")
        self.assertEqual(record.failure_type, "timeout")
        self.assertIsNone(record.rounds)
        self.assertIsNone(record.tool_calls)
        self.assertNotIn("SYNTHETIC_TEST_ONLY", record.error_message or "")
        self.assertNotIn("demo-secret", record.error_message or "")

    def test_metrics_exclude_unverified_claims_from_success_rate(self) -> None:
        verified_success = normalize_baseline_log(
            {"duration_seconds": 4, "rounds": 1, "tool_calls": 2},
            run_id="synthetic-success",
            challenge_id="2016q-pwn-warmup",
            dataset_version="v20250206",
            category="pwn",
            flag_verified=True,
        )
        verified_failure = normalize_baseline_log(
            {},
            run_id="synthetic-failure",
            challenge_id="2016q-pwn-warmup",
            dataset_version="v20250206",
            category="pwn",
            flag_verified=False,
        )
        unverified = normalize_baseline_log(
            {"solved": True},
            run_id="synthetic-claim",
            challenge_id="2016q-pwn-warmup",
            dataset_version="v20250206",
            category="pwn",
        )
        summary = aggregate_records([verified_success, verified_failure, unverified])
        overall = summary["overall"]
        self.assertEqual(overall["runs"], 3)
        self.assertEqual(overall["verified_runs"], 2)
        self.assertEqual(overall["unverified_runs"], 1)
        self.assertEqual(overall["success_rate"], 0.5)
        self.assertEqual(overall["failure_types"], {"wrong_flag": 1})

    def test_json_csv_and_aggregate_exports_have_expected_schema(self) -> None:
        record = normalize_baseline_log(
            {"usage": {"input_tokens": 10, "output_tokens": 5}},
            run_id="synthetic-export",
            challenge_id="2015q-rev-wyvern",
            dataset_version="v20250206",
            flag_verified=True,
        )
        aggregate = aggregate_records([record])
        # Keep short-lived export fixtures in project-local ignored storage.
        with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as temporary_directory:
            output = Path(temporary_directory)
            json_path = output / "records.json"
            csv_path = output / "records.csv"
            aggregate_path = output / "aggregate.json"
            export_records_json(json_path, [record])
            export_records_csv(csv_path, [record])
            export_aggregate_json(aggregate_path, aggregate)
            stored_records = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(set(stored_records[0]), set(record.as_dict()))
            with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
                self.assertEqual(set(csv.DictReader(csv_file).fieldnames or ()), set(record.as_dict()))
            self.assertIn("overall", json.loads(aggregate_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
