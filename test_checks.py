"""Regression checks for dependency gating, the cipher, envelopes and public/draft separation."""
import copy
import json
import os
import tempfile
import unittest
from checks import readiness, reachable, section
import kit


def record(rid, kind, **fields):
    return dict(dict(id=rid, type=kind, title=rid, status="decided", body="", path=rid + ".md"), **fields)


PLANETS = kit.load_cipher({"cipher": {"preset": "planets"}})[0]
COMPLETE = "\n".join(["## Hints", "1. Inspect the label.", "## Solution", "Read the corners.",
                      "## Playtest evidence", "2026-10-12: solved in 4 min."])


class Checks(unittest.TestCase):
    def test_missing_and_cyclic_inputs_never_open(self):
        p = record("PZ-001", "puzzle", props=["PP-001"])
        prop = record("PP-001", "prop", envelope="PZ-001")
        self.assertEqual(reachable([p, prop]), (set(), set()))
        self.assertEqual(reachable([p]), (set(), set()))

    def test_parallel_chains_converge(self):
        a = record("PZ-001", "puzzle")
        b = record("PZ-002", "puzzle")
        prop = record("PP-001", "prop", envelope="PZ-002")
        c = record("PZ-003", "puzzle", needs=["PZ-001", "PZ-002"], props=["PP-001"])
        self.assertEqual(reachable([c, prop, b, a]), ({"PZ-001", "PZ-002", "PZ-003"}, {"PP-001"}))

    def test_candidates_do_not_satisfy_decided_inputs(self):
        prop = record("PP-001", "prop", envelope="start")
        prop["status"] = "candidate"
        p = record("PZ-001", "puzzle", props=["PP-001"])
        self.assertTrue(any("Unreachable" in w["msg"] for w in readiness([p, prop])))
        self.assertFalse(any("Unreachable" in w["msg"] for w in readiness([p, prop], candidates=True)))

    def test_answer_and_physical_evidence(self):
        p = record("PZ-001", "puzzle", answer="0427", test_status="passed", test_method="physical", body=COMPLETE)
        self.assertEqual(readiness([p], release=True), [])
        p["test_method"] = "digital"
        self.assertTrue(any("physical" in w["msg"] for w in readiness([p], release=True)))
        p["answer"] = ""
        self.assertTrue(any("No answer" in w["msg"] for w in readiness([p])))
        p["body"] = "## Playtest evidence\n<!-- add a date later -->"
        self.assertTrue(any("dated" in w["msg"] for w in readiness([p], release=True)))

    def test_brief_placeholders_are_not_evidence(self):
        p = record("PZ-001", "puzzle")
        p["body"] = "## Player does\n[Read and decode; adapt to the story]\n## Playtest evidence\n<!-- No test recorded -->"
        self.assertEqual(section(p, "Player does"), "")
        self.assertEqual(section(p, "Playtest evidence"), "")

    def test_empty_game_does_not_pass(self):
        self.assertTrue(readiness([]))


class Cipher(unittest.TestCase):
    def test_encode_ignores_case_spaces_and_dashes(self):
        self.assertEqual(kit.encode("82-47", PLANETS), ["♅", "☿", "♁", "♄"])
        self.assertIsNone(kit.encode("82A7", PLANETS))
        self.assertIsNone(kit.encode("", PLANETS))

    def test_answer_problems(self):
        self.assertEqual(kit.answer_problems("8247", PLANETS), [])
        self.assertTrue(any("can't encode" in m for m in kit.answer_problems("82A7", PLANETS)))
        self.assertTrue(any("3 characters" in m for m in kit.answer_problems("732", PLANETS)))

    def test_custom_symbols_and_unknown_preset(self):
        c, problems = kit.load_cipher({"cipher": {"symbols": {"a": "X", "b": "Y"}, "length": 2}})
        self.assertEqual(kit.encode("ab", c), ["X", "Y"])
        self.assertEqual(c["length"], [2, 2])
        self.assertEqual(problems, [])
        self.assertTrue(kit.load_cipher({"cipher": {"preset": "nope"}})[1])
        self.assertTrue(kit.load_cipher({"cipher": {"symbols": {"1": "X", "2": "X"}}})[1])
        self.assertTrue(kit.load_cipher({})[1])  # no cipher: falls back to shapes, with a warning

    def test_decoys_are_stable_and_never_real(self):
        c = dict(PLANETS, decoys=5)
        real = [["♅", "☿", "♁", "♄"]]
        a, b = kit.decoy_codes(c, real, "Space"), kit.decoy_codes(c, real, "Space")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)
        self.assertNotIn(real[0], a)
        self.assertEqual(len({"".join(x) for x in a}), 5)

    def test_envelope_model_order_and_contents(self):
        first = record("PZ-002", "puzzle", answer="12345", props=["PP-001"])
        second = record("PZ-001", "puzzle", answer="8247", props=["PP-002"])
        recs = [second, first, record("PP-001", "prop", envelope="start"), record("PP-002", "prop", envelope="PZ-002"),
                record("PP-003", "prop", envelope="PZ-001", status="parked")]
        m = kit.envelope_model(recs, {"name": "T"}, PLANETS)
        self.assertEqual(m["start"], ["PP-001"])
        self.assertEqual([e["puzzle"] for e in m["envelopes"]], ["PZ-002", "PZ-001"])
        self.assertEqual(m["envelopes"][0]["contents"], ["PP-002"])
        self.assertEqual(m["envelopes"][1]["contents"], [])
        self.assertEqual("".join(m["envelopes"][1]["code"]), "♅☿♁♄")


class Project(unittest.TestCase):
    """A small adventure on disk, run through load(), build and the public pages."""
    def make(self, root, puzzles):
        with open(os.path.join(root, "backpack.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "Test", "cipher": {"preset": "planets"}}, f)
        for rid, fields in puzzles.items():
            folder = os.path.join(root, "records", "puzzles" if rid.startswith("PZ") else "props")
            os.makedirs(folder, exist_ok=True)
            lines = ["---", f"id: {rid}", f"title: {rid}", "status: decided"] + [f"{k}: {v}" for k, v in fields.items()] + ["---", COMPLETE]
            with open(os.path.join(folder, rid + ".md"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

    def test_duplicate_codes_and_legacy_fields_are_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self.make(root, {"PZ-001": {"answer": "1234"}, "PZ-002": {"answer": "12-34", "lock": "4-digit"},
                             "PP-001": {"found_in": "start"}})
            msgs = [w["msg"] for w in kit.load(root)["warnings"]]
            self.assertTrue(any("same envelope code" in m for m in msgs))
            self.assertTrue(any(m.startswith("lock is from the lock-based kit") for m in msgs))
            self.assertTrue(any(m.startswith("found_in is from the lock-based kit") for m in msgs))

    def test_build_writes_every_page(self):
        with tempfile.TemporaryDirectory() as root:
            self.make(root, {"PZ-001": {"answer": "8247", "props": "[PP-001]"}, "PP-001": {"envelope": "start"},
                             "PP-002": {"envelope": "PZ-001", "after_game": "keep"}})
            with open(os.path.join(root, "backpack.json"), "w", encoding="utf-8") as f:
                json.dump({"name": "Test", "cipher": {"preset": "planets"}, "publish_reset": True}, f)
            data = kit.cmd_build(root, quiet=True)
            self.assertEqual(data["warnings"], [])
            for page in ("index.html", "play.html", "print.html", "hints/index.html", "reset/index.html"):
                self.assertTrue(os.path.exists(os.path.join(root, "site", page)), page)
            reset = kit.reset_model(data)
            self.assertEqual(reset["steps"][0]["code"], "♅☿♁♄")
            self.assertEqual(reset["steps"][0]["keep"], ["PP-002"])
            self.assertEqual(reset["start"], ["PP-001"])


class Public(unittest.TestCase):
    def test_public_payload_excludes_drafts_and_private_notes(self):
        public = record("PZ-001", "puzzle", answer="0427", hint_title="Tag", publish_hints="yes")
        public["body"] = "## Hints\n1. Look at the tag.\n## Solution\nRead the corners.\n## Playtest evidence\nPRIVATE-NOTE"
        private = copy.deepcopy(public)
        private.update(id="PZ-002", answer="PRIVATE-ANSWER", publish_hints="no")
        candidate = copy.deepcopy(public)
        candidate.update(id="PZ-003", answer="CANDIDATE-ANSWER", status="candidate")
        replaced = copy.deepcopy(public)
        replaced.update(id="PZ-004", answer="SUPERSEDED-ANSWER", superseded_by="PZ-001")
        with tempfile.TemporaryDirectory() as site:
            kit.build_hints({"config": {"name": "Test", "cipher": {"preset": "planets"}}, "builtAt": "test",
                             "records": [public, private, candidate, replaced]}, site, os.path.join(kit.KIT, "viewer"))
            with open(os.path.join(site, "hints", "index.html"), encoding="utf-8") as f:
                html = f.read()
            self.assertIn('"answer": "0427"', html)
            self.assertIn('"code": "☉♁☿♄"', html)
            for secret in ("PRIVATE-NOTE", "PRIVATE-ANSWER", "CANDIDATE-ANSWER", "SUPERSEDED-ANSWER"):
                self.assertNotIn(secret, html)

    def test_incomplete_public_hint_is_left_off(self):
        p = record("PZ-001", "puzzle", publish_hints="yes", hint_title="INCOMPLETE-TAG")
        self.assertEqual(kit.hint_gaps(p), ["## Hints list", "## Solution", "answer"])
        with tempfile.TemporaryDirectory() as site:
            kit.build_hints({"config": {"name": "Test"}, "builtAt": "test", "records": [p]}, site, os.path.join(kit.KIT, "viewer"))
            with open(os.path.join(site, "hints", "index.html"), encoding="utf-8") as f:
                self.assertNotIn("INCOMPLETE-TAG", f.read())


if __name__ == "__main__":
    unittest.main()
