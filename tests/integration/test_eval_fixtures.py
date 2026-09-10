from pathlib import Path

import yaml  # type: ignore[import-untyped]

EVAL_CASES = Path(__file__).parents[2] / "eval" / "cases"


def test_all_eval_cases_have_consistent_metadata_and_fixtures() -> None:
    cases = sorted(EVAL_CASES.glob("*/case.yaml"))
    assert len(cases) == 5

    for case_path in cases:
        case = yaml.safe_load(case_path.read_text())
        case_dir = case_path.parent
        assert case["id"] == case_dir.name
        assert case["sender"]["id"]
        assert case["receiver"]["id"]
        assert (case_dir / case["sender"]["document"]).is_file()
        assert (case_dir / case["receiver"]["document"]).is_file()
        assert case["template_id"] == "newsletter"
        assert case["runs"] >= 1

        expected = yaml.safe_load((case_dir / "expected_facts.yaml").read_text())
        assert expected["sender_facts"]
        assert expected["receiver_facts"]
        assert expected["forbidden_claims"]
