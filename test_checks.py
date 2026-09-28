"""Regression checks for dependency gating and public/draft separation."""
import copy
import json
import os
import tempfile
import unittest
from checks import readiness, reachable, flow_model, section
import kit


def record(rid, kind, **fields):
    return dict(id=rid, type=kind, title=rid, status="decided", body="", path=rid + ".md", **fields)


class Checks(unittest.TestCase):
    def test_missing_and_cyclic_inputs_never_open(self):
        p = record("PZ-001", "puzzle", props=["PP-001"])
        prop = record("PP-001", "prop", found_in="PZ-001")
        self.assertEqual(reachable([p, prop]), (set(), set()))
        self.assertEqual(reachable([p]), (set(), set()))
        model = flow_model([p, prop])
        self.assertTrue(all(n["blocked"] for n in model["nodes"] if n["id"] != "start"))

    def test_parallel_chains_converge(self):
        a = record("PZ-001", "puzzle")
        b = record("PZ-002", "puzzle")
        prop = record("PP-001", "prop", found_in="PZ-002")
        c = record("PZ-003", "puzzle", needs=["PZ-001", "PZ-002"], props=["PP-001"])
        self.assertEqual(reachable([c, prop, b, a]), ({"PZ-001", "PZ-002", "PZ-003"}, {"PP-001"}))

    def test_candidates_do_not_satisfy_decided_inputs(self):
        prop = record("PP-001", "prop", found_in="start")
        prop["status"] = "candidate"
        p = record("PZ-001", "puzzle", props=["PP-001"])
        self.assertTrue(any("Unreachable" in w["msg"] for w in readiness([p, prop])))
        self.assertFalse(any("Unreachable" in w["msg"] for w in readiness([p, prop], candidates=True)))

    def test_lock_format_and_physical_evidence(self):
        p = record("PZ-001", "puzzle", lock="4-digit", answer="0427", test_status="passed", test_method="physical")
        p["body"] = "\n".join("## " + s + "\nDocumented evidence." for s in (
            "Player notices", "Player does", "Player obtains", "Story reason", "Hints", "Solution", "Playtest evidence"))
        p["body"] = p["body"].replace("## Hints\nDocumented evidence.", "## Hints\n1. Inspect the label.")
        self.assertEqual(readiness([p], release=True), [])
        p["test_method"] = "digital"
        self.assertTrue(any("physical" in w["msg"] for w in readiness([p], release=True)))
        p["answer"] = "427"
        self.assertTrue(any("fit" in w["msg"] for w in readiness([p])))
        p["body"] = "## Playtest evidence\n<!-- add a date later -->"
        self.assertTrue(any("dated" in w["msg"] for w in readiness([p], release=True)))

    def test_public_payload_excludes_drafts_and_private_notes(self):
        public = record("PZ-001", "puzzle", lock="4-digit", answer="0427", hint_title="Tag", publish_hints="yes")
        public["body"] = "## Hints\n1. Look at the tag.\n## Solution\nRead the corners.\n## Playtest evidence\nPRIVATE-NOTE"
        private = copy.deepcopy(public)
        private.update(id="PZ-002", answer="PRIVATE-ANSWER", publish_hints="no")
        candidate = copy.deepcopy(public)
        candidate.update(id="PZ-003", answer="CANDIDATE-ANSWER", status="candidate")
        replaced = copy.deepcopy(public)
        replaced.update(id="PZ-004", answer="SUPERSEDED-ANSWER", superseded_by="PZ-001")
        with tempfile.TemporaryDirectory() as site:
            kit.build_hints({"config": {"name": "Test"}, "builtAt": "test", "records": [public,private,candidate,replaced]}, site, os.path.join(kit.KIT,"viewer"))
            with open(os.path.join(site,"hints","index.html"),encoding="utf-8") as f:
                html = f.read()
            self.assertIn('"answer": "0427"',html)
            for secret in ("PRIVATE-NOTE","PRIVATE-ANSWER","CANDIDATE-ANSWER","SUPERSEDED-ANSWER"):
                self.assertNotIn(secret,html)

    def test_incomplete_public_hint_is_left_off(self):
        p = record("PZ-001", "puzzle", publish_hints="yes", lock="4-digit", hint_title="INCOMPLETE-TAG")
        self.assertEqual(kit.hint_gaps(p), ["## Hints list", "## Solution", "answer"])
        with tempfile.TemporaryDirectory() as site:
            kit.build_hints({"config":{"name":"Test"},"builtAt":"test","records":[p]},site,os.path.join(kit.KIT,"viewer"))
            with open(os.path.join(site,"hints","index.html"),encoding="utf-8") as f:
                self.assertNotIn("INCOMPLETE-TAG", f.read())

    def test_empty_game_does_not_pass(self):
        self.assertTrue(readiness([]))

    def test_brief_placeholders_are_not_evidence(self):
        p = record("PZ-001", "puzzle")
        p["body"] = "## Player does\n[Read and decode; adapt to the story]\n## Playtest evidence\n<!-- No test recorded -->\n<!-- Prop-record follow-up -->"
        self.assertEqual(section(p, "Player does"), "")
        self.assertEqual(section(p, "Playtest evidence"), "")


if __name__ == "__main__":
    unittest.main()
