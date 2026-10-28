"""Verify that every fact the answer key plants actually landed in the synthetic data. Prototype.

Reads data through `lead_brief.data_store`, the same loader the agent uses, and checks:
- record IDs are unique and every cross-reference (parent, account, contact, opp) exists;
- every ID the answer key names exists;
- each case's planted facts (data/answer_key/planted_facts.json) hold: usage trends,
  transcript lines, opportunities, contacts, MEDDPICC dates, lead notes;
- each case's relationship holds: required accounts are exactly the lead company's family,
  forbidden accounts are unrelated look-alikes or namesakes, net new leads match nothing,
  and each required flag's sources show what the flag claims;
- no generated text contains an em or en dash.

Usage: python scripts/check_data.py   (exit code 1 if anything fails)
"""

import json
import re
import sys
from collections import Counter
from datetime import date

from lead_brief import config, data_store

PLANTED_PATH = config.DATA_DIR / "answer_key" / "planted_facts.json"
LEVELS = {
    "net_new": "routine", "healthy_department": "heads_up", "at_risk_department": "caution",
    "closed_lost_history": "caution", "job_changer": "heads_up", "conflict": "caution",
}
NO_COMPANY = {"net_new", "job_changer"}  # the lead's company is not in the CRM


def trend(scorecard: dict) -> str | None:
    """'declining', 'healthy', or None for anything in between."""
    weeks = scorecard["weeks"]
    utils = [w["utilization_pct"] for w in weeks]
    if all(u >= 70 for u in utils) and all(w["health_band"] == "green" for w in weeks):
        return "healthy"
    first, last = sum(utils[:4]) / 4, sum(utils[-4:]) / 4
    drops = [a - b for a, b in zip(utils, utils[1:])]
    steep_late = sum(drops[-5:]) / 5 > sum(drops[:6]) / 6
    if first - last >= 15 and weeks[-1]["health_band"] == "red" and steep_late:
        return "declining"
    return None


def _domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


class Checker:
    def __init__(self):
        self.data = data_store._load()
        self.cases = json.loads(config.ANSWER_KEY_PATH.read_text(encoding="utf-8"))
        self.planted = {k: v for k, v in json.loads(PLANTED_PATH.read_text(encoding="utf-8")).items() if not k.startswith("_")}
        self.transcripts = {t["transcript_id"]: t for t in self.data["transcripts"]}
        self.source_ids = data_store.all_source_ids()
        self.problems: list[str] = []

    def fail(self, where: str, message: str) -> None:
        self.problems.append(f"{where}: {message}")

    # ---- Helpers ----

    def root(self, account_id: str) -> str:
        accounts = self.data["accounts"]
        while accounts[account_id]["parent_account_id"]:
            account_id = accounts[account_id]["parent_account_id"]
        return account_id

    def family(self, account_id: str) -> set[str]:
        r = self.root(account_id)
        return {a for a in self.data["accounts"] if self.root(a) == r}

    def lead_matches(self, lead: dict) -> set[str]:
        """Accounts that are the lead's company by email domain or exact name."""
        company = lead["company"].lower()
        return {
            a["account_id"] for a in self.data["accounts"].values()
            if a["domain"] == _domain(lead["email"]) or company in [n.lower() for n in [a["name"], *a["name_variants"]]]
        }

    def said(self, tid: str, speaker: str, text: str) -> bool:
        turns = self.transcripts[tid]["text"].split("\n\n")
        return any(t.startswith(f"{speaker}:") and text in t for t in turns)

    # ---- Whole-dataset checks ----

    def check_records(self) -> None:
        d = self.data
        dupes = [i for i, n in Counter(data_store.all_record_ids()).items() if n > 1]
        if dupes:
            self.fail("records", f"duplicate IDs {dupes}")
        for a in d["accounts"].values():
            if a["parent_account_id"] and a["parent_account_id"] not in d["accounts"]:
                self.fail(a["account_id"], f"unknown parent {a['parent_account_id']}")
            if a["is_customer"]:
                usage = d["usage"].get(a["account_id"])
                if usage is None:
                    self.fail(a["account_id"], "customer without a usage scorecard")
                elif len(usage["weeks"]) != 12 or usage["weeks"][-1]["week_ending"] != "2026-10-04":
                    self.fail(a["account_id"], "usage is not 12 weeks ending 2026-10-04")
                elif any(w["licensed_seats"] != a["licensed_seats"] for w in usage["weeks"]):
                    self.fail(a["account_id"], "usage seats differ from the CRM's licensed seats")
        for account_id in d["usage"]:
            if not d["accounts"].get(account_id, {}).get("is_customer"):
                self.fail(f"usage:{account_id}", "scorecard for a non-customer")
        for c in d["contacts"].values():
            if c["account_id"] not in d["accounts"]:
                self.fail(c["contact_id"], f"unknown account {c['account_id']}")
        for o in d["opps"].values():
            if o["account_id"] not in d["accounts"]:
                self.fail(o["opp_id"], f"unknown account {o['account_id']}")
            for field, value in o["meddpicc"].items():
                if "contact_id" in value and value["contact_id"] not in d["contacts"]:
                    self.fail(o["opp_id"], f"MEDDPICC {field} names unknown contact {value['contact_id']}")
        for t in d["transcripts"]:
            tid = t["transcript_id"]
            account = d["accounts"].get(t["account_id"])
            if account is None:
                self.fail(tid, f"unknown account {t['account_id']}")
                continue
            for cid in t["contact_ids"]:
                if d["contacts"].get(cid, {}).get("account_id") != t["account_id"]:
                    self.fail(tid, f"contact {cid} is not at {t['account_id']}")
            if account["account_owner"] and account["account_owner"] not in t["participants"]:
                self.fail(tid, f"account owner {account['account_owner']} is not a participant")
        for path in sorted(config.DATA_DIR.rglob("*")):
            if path.suffix in {".json", ".txt"} and re.search("[\u2013\u2014]", path.read_text(encoding="utf-8")):
                self.fail(str(path.relative_to(config.REPO_ROOT)), "contains an em or en dash")

    # ---- Planted facts ----

    def check_fact(self, where: str, f: dict) -> None:
        d = self.data
        kind = f["check"]
        if kind == "usage":
            usage = d["usage"].get(f["account_id"])
            got = trend(usage) if usage else "missing"
            if got != f["trend"]:
                self.fail(where, f"usage:{f['account_id']} should be {f['trend']}, is {got}")
        elif kind == "transcript":
            t = self.transcripts.get(f["transcript_id"])
            if t is None:
                self.fail(where, f"{f['transcript_id']} missing")
            elif t["account_id"] != f["account_id"]:
                self.fail(where, f"{f['transcript_id']} is on {t['account_id']}, not {f['account_id']}")
            elif not self.said(f["transcript_id"], f["speaker"], f["says"]):
                self.fail(where, f"{f['transcript_id']}: {f['speaker']} never says {f['says']!r}")
        elif kind == "opp":
            o = d["opps"].get(f["opp_id"])
            if o is None:
                self.fail(where, f"{f['opp_id']} missing")
                return
            for key in ("account_id", "type", "status", "owner", "closed_lost_reason"):
                if key in f and o[key] != f[key]:
                    self.fail(where, f"{f['opp_id']} {key} is {o[key]!r}, expected {f[key]!r}")
            if f["status"] == "closed_lost" and not o["closed_lost_reason"]:
                self.fail(where, f"{f['opp_id']} is closed lost with no reason")
        elif kind == "contact":
            c = d["contacts"].get(f["contact_id"])
            if c is None:
                self.fail(where, f"{f['contact_id']} missing")
                return
            if (c["account_id"], c["name"]) != (f["account_id"], f["name"]):
                self.fail(where, f"{f['contact_id']} is {c['name']} at {c['account_id']}")
            if "last_updated_before" in f and not c["last_updated"] < f["last_updated_before"]:
                self.fail(where, f"{f['contact_id']} updated {c['last_updated']}, not before {f['last_updated_before']}")
            if "last_updated_after" in f and not c["last_updated"] > f["last_updated_after"]:
                self.fail(where, f"{f['contact_id']} updated {c['last_updated']}, not after {f['last_updated_after']}")
        elif kind == "meddpicc":
            champion = d["opps"].get(f["opp_id"], {}).get("meddpicc", {}).get("champion", {})
            if (champion.get("contact_id"), champion.get("last_updated")) != (f["champion"], f["last_updated"]):
                self.fail(where, f"{f['opp_id']} MEDDPICC champion is {champion}")
        elif kind == "lead_note":
            if f["says"] not in d["leads"][f["lead_id"]]["form_note"]:
                self.fail(where, f"form note lacks {f['says']!r}")
        else:
            self.fail(where, f"unknown check {kind!r}")

    # ---- Each case's relationship ----

    def check_flag_sources(self, where: str, case: dict, lead: dict, family: set[str]) -> None:
        d = self.data
        planted_tids = {f["transcript_id"] for f in self.planted.get(case["case_id"], []) if f["check"] == "transcript"}
        for flag in case["required_flags"]:
            kind = flag["type"]
            for source in flag["any_source"]:
                if source not in self.source_ids:
                    self.fail(where, f"{kind} source {source} does not exist")
                    continue
                prefix, _, ident = source.partition(":")
                ident = ident.split("/")[-1]
                if prefix == "usage":
                    want = "declining" if kind == "renewal_risk" else "healthy"
                    if trend(d["usage"][ident]) != want:
                        self.fail(where, f"{kind} cites {source}, which is not {want}")
                elif source.startswith("crm:opp/"):
                    o = d["opps"][ident]
                    ok = {
                        "renewal_risk": o["type"] == "renewal" and o["status"] == "open",
                        "closed_lost_history": o["status"] == "closed_lost",
                        "open_opp_conflict": o["status"] == "open" and o["owner"] and o["account_id"] in family,
                    }.get(kind, True)
                    if not ok:
                        self.fail(where, f"{kind} cites {source}, which does not show it")
                elif source.startswith("crm:contact/"):
                    c = d["contacts"][ident]
                    account = d["accounts"][c["account_id"]]
                    if kind == "job_changer":
                        same_surname = c["name"].split()[-1] == lead["name"].split()[-1]
                        if not (same_surname and account["is_customer"] and _domain(c["email"]) != _domain(lead["email"])):
                            self.fail(where, f"{source} is not the lead's earlier record at another customer")
                    elif kind == "stale_contact":
                        age = (date.fromisoformat(config.AS_OF_DATE) - date.fromisoformat(c["last_updated"])).days
                        if c["name"] != lead["name"] or age < 365 or c["title"] == lead["title"] or c["account_id"] not in family:
                            self.fail(where, f"{source} is not a stale record of the lead in their own company")
                elif prefix == "transcript":
                    if kind in ("champion_change", "closed_lost_history", "job_changer") and ident not in planted_tids:
                        self.fail(where, f"{kind} cites {source}, which plants nothing for this case")

    def check_case(self, case: dict) -> None:
        cid = case["case_id"]
        d = self.data
        lead = d["leads"].get(case["lead_id"])
        if lead is None:
            self.fail(cid, f"lead {case['lead_id']} missing")
            return
        status = case["relationship_status"]
        if LEVELS[status] != case["alert_level"]:
            self.fail(cid, f"{status} should be {LEVELS[status]}, not {case['alert_level']}")
        if cid not in self.planted:
            self.fail(cid, "no entry in planted_facts.json")
        for fact in self.planted.get(cid, []):
            self.check_fact(cid, fact)

        required, forbidden = set(case["related_account_ids_required"]), set(case["related_account_ids_forbidden"])
        for account_id in required | forbidden:
            if account_id not in d["accounts"]:
                self.fail(cid, f"account {account_id} does not exist")
                return
        matches = self.lead_matches(lead)
        family: set[str] = set()
        if status in NO_COMPANY:
            if required or matches:
                self.fail(cid, f"lead's company should not be in the CRM; matches {sorted(matches)}")
        else:
            family = self.family(next(iter(required))) if required else set()
            if not matches or not matches <= family:
                self.fail(cid, f"lead matches {sorted(matches)}, outside the required family")
            if required != family:
                self.fail(cid, f"required {sorted(required)} is not the whole family {sorted(family)}")
        for account_id in forbidden:
            account = d["accounts"][account_id]
            if account_id in family or account["domain"] == _domain(lead["email"]):
                self.fail(cid, f"forbidden {account_id} is related to the lead")
            shares_word = lead["company"].split()[0].lower() in account["name"].lower()
            namesake = any(c["name"] == lead["name"] and c["account_id"] == account_id for c in d["contacts"].values())
            if not (shares_word or namesake):
                self.fail(cid, f"forbidden {account_id} is neither a look-alike nor a namesake's company")
        if status == "net_new":
            for c in d["contacts"].values():
                if c["email"] == lead["email"]:
                    self.fail(cid, f"net new lead's email is on {c['contact_id']}")
                if c["name"] == lead["name"] and not any(
                    f["check"] == "contact" and f["contact_id"] == c["contact_id"] and "last_updated_after" in f
                    for f in self.planted.get(cid, [])
                ):
                    self.fail(cid, f"{c['contact_id']} shares the lead's name without a planted namesake check")
        self.check_flag_sources(cid, case, lead, family)

    def run(self) -> list[str]:
        self.check_records()
        ids = [c["case_id"] for c in self.cases]
        if len(ids) != len(set(ids)):
            self.fail("answer key", "duplicate case IDs")
        for case in self.cases:
            self.check_case(case)
        return self.problems


def main() -> int:
    checker = Checker()
    problems = checker.run()
    counts = Counter(c["relationship_status"] for c in checker.cases)
    print(f"{len(checker.cases)} cases: " + ", ".join(f"{n} {s}" for s, n in counts.items()))
    print(f"{len(checker.data['accounts'])} accounts, {len(checker.data['contacts'])} contacts, "
          f"{len(checker.data['opps'])} opps, {len(checker.data['leads'])} leads, "
          f"{len(checker.data['usage'])} scorecards, {len(checker.data['transcripts'])} transcripts")
    for p in problems:
        print(f"FAIL {p}")
    print("All planted facts landed." if not problems else f"{len(problems)} problems.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
