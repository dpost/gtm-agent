"""Scorers. Today: correctness, as code. Groundedness and actionability judges come later."""

from dataclasses import dataclass

from lead_brief.schema import Brief


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    expected: str = ""  # short, human-readable; shown side by side in the HTML report
    got: str = ""


def _ids(ids) -> str:
    return ", ".join(sorted(ids)) or "none"


def correctness(brief: Brief, case: dict, known_source_ids: set[str]) -> list[Check]:
    """The six correctness checks for one case. The case passes only if every check passes."""
    checks = []

    expected = case["relationship_status"]
    checks.append(Check(
        "relationship_status",
        brief.relationship_status == expected,
        f"expected {expected}, got {brief.relationship_status}",
        expected,
        brief.relationship_status,
    ))

    expected = case["alert_level"]
    checks.append(Check(
        "alert_level",
        brief.alert_level == expected,
        f"expected {expected}, got {brief.alert_level}",
        expected,
        brief.alert_level,
    ))

    related = set(brief.related_account_ids)
    missing = sorted(set(case["related_account_ids_required"]) - related)
    forbidden = sorted(set(case["related_account_ids_forbidden"]) & related)
    checks.append(Check(
        "related_accounts",
        not missing and not forbidden,
        f"got {sorted(related)}; missing {missing}; forbidden present {forbidden}",
        f"{_ids(case['related_account_ids_required'])}; not {_ids(case['related_account_ids_forbidden'])}",
        _ids(related),
    ))

    problems = []
    for required in case["required_flags"]:
        flags = [f for f in brief.flags if f.type == required["type"]]
        if not flags:
            problems.append(f"{required['type']} missing")
        elif not any(set(f.source_ids) & set(required["any_source"]) for f in flags):
            cited = sorted({s for f in flags for s in f.source_ids})
            problems.append(f"{required['type']} cites {cited}, needs one of {required['any_source']}")
    checks.append(Check(
        "required_flags",
        not problems,
        "; ".join(problems) or f"found {[r['type'] for r in case['required_flags']]} with expected sources",
        "; ".join(f"{r['type']} citing {' or '.join(r['any_source'])}" for r in case["required_flags"]) or "none",
        "; ".join(f"{f.type} citing {', '.join(f.source_ids)}" for f in brief.flags) or "no flags",
    ))

    bad_types = sorted({f.type for f in brief.flags} & set(case["forbidden_flag_types"]))
    checks.append(Check(
        "forbidden_flags",
        not bad_types,
        f"forbidden types present: {bad_types}" if bad_types else f"none of {case['forbidden_flag_types']}",
        f"none of {_ids(case['forbidden_flag_types'])}",
        _ids(bad_types) if bad_types else "none present",
    ))

    cited = {s for f in brief.flags for s in f.source_ids}
    unknown = sorted(cited - known_source_ids)
    checks.append(Check(
        "source_ids_exist",
        not unknown,
        f"unknown IDs: {unknown}" if unknown else f"all {len(cited)} cited IDs exist",
        "every cited ID exists in the data",
        f"unknown: {_ids(unknown)}" if unknown else f"all {len(cited)} exist",
    ))

    return checks
