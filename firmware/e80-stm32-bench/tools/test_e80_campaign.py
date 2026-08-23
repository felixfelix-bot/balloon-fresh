#!/usr/bin/env python3
"""Host tests for e80_campaign.py — adaptive sweep controller (TDD, no HW).

Run:  python3 -m pytest test_e80_campaign.py -v
  or: python3 -m unittest test_e80_campaign -v

Covers (plan §1–§5, §9 D1–D6):
  - sprt_decide: boundary math, decision table, n_min floor, EDGE at cap
  - wilson_ci: plan §5 table match
  - build_campaign_configs: PROBE=2, GOOD=25, DEGRADED=8, CLIFF, DUAL-BAND
  - maybe_reset: mod/band change/error/PA22/stop-change; same-mod skip
  - CampaignState: carry-forward DEAD/CLEAN skips, anchor contradiction,
    crash-safe JSON, symmetric far->near AND near->far (D4)
  - cliff_search: sentinel+bisect+n=50 validation (D2)
  - branch: verdict mapping from probe results
"""
import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import e80_campaign as camp  # noqa: E402


class TestSprtDecide(unittest.TestCase):
    """SPRT boundary math — plan §3."""

    # Boundaries: ln(beta/(1-alpha)) = -2.944, ln((1-beta)/alpha) = +2.944
    BOUND_LOW = math.log(0.05 / 0.95)   # -2.944
    BOUND_HIGH = math.log(0.95 / 0.05)   # +2.944

    def test_zero_errors_clean_at_15(self):
        """0 errors → CLEAN at n=15 (plan §3 table)."""
        v = camp.sprt_decide(0, 15)
        self.assertEqual(v.verdict, "CLEAN")
        self.assertEqual(v.k, 0)
        self.assertEqual(v.n, 15)

    def test_zero_errors_not_clean_before_15(self):
        """0 errors at n=14 → UNDECIDED (not past boundary yet)."""
        v = camp.sprt_decide(0, 14)
        self.assertEqual(v.verdict, "UNDECIDED")

    def test_all_errors_dead_at_10(self):
        """All errors → DEAD at n=10 (n_min floor, plan §3 table)."""
        v = camp.sprt_decide(10, 10)
        self.assertEqual(v.verdict, "DEAD")
        self.assertEqual(v.k, 10)
        self.assertEqual(v.n, 10)

    def test_all_errors_not_dead_before_nmin(self):
        """All errors at n=9 → UNDECIDED (n_min=10 floor)."""
        v = camp.sprt_decide(9, 9)
        self.assertEqual(v.verdict, "UNDECIDED")

    def test_one_error_clean_at_27(self):
        """k=1 → CLEAN at n=27 (plan §3 table)."""
        v = camp.sprt_decide(1, 27)
        self.assertEqual(v.verdict, "CLEAN")

    def test_one_error_not_clean_at_20(self):
        """k=1 at n=20 (n_cap) → EDGE (gray zone at cap)."""
        v = camp.sprt_decide(1, 20)
        self.assertEqual(v.verdict, "EDGE")

    def test_two_errors_clean_at_40(self):
        """k=2 → CLEAN at n=40 (plan §3 table)."""
        v = camp.sprt_decide(2, 40)
        self.assertEqual(v.verdict, "CLEAN")

    def test_edge_at_cap(self):
        """Gray zone (e.g. k=2, n=20 cap) → EDGE."""
        v = camp.sprt_decide(2, 20)
        self.assertEqual(v.verdict, "EDGE")

    def test_edge_at_cap_k1(self):
        """k=1, n=20 → EDGE (between boundaries)."""
        v = camp.sprt_decide(1, 20)
        self.assertEqual(v.verdict, "EDGE")

    def test_dead_with_some_success(self):
        """High error rate crosses DEAD boundary: k=4, n=10 → DEAD."""
        # LLR = 4*ln(10) + 6*ln(0.8/0.98) = 4*2.303 + 6*(-0.203) = 9.212 - 1.218 = 7.99 > 2.944
        v = camp.sprt_decide(4, 10)
        self.assertEqual(v.verdict, "DEAD")

    def test_verdict_constants(self):
        """Verdict strings are stable constants."""
        self.assertIn("CLEAN", camp.VERDICTS)
        self.assertIn("DEAD", camp.VERDICTS)
        self.assertIn("EDGE", camp.VERDICTS)

    def test_sprt_policy_params(self):
        """SPRT policy matches plan: p0=0.02, p1=0.20, alpha=0.05, beta=0.05."""
        p = camp.SPRT
        self.assertAlmostEqual(p["p0"], 0.02)
        self.assertAlmostEqual(p["p1"], 0.20)
        self.assertAlmostEqual(p["alpha"], 0.05)
        self.assertAlmostEqual(p["beta"], 0.05)
        self.assertEqual(p["n_min"], 10)
        self.assertEqual(p["n_cap"], 20)


class TestWilsonCI(unittest.TestCase):
    """Wilson 95% CI — plan §5 table."""

    def test_50_0(self):
        """n=50, k=0 → [0, 7.1%]."""
        lo, hi = camp.wilson_ci(0, 50)
        self.assertAlmostEqual(lo, 0.0, places=4)
        self.assertAlmostEqual(hi, 0.071, places=2)

    def test_50_25(self):
        """n=50, k=25 → [36.5%, 63.5%]."""
        lo, hi = camp.wilson_ci(25, 50)
        self.assertAlmostEqual(lo, 0.365, places=2)
        self.assertAlmostEqual(hi, 0.635, places=2)

    def test_20_0(self):
        """n=20, k=0 → [0, 16.1%]."""
        lo, hi = camp.wilson_ci(0, 20)
        self.assertAlmostEqual(lo, 0.0, places=4)
        self.assertAlmostEqual(hi, 0.161, places=2)

    def test_20_2(self):
        """n=20, k=2 → [2.8%, 30.1%]."""
        lo, hi = camp.wilson_ci(2, 20)
        self.assertAlmostEqual(lo, 0.028, places=2)
        self.assertAlmostEqual(hi, 0.301, places=2)

    def test_15_0(self):
        """n=15, k=0 → [0, 20.4%] (SPRT clean stop point)."""
        lo, hi = camp.wilson_ci(0, 15)
        self.assertAlmostEqual(lo, 0.0, places=4)
        self.assertAlmostEqual(hi, 0.204, places=2)

    def test_10_10(self):
        """n=10, k=10 → [72.3%, 100%] (SPRT dead stop point)."""
        lo, hi = camp.wilson_ci(10, 10)
        self.assertAlmostEqual(lo, 0.723, places=2)
        self.assertAlmostEqual(hi, 1.0, places=4)


class TestBuildCampaignConfigs(unittest.TestCase):
    """Config set builders — plan §1.1–§1.4."""

    def test_probe_has_2_canaries(self):
        """PROBE = 2 canaries: FLRC-650 + LoRa SF7 (D6 anchors)."""
        cfgs = camp.build_campaign_configs("probe")
        self.assertEqual(len(cfgs), 2)
        mods = [c["mod"] for c in cfgs]
        self.assertIn("flrc", mods)
        self.assertIn("lora", mods)
        # FLRC canary is BR650
        flrc_cfg = [c for c in cfgs if c["mod"] == "flrc"][0]
        self.assertEqual(flrc_cfg["br"], 650)
        # LoRa canary is SF7
        lora_cfg = [c for c in cfgs if c["mod"] == "lora"][0]
        self.assertEqual(lora_cfg["sf"], 7)

    def test_probe_dual_band(self):
        """D3: PROBE has dual-band pairs (868 + 2.4G)."""
        cfgs = camp.build_campaign_configs("probe", band="both")
        # 2 canaries per band = 4
        self.assertEqual(len(cfgs), 4)
        freqs = {c["freq"] for c in cfgs}
        has_868 = any(863e6 <= f <= 870e6 for f in freqs)
        has_2g4 = any(2400e6 <= f <= 2484e6 for f in freqs)
        self.assertTrue(has_868, "missing 868 MHz probe")
        self.assertTrue(has_2g4, "missing 2.4 GHz probe")

    def test_good_25_throughput(self):
        """GOOD ≈ 25 throughput configs (±2 tolerance for rounding)."""
        cfgs = camp.build_campaign_configs("good")
        self.assertGreaterEqual(len(cfgs), 23)
        self.assertLessEqual(len(cfgs), 30)

    def test_good_has_flrc_ladder(self):
        """GOOD contains FLRC BR {650,1300,2600} × LEN {128,255,511}."""
        cfgs = camp.build_campaign_configs("good")
        flrc_cfgs = [c for c in cfgs if c["mod"] == "flrc"]
        brs = {c["br"] for c in flrc_cfgs}
        plens = {c["plen"] for c in flrc_cfgs}
        for br in (650, 1300, 2600):
            self.assertIn(br, brs, f"missing FLRC BR {br}")
        for plen in (128, 255, 511):
            self.assertIn(plen, plens, f"missing LEN {plen}")

    def test_degraded_8_ladder(self):
        """DEGRADED ≈ 8 robustness ladder configs (±1 tolerance)."""
        cfgs = camp.build_campaign_configs("degraded")
        self.assertGreaterEqual(len(cfgs), 7)
        self.assertLessEqual(len(cfgs), 12)

    def test_degraded_has_sf9_to_sf12(self):
        """DEGRADED contains SF {9,10,11,12} BW125 LEN=16."""
        cfgs = camp.build_campaign_configs("degraded")
        sf_lora = [c for c in cfgs if c["mod"] == "lora" and c.get("bw") == 125
                   and c.get("plen") == 16]
        sfs = {c["sf"] for c in sf_lora}
        for sf in (9, 10, 11, 12):
            self.assertIn(sf, sfs, f"missing SF{sf} in degraded ladder")

    def test_cliff_sentinel_and_bisect(self):
        """CLIFF config set supports sentinel+bisect: has SF5 and SF12 sentinels."""
        cfgs = camp.build_campaign_configs("cliff")
        # Cliff axis: SF5..SF12 at BW125
        sfs = [c["sf"] for c in cfgs if c["mod"] == "lora" and c.get("bw") == 125]
        self.assertIn(5, sfs, "missing SF5 sentinel")
        self.assertIn(12, sfs, "missing SF12 sentinel")

    def test_all_configs_have_required_keys(self):
        """Every config dict has mod, pa, freq, plen, gap, label."""
        for mode in ("probe", "good", "degraded", "cliff"):
            cfgs = camp.build_campaign_configs(mode)
            for c in cfgs:
                for key in ("mod", "pa", "freq", "plen", "gap", "label"):
                    self.assertIn(key, c, f"{mode} config missing {key}: {c}")

    def test_good_config_count_dual_band(self):
        """D3: GOOD with band=both has 868 + 2.4G configs."""
        cfgs = camp.build_campaign_configs("good", band="both")
        has_868 = any(863e6 <= c["freq"] <= 870e6 for c in cfgs)
        has_2g4 = any(2400e6 <= c["freq"] <= 2484e6 for c in cfgs)
        self.assertTrue(has_868)
        self.assertTrue(has_2g4)


class TestMaybeReset(unittest.TestCase):
    """Reset policy gate — plan §4.2."""

    def test_mod_change_requires_reset(self):
        """LoRa→FLRC transition requires reset."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "flrc", "band": "868", "pa": 5, "error": False,
               "stop_id": "S1"}
        self.assertTrue(camp.maybe_reset(prev, cur, policy="strict"))

    def test_band_change_requires_reset(self):
        """868→2.4G band change requires reset."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "lora", "band": "2g4", "pa": 10, "error": False,
               "stop_id": "S1"}
        self.assertTrue(camp.maybe_reset(prev, cur, policy="strict"))

    def test_error_event_requires_reset(self):
        """Any error/unresponsive event requires reset."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "lora", "band": "868", "pa": 10, "error": True,
               "stop_id": "S1"}
        self.assertTrue(camp.maybe_reset(prev, cur, policy="strict"))

    def test_pa22_requires_reset(self):
        """PA22 cells always reset-guarded (D5)."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "lora", "band": "868", "pa": 22, "error": False,
               "stop_id": "S1"}
        self.assertTrue(camp.maybe_reset(prev, cur, policy="strict"))

    def test_stop_change_requires_reset(self):
        """New distance stop requires reset."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "lora", "band": "868", "pa": 10, "error": False,
               "stop_id": "S2"}
        self.assertTrue(camp.maybe_reset(prev, cur, policy="strict"))

    def test_same_mod_adjacency_skip_gated(self):
        """Same mod, same band, no error, same stop → skip in gated policy."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "lora", "band": "868", "pa": 7, "error": False,
               "stop_id": "S1"}
        self.assertFalse(camp.maybe_reset(prev, cur, policy="gated"))

    def test_same_mod_adjancy_reset_in_strict(self):
        """Same mod adjacency → still reset in strict policy."""
        prev = {"mod": "lora", "band": "868", "pa": 10, "error": False,
                "stop_id": "S1"}
        cur = {"mod": "lora", "band": "868", "pa": 7, "error": False,
               "stop_id": "S1"}
        self.assertTrue(camp.maybe_reset(prev, cur, policy="strict"))

    def test_flrc_to_flrc_same_band_skip_gated(self):
        """FLRC→FLRC same band, same stop → skip in gated."""
        prev = {"mod": "flrc", "band": "868", "pa": 5, "error": False,
                "stop_id": "S1", "br": 650}
        cur = {"mod": "flrc", "band": "868", "pa": 5, "error": False,
               "stop_id": "S1", "br": 1300}
        self.assertFalse(camp.maybe_reset(prev, cur, policy="gated"))


class TestCampaignState(unittest.TestCase):
    """Carry-forward state DB — plan §4.1, D4 (symmetric)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "campaign_state.json")

    def test_dead_skips_greater_distance(self):
        """DEAD@d skips d'>d (farther stops)."""
        st = camp.CampaignState(self.state_path)
        st.record_verdict("S1", d=50, config_label="FLRC-650",
                          verdict="DEAD", k=10, n=10)
        st.commit()
        skips = st.get_skips("S2", d=100)
        self.assertIn("FLRC-650", skips)

    def test_clean_skips_lesser_distance(self):
        """CLEAN@d skips d'<d (closer stops)."""
        st = camp.CampaignState(self.state_path)
        st.record_verdict("S3", d=200, config_label="FLRC-650",
                          verdict="CLEAN", k=0, n=15)
        st.commit()
        skips = st.get_skips("S2", d=100)
        self.assertIn("FLRC-650", skips)

    def test_dead_does_not_skip_closer(self):
        """DEAD@d does NOT skip d'<d (might be clean closer)."""
        st = camp.CampaignState(self.state_path)
        st.record_verdict("S3", d=200, config_label="FLRC-650",
                          verdict="DEAD", k=10, n=10)
        st.commit()
        skips = st.get_skips("S2", d=100)
        self.assertNotIn("FLRC-650", skips)

    def test_clean_does_not_skip_farther(self):
        """CLEAN@d does NOT skip d'>d (might be dead farther)."""
        st = camp.CampaignState(self.state_path)
        st.record_verdict("S1", d=50, config_label="FLRC-650",
                          verdict="CLEAN", k=0, n=15)
        st.commit()
        skips = st.get_skips("S2", d=100)
        self.assertNotIn("FLRC-650", skips)

    def test_anchor_contradiction_invalidates_skips(self):
        """Anchor contradiction → invalidate carry-forward for that config."""
        st = camp.CampaignState(self.state_path)
        # Record DEAD at d=100, which would skip d=200
        st.record_verdict("S2", d=100, config_label="FLRC-650",
                          verdict="DEAD", k=10, n=10)
        st.commit()
        # Now anchor at d=200 says CLEAN — contradicts DEAD carry-forward
        st.record_verdict("S3", d=200, config_label="FLRC-650",
                          verdict="CLEAN", k=0, n=15, is_anchor=True)
        st.commit()
        # Skips should be invalidated for FLRC-650
        skips = st.get_skips("S4", d=300)
        self.assertNotIn("FLRC-650", skips)

    def test_crash_safe_json_load(self):
        """State survives crash: commit then reload from disk."""
        st1 = camp.CampaignState(self.state_path)
        st1.record_verdict("S1", d=50, config_label="SF7",
                           verdict="CLEAN", k=0, n=15)
        st1.commit()
        # Simulate crash: new instance loads from file
        st2 = camp.CampaignState(self.state_path)
        # S1 data should be present
        data = st2.get_stop_data("S1")
        self.assertIsNotNone(data)
        self.assertIn("SF7", data)

    def test_crash_safe_partial_json(self):
        """Corrupt/partial JSON doesn't crash — starts fresh."""
        with open(self.state_path, "w") as f:
            f.write('{"partial": broken')
        st = camp.CampaignState(self.state_path)
        # Should not raise, should have empty state
        skips = st.get_skips("S1", d=50)
        self.assertEqual(skips, set())

    def test_symmetric_far_to_near(self):
        """D4: carry-forward works far→near (DEAD@far skips nothing closer,
        CLEAN@far skips closer)."""
        st = camp.CampaignState(self.state_path)
        # Walk far→near: start at d=200, go to d=100
        st.record_verdict("S3", d=200, config_label="SF7",
                          verdict="CLEAN", k=0, n=15)
        st.commit()
        # CLEAN at d=200 → skip d=100 (closer)
        skips = st.get_skips("S2", d=100)
        self.assertIn("SF7", skips)

    def test_symmetric_near_to_far(self):
        """D4: carry-forward works near→far (DEAD@near skips farther)."""
        st = camp.CampaignState(self.state_path)
        # Walk near→far: start at d=50, go to d=100
        st.record_verdict("S1", d=50, config_label="SF7",
                          verdict="DEAD", k=10, n=10)
        st.commit()
        # DEAD at d=50 → skip d=100 (farther)
        skips = st.get_skips("S2", d=100)
        self.assertIn("SF7", skips)

    def test_commit_idempotent(self):
        """Multiple commits don't duplicate data."""
        st = camp.CampaignState(self.state_path)
        st.record_verdict("S1", d=50, config_label="SF7",
                          verdict="CLEAN", k=0, n=15)
        st.commit()
        st.commit()  # double commit
        st2 = camp.CampaignState(self.state_path)
        data = st2.get_stop_data("S1")
        self.assertEqual(len(data["SF7"]), 1)


class TestCliffSearch(unittest.TestCase):
    """Cliff search: sentinel + bisect + n=50 validation — plan §1.4, D2."""

    SF_AXIS = [5, 6, 7, 8, 9, 10, 11, 12]

    def test_dead_sf5_all_dead(self):
        """All SFs dead → no clean LoRa at this stop."""
        # All SFs are dead
        def sprt_stub(sf_label, n_cap=20):
            return camp.SprtResult("DEAD", 10, 10)

        result = camp.cliff_search(self.SF_AXIS, sprt_stub, d=100,
                                   state=None, band="868")
        self.assertEqual(result.boundary_lo, None)
        self.assertEqual(result.boundary_hi, None)
        self.assertIn("dead", result.summary.lower())

    def test_clean_sf5_whole_axis_clean(self):
        """SF5 sentinel CLEAN → whole axis clean at this stop."""
        calls = []
        def sprt_stub(sf_label, n_cap=20):
            calls.append(sf_label)
            return camp.SprtResult("CLEAN", 0, 15)
        result = camp.cliff_search(self.SF_AXIS, sprt_stub, d=100,
                                   state=None, band="868")
        # Should detect SF5 clean and stop (whole axis clean)
        self.assertEqual(result.boundary_lo, 5)  # fastest clean
        self.assertEqual(result.boundary_hi, 12)
        self.assertIn("clean", result.summary.lower())

    def test_bisect_finds_boundary(self):
        """Bisect: SF5 dead, SF12 clean → finds boundary SF."""
        # SF5-7 dead, SF8-12 clean
        def sprt_stub(sf_label, n_cap=20):
            sf = int(sf_label.replace("SF", ""))
            if sf <= 7:
                return camp.SprtResult("DEAD", 10, 10)
            return camp.SprtResult("CLEAN", 0, 15)
        result = camp.cliff_search(self.SF_AXIS, sprt_stub, d=100,
                                   state=None, band="868")
        # Boundary: lo=SF7 (dead), hi=SF8 (clean)
        self.assertEqual(result.boundary_lo, 7)
        self.assertEqual(result.boundary_hi, 8)

    def test_validation_n50_on_boundary(self):
        """D2: boundary cells validated at n=50."""
        validation_calls = []
        def sprt_stub(sf_label, n_cap=20):
            sf = int(sf_label.replace("SF", ""))
            if sf <= 7:
                return camp.SprtResult("DEAD", 10, 10)
            return camp.SprtResult("CLEAN", 0, 15)
        def validation_stub(sf_label, n=50):
            validation_calls.append((sf_label, n))
            sf = int(sf_label.replace("SF", ""))
            if sf <= 7:
                return camp.SprtResult("DEAD", 40, 50)
            return camp.SprtResult("CLEAN", 0, 50)
        result = camp.cliff_search(self.SF_AXIS, sprt_stub, d=100,
                                   state=None, band="868",
                                   validate_fn=validation_stub)
        # Validation called on boundary cells (lo=7, hi=8)
        self.assertEqual(len(validation_calls), 2)
        validated_sfs = [int(s[0].replace("SF", "")) for s in validation_calls]
        self.assertIn(7, validated_sfs)
        self.assertIn(8, validated_sfs)
        # All validations at n=50
        for _, n in validation_calls:
            self.assertEqual(n, 50)


class TestBranch(unittest.TestCase):
    """Branch decision from probe verdicts — plan §1.1."""

    def test_both_clean_good(self):
        """Both probes CLEAN → GOOD."""
        v = camp.branch(
            camp.SprtResult("CLEAN", 0, 15),
            camp.SprtResult("CLEAN", 0, 15))
        self.assertEqual(v, "GOOD")

    def test_sf7_dead_degraded(self):
        """SF7 probe DEAD → DEGRADED."""
        v = camp.branch(
            camp.SprtResult("DEAD", 10, 10),
            camp.SprtResult("CLEAN", 0, 15))
        self.assertEqual(v, "DEGRADED")

    def test_sf7_edge_cliff(self):
        """SF7 probe EDGE → EDGE (cliff first)."""
        v = camp.branch(
            camp.SprtResult("EDGE", 2, 20),
            camp.SprtResult("CLEAN", 0, 15))
        self.assertEqual(v, "EDGE")

    def test_flrc_dead_sf7_clean_still_good(self):
        """FLRC dead but SF7 clean → still GOOD (FLRC dies first at range)."""
        v = camp.branch(
            camp.SprtResult("CLEAN", 0, 15),
            camp.SprtResult("DEAD", 10, 10))
        self.assertEqual(v, "GOOD")

    def test_both_edge_edge(self):
        """Both probes EDGE → EDGE."""
        v = camp.branch(
            camp.SprtResult("EDGE", 2, 20),
            camp.SprtResult("EDGE", 2, 20))
        self.assertEqual(v, "EDGE")

    def test_both_dead_degraded(self):
        """Both probes DEAD → DEGRADED."""
        v = camp.branch(
            camp.SprtResult("DEAD", 10, 10),
            camp.SprtResult("DEAD", 10, 10))
        self.assertEqual(v, "DEGRADED")


if __name__ == "__main__":
    unittest.main()