import unittest
from build import ROOT, render
from connections import CAPS, CUTOFF, DEPARTURE, PROFILES, RUNS, Transfer, generate, replay


class ConnectionTests(unittest.TestCase):
    def test_exact_cutoff_is_included(self):
        lots = [Transfer("a", "i", 10, CUTOFF), Transfer("b", "i", 20, CUTOFF + 30),
                Transfer("c", "i", 40, CUTOFF + 31)]
        result = replay(lots, 30)
        self.assertEqual((result["connected"], result["missed"], result["missed_lots"]), (30, 40, ["c"]))

    def test_no_hold_needed_or_release_early(self):
        ready = Transfer("a", "i", 15, CUTOFF)
        late = Transfer("b", "i", 20, CUTOFF + 12)
        self.assertEqual(replay([ready], 90)["hold"], 0)
        self.assertEqual(replay([ready, late], 90)["departure"], DEPARTURE + 12)

    def test_future_after_release_does_not_change_decision(self):
        soon = Transfer("a", "i", 20, CUTOFF + 15)
        first = replay([soon, Transfer("b", "i", 40, CUTOFF + 31)], 30)
        second = replay([soon, Transfer("b", "i", 40, CUTOFF + 300)], 30)
        self.assertEqual(first, second)

    def test_conservation_hold_bound_and_monotonic_recovery(self):
        for profile in PROFILES:
            for seed in range(1, RUNS + 1):
                lots = generate(seed, profile)
                previous = sum(lot.teu for lot in lots)
                for cap in CAPS:
                    r = replay(lots, cap)
                    self.assertLessEqual(r["hold"], cap)
                    self.assertGreaterEqual(r["hold"], 0)
                    self.assertEqual(r["connected"] + r["missed"], r["total"])
                    self.assertLessEqual(r["missed"], previous)
                    self.assertEqual(r["missed_lots"], sorted(l.name for l in lots if l.ready > r["cutoff"]))
                    previous = r["missed"]

    def test_report_reproduces(self):
        self.assertEqual((ROOT / "index.html").read_text(encoding="utf-8"), render())
