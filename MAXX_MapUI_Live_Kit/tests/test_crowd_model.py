"""Small, explainable weighted-field tests. No team repository is needed here."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import copy
import unittest
from crowd_model import (timestamp, validate_point, effective_weight, prepare_points,
                         density_at, sample_polyline, edge_exposure, travel_seconds)


def example():
    return validate_point({"id": "one", "name": "Training entrance", "kind": "class",
        "lat": 38.831, "lon": -77.307, "radius_m": 100, "weight": 0.8,
        "confidence": 0.5, "half_life_minutes": 60,
        "starts_at": "2026-10-26T09:00:00Z", "ends_at": "2026-10-26T13:00:00Z",
        "updated_at": "2026-10-26T10:00:00Z", "source": "SIMULATION",
        "data_mode": "simulated"})


class WeightedFieldChecks(unittest.TestCase):
    def setUp(self):
        self.point = example()
        self.now = timestamp("2026-10-26T10:00:00Z")

    def test_weight_times_confidence(self):
        self.assertAlmostEqual(effective_weight(self.point, self.now), 0.4)

    def test_freshness_halves_after_one_half_life(self):
        self.assertAlmostEqual(effective_weight(self.point, self.now + 3600), 0.2)

    def test_inactive_and_ended_points_have_zero_weight(self):
        self.assertEqual(effective_weight(self.point, self.now - 7200), 0)
        self.assertEqual(effective_weight(self.point, self.now + 10800), 0)

    def test_quadratic_distance_falloff_and_boundary(self):
        points = prepare_points([self.point], self.now, self.now + 1)
        self.assertAlmostEqual(density_at(38.831, -77.307, points), 0.4)
        self.assertAlmostEqual(density_at(38.831 + 50 / 111320, -77.307, points), 0.1)
        self.assertAlmostEqual(density_at(38.831 + 100 / 111320, -77.307, points), 0, places=9)

    def test_overlaps_saturate_without_exceeding_one(self):
        other = {**self.point, "id": "two"}
        points = prepare_points([self.point, other], self.now, self.now + 1)
        self.assertAlmostEqual(density_at(38.831, -77.307, points), 0.64)

    def test_midpoint_crowd_affects_long_edge(self):
        # Endpoints are outside a 20m radius, but the walkway passes through it.
        point = {**self.point, "radius_m": 20}
        points = prepare_points([point], self.now, self.now + 1)
        samples = sample_polyline([(38.830, -77.307), (38.832, -77.307)])
        self.assertGreater(edge_exposure(samples, points), 0)

    def test_more_exposure_never_reduces_travel_time(self):
        self.assertEqual(travel_seconds(100, 2, 0), 50)
        self.assertEqual(travel_seconds(100, 2, 1), 200)
        self.assertGreater(travel_seconds(100, 2, 0.8), travel_seconds(100, 2, 0.2))

    def test_bad_numbers_and_unzoned_times_are_rejected(self):
        self.assertNotIn("private_notes", validate_point({**self.point, "private_notes": "Do not publish this extra column"}))
        for field, value in [("weight", 2), ("confidence", -1), ("lat", float("nan")), ("half_life_minutes", 0)]:
            with self.assertRaises(ValueError):
                validate_point({**self.point, field: value})
        with self.assertRaises(ValueError):
            timestamp("2026-10-26T10:00:00")

    def test_forecast_window_includes_a_later_start(self):
        later = {**self.point, "starts_at": "2026-10-26T11:00:00Z"}
        self.assertEqual(prepare_points([later], self.now, self.now + 60), [])
        self.assertEqual(len(prepare_points([later], self.now, self.now + 7200)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
