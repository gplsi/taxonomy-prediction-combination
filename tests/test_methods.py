import json
from itertools import permutations
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from taxensemble.rules import combine, transitive_filter
from taxensemble.report import reports


def candidates(order):
    return [(p, "h", -i) for i, p in enumerate(order)]


class Rules(unittest.TestCase):
    def test_consensus_examples(self):
        cases = [("ABC", "AD", "A", "A", "A"), ("ABC", "BAD", "", "AB", "AB"),
                 ("ABC", "DAC", "", "A", "A"), ("AB", "CD", "", "", ""),
                 ("AB", "", "", "", "A")]
        for a, b, agree, backed, rescue in cases:
            out, _ = combine(candidates(a), candidates(b))
            for method, expected in (("union", set(a+b)), ("intersection", set(a)&set(b)),
                                     ("top_agreement", agree), ("supported_top", backed),
                                     ("rescue", rescue)):
                self.assertEqual(set(out[method]), {(p,"h") for p in expected})

    def test_rank_and_score_rules(self):
        a = [("C","h",2), ("B","h",3), ("A","h",3)]
        b = [("D","h",7), ("B","h",6), ("A","h",2), ("C","h",1)]
        out, audit = combine(a,b)
        self.assertEqual(out["pareto"], [("A","h"),("B","h")])
        for method, p in (("top_a","A"), ("top_b","D"), ("top_intersection","B"),
                          ("reciprocal_rank","A")):
            self.assertEqual(out[method], [(p,"h")])
        self.assertIn(("B","h",2,2,"first_neither",0),audit)

    def test_transitive_and_cycle(self):
        internal = {("b","a"),("a","b"),("c","b"),("b","c"),("c","a")}
        external = {("root","x"),("x","a"),("root","a")}
        expected = internal | {("root","x"),("x","a")}
        self.assertEqual(transitive_filter(internal|external),expected)

    def test_duplicates_and_case(self):
        out, audit = combine([("A","h",0),("A","h",1)], candidates("A"))
        tables = reports(out, audit, [("a","H"),("a","h")])
        self.assertEqual(tables["metrics"][1][0][1:], (2,2,1,1,0,0,.5,.5,.5))
        self.assertEqual(tables["metrics"][1][2][1:], (1,2,1,1,0,0,1,.5,2/3))

    def test_pareto_all_three_parent_orders(self):
        for order in permutations("ABC"):
            out, _ = combine(candidates("ABC"), candidates(order))
            expected = {p for i,p in enumerate("ABC") if not any(
                order.index(q)<order.index(p) for q in "ABC"[:i])}
            self.assertEqual({p for p,h in out["pareto"]},expected)

    def test_cli(self):
        with TemporaryDirectory() as tmp:
            for gold in (False,True):
                dest = Path(tmp)/str(gold)
                cmd = [sys.executable,"-m","taxensemble","--a","examples/a.json",
                       "--b","examples/b.json","--out",str(dest)]
                if gold:
                    cmd.extend(["--gold","examples/gold.json"])
                subprocess.run(cmd,check=True)
                self.assertEqual(len(list((dest/"predictions").glob("*.json"))),13)
                self.assertEqual((dest/"metrics.json").exists(),gold)
                with (dest/"predictions/transitive.json").open() as f:
                    self.assertEqual(json.load(f),
                                     [{"parent":"instrument","child":"strings"},
                                      {"parent":"strings","child":"violin"}])
                self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
