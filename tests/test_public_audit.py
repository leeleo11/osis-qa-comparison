from __future__ import annotations

from scripts.audit_public_boundary import audit_paths, scan_text


def test_path_audit_blocks_dataset_and_results() -> None:
    findings = audit_paths(
        [
            "README.md",
            "datasets/qa/questions.json",
            "runs/formal/results.jsonl",
            "private/gold.json",
        ]
    )
    assert {finding["path"] for finding in findings} == {
        "datasets/qa/questions.json",
        "runs/formal/results.jsonl",
        "private/gold.json",
    }


def test_text_audit_blocks_literal_secrets_but_allows_env_references() -> None:
    assert not scan_text("config.json", '"apiKey": "{env:OSIS_MODEL_API_KEY}"')
    findings = scan_text("leak.txt", "OSIS_MODEL_API_KEY=" + "sk-" + "live-secret-value")
    assert findings and findings[0]["kind"] == "credential"
