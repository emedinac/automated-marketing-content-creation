"""Minimal live-API evaluation runner.

The fact check is a lightweight lexical screen. It is useful for triage, not
a replacement for human review or a grounded LLM judge.
"""

import argparse
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

import httpx
import yaml  # type: ignore[import-untyped]

from marketing_collateral.adapters.pdf import PdfPlumberContextExtractor
from marketing_collateral.settings import Settings

ROOT = Path(__file__).parent
STOPWORDS = set(
    "a an and as at by for in of on or the to with provides describes "
    "discusses supports".split()
)


def words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOPWORDS and len(word) > 2
    }


def fact_score(text: str, facts: list[dict[str, str]]) -> int:
    text_words = words(text)
    hits = sum(len(words(item["fact"]) & text_words) >= 2 for item in facts)
    return 2 if hits == len(facts) else 1 if hits else 0


def claim_safety(text: str, forbidden: list[str]) -> int:
    lowered = text.lower()
    return 0 if any(claim.lower() in lowered for claim in forbidden) else 2


def unsupported_numbers(text: str, source_text: str) -> list[str]:
    """Find generated numeric claims absent from the extracted source PDFs."""
    normalized_source = re.sub(r"(\d+)\s*percent", r"\1%", source_text.lower())
    normalized_source = re.sub(r"(\d+)\s*%", r"\1%", normalized_source)
    return sorted(
        {
            number
            for number in re.findall(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])", text)
            if number.lower() not in normalized_source
        }
    )


def evaluate_result(
    result: dict[str, Any],
    case: dict[str, Any],
    expected: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    text = " ".join(section["text"] for section in result["sections"])
    technical = (
        result.get("template_id") == case["template_id"]
        and bool(result.get("sections"))
        and result.get("review_required") is True
        and all(
            section["word_count"] <= section["word_limit"]
            for section in result["sections"]
        )
    )
    sender = fact_score(text, expected["sender_facts"])
    receiver = fact_score(text, expected["receiver_facts"])
    names = {case["sender"]["id"], case["receiver"]["id"]}
    has_names = all(name.lower() in text.lower() for name in names)
    qualified = bool(re.search(r"\b(could|potentially|may|might)\b", text.lower()))
    connection = 2 if has_names and qualified else 1 if has_names else 0
    safety = claim_safety(text, expected["forbidden_claims"])
    unsupported = unsupported_numbers(text, source_text)
    if unsupported:
        safety = 0
    constraints = 2 if technical else 0
    score = sender + receiver + connection + safety + constraints
    return {
        "score": score,
        "technical": technical,
        "sender_grounding": sender,
        "receiver_grounding": receiver,
        "connection": connection,
        "claim_safety": safety,
        "unsupported_numbers": unsupported,
        "quality_constraints": constraints,
        "human_review_required": result.get("review_required") is True,
        "result": result,
    }


def run_case(
    client: httpx.Client,
    case_dir: Path,
    case: dict[str, Any],
    expected: dict[str, Any],
    runs: int,
) -> list[dict[str, Any]]:
    outputs = []
    extractor = PdfPlumberContextExtractor()
    source_text = "\n".join(
        extractor.extract((case_dir / case[role]["document"]).read_bytes()).text
        for role in ("sender", "receiver")
    )
    for _ in range(runs):
        for role in ("sender", "receiver"):
            document = case[role]["document"]
            response = client.post(
                "/upload",
                data={
                    "sender_id": case["sender"]["id"],
                    "receiver_id": case["receiver"]["id"],
                    "role": role,
                },
                files={
                    "files": (
                        document,
                        (case_dir / document).read_bytes(),
                        "application/pdf",
                    )
                },
            )
            response.raise_for_status()
        response = client.post(
            "/generate",
            json={
                "sender_id": case["sender"]["id"],
                "receiver_id": case["receiver"]["id"],
                "prompt": case["prompt"],
                "template_id": case["template_id"],
            },
        )
        response.raise_for_status()
        outputs.append(
            evaluate_result(response.json()["result"], case, expected, source_text)
        )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=0, help="Override case run counts")
    parser.add_argument("--case", help="Evaluate one case directory name")
    parser.add_argument("--reports", default=str(ROOT / "reports"))
    args = parser.parse_args()
    if args.runs < 0:
        parser.error("--runs must be non-negative")

    case_paths = sorted(ROOT.joinpath("cases").glob("*/case.yaml"))
    if args.case:
        case_paths = [path for path in case_paths if path.parent.name == args.case]
    settings = Settings()
    report: dict[str, Any] = {
        "base_url": args.base_url,
        "model": settings.gemini_model,
        "prompt_version": settings.prompt_version,
        "cases": [],
    }
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120) as client:
        for case_path in case_paths:
            case_dir = case_path.parent
            case = yaml.safe_load(case_path.read_text())
            expected = yaml.safe_load((case_dir / "expected_facts.yaml").read_text())
            runs = args.runs or case["runs"]
            results = run_case(client, case_dir, case, expected, runs)
            report["cases"].append(
                {
                    "id": case["id"],
                    "runs": results,
                    "mean_score": mean(item["score"] for item in results),
                    "pass": all(
                        item["technical"]
                        and item["claim_safety"] == 2
                        and not item["unsupported_numbers"]
                        and item["score"] >= 8
                        for item in results
                    ),
                }
            )

    reports = Path(args.reports)
    reports.mkdir(parents=True, exist_ok=True)
    output = reports / "latest.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    for case in report["cases"]:
        status = "PASS" if case["pass"] else "FAIL"
        print(f"{case['id']}: {case['mean_score']:.2f}/10 {status}")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
