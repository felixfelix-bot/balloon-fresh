import math

from conftest import load_link_budget

lb = load_link_budget()


class TestFreeSpacePathLoss:
    def test_known_value_868mhz_1km(self):
        result = lb.free_space_path_loss_db(868.0, 1.0)
        assert math.isclose(result, 32.4 + 20 * math.log10(868.0), abs_tol=0.5)

    def test_known_value_2400mhz_1km(self):
        result = lb.free_space_path_loss_db(2400.0, 1.0)
        assert result > 90

    def test_doubles_with_distance(self):
        loss_1km = lb.free_space_path_loss_db(868.0, 1.0)
        loss_10km = lb.free_space_path_loss_db(868.0, 10.0)
        assert math.isclose(loss_10km - loss_1km, 20.0, abs_tol=0.1)

    def test_doubles_with_frequency(self):
        loss_868 = lb.free_space_path_loss_db(868.0, 100.0)
        loss_2400 = lb.free_space_path_loss_db(2400.0, 100.0)
        assert loss_2400 > loss_868

    def test_inverse_square_law(self):
        loss_100 = lb.free_space_path_loss_db(868.0, 100.0)
        loss_200 = lb.free_space_path_loss_db(868.0, 200.0)
        assert math.isclose(loss_200 - loss_100, 6.0, abs_tol=0.1)


class TestSensitivity:
    def test_sf9_125_known(self):
        assert lb.get_sensitivity(9, 125) == -129

    def test_sf7_125_known(self):
        assert lb.get_sensitivity(7, 125) == -123

    def test_sf12_125_known(self):
        assert lb.get_sensitivity(12, 125) == -137

    def test_unknown_sf_returns_default(self):
        result = lb.get_sensitivity(20, 125)
        assert result == -130 + 20

    def test_higher_sf_more_sensitive(self):
        assert lb.get_sensitivity(12, 125) < lb.get_sensitivity(7, 125)


class TestAirRate:
    def test_sf9_125_known(self):
        assert lb.get_air_rate_bps(9, 125) == 1768

    def test_sf7_125_known(self):
        assert lb.get_air_rate_bps(7, 125) == 5469

    def test_unknown_returns_zero(self):
        assert lb.get_air_rate_bps(20, 999) == 0

    def test_higher_sf_lower_rate(self):
        assert lb.get_air_rate_bps(7, 125) > lb.get_air_rate_bps(12, 125)


class TestMaxPayload:
    def test_sf7_222(self):
        assert lb.get_max_payload(7) == 222

    def test_sf12_51(self):
        assert lb.get_max_payload(12) == 51


class TestTimeOnAir:
    def test_nonzero_for_valid(self):
        toa = lb.estimate_toa_ms(28, 9, 125)
        assert toa > 0

    def test_larger_payload_longer_toa(self):
        toa_28 = lb.estimate_toa_ms(28, 9, 125)
        toa_200 = lb.estimate_toa_ms(200, 9, 125)
        assert toa_200 > toa_28

    def test_higher_sf_longer_toa(self):
        toa_sf7 = lb.estimate_toa_ms(28, 7, 125)
        toa_sf12 = lb.estimate_toa_ms(28, 12, 125)
        assert toa_sf12 > toa_sf7

    def test_zero_for_unknown_sf_bw(self):
        toa = lb.estimate_toa_ms(28, 20, 999)
        assert toa == 0


class TestCalculateLink:
    def test_tracker_scenario_positive_margin(self):
        r = lb.calculate_link(868.0, 9, 125, 22, 2.15, 5.0, 1.0, 300, 28)
        assert r["link_margin_db"] > 0
        assert r["feasible"] is True

    def test_mesh_v1_scenario(self):
        r = lb.calculate_link(2400.0, 7, 125, 22, 2.15, 5.0, 1.0, 300, 200)
        assert r["feasible"] is True

    def test_very_long_range_negative_margin(self):
        r = lb.calculate_link(868.0, 9, 125, 22, 2.15, 5.0, 1.0, 5000, 28)
        assert r["link_margin_db"] < 0

    def test_zero_distance(self):
        r = lb.calculate_link(868.0, 9, 125, 22, 2.15, 5.0, 1.0, 0.001, 28)
        assert r["fspl_db"] < 40

    def test_received_power_calculation(self):
        r = lb.calculate_link(868.0, 9, 125, 22, 2.15, 5.0, 1.0, 300, 28)
        expected_eirp = 22 + 2.15 - 1.0
        expected_rx = expected_eirp - r["fspl_db"] + 5.0
        assert math.isclose(r["received_power_dbm"], expected_rx, abs_tol=0.01)

    def test_max_range_extends_when_positive_margin(self):
        r = lb.calculate_link(868.0, 9, 125, 22, 2.15, 5.0, 1.0, 300, 28)
        if r["link_margin_db"] > 0:
            assert r["max_range_km"] > 300


class TestScenarios:
    def test_all_scenarios_valid(self):
        for key, s in lb.SCENARIOS.items():
            params = {k: v for k, v in s.items() if k != "name"}
            r = lb.calculate_link(**params)
            assert "link_margin_db" in r
            assert "feasible" in r

    def test_tracker_scenario_exists(self):
        assert "tracker" in lb.SCENARIOS

    def test_mesh_v1_scenario_exists(self):
        assert "mesh_v1" in lb.SCENARIOS

    def test_mesh_v2_scenario_exists(self):
        assert "mesh_v2" in lb.SCENARIOS

    def test_tracker_long_range_scenario_exists(self):
        assert "tracker_long_range" in lb.SCENARIOS
