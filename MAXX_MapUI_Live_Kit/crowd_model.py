"""Weighted crowd points -> spatial field -> route-edge time costs.

These are transparent demonstration heuristics, NOT calibrated pedestrian counts.
Routing nodes retain position/identity. We do not add a second cost at the nodes.
"""
import math
from datetime import datetime

METERS_PER_DEGREE = 111320.0


def timestamp(value):
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("A crowd timestamp needs Z or an explicit UTC offset.")
    return date.timestamp()


def distance_m(lat1, lon1, lat2, lon2):
    """Campus-scale metric approximation, matching the team's distance convention."""
    x = (lon2 - lon1) * METERS_PER_DEGREE * math.cos(math.radians((lat1 + lat2) / 2))
    y = (lat2 - lat1) * METERS_PER_DEGREE
    return math.hypot(x, y)


def validate_point(raw):
    """Normalize one JSON/CSV record; reject ambiguous or nonfinite inputs early."""
    if not isinstance(raw, dict):
        raise ValueError("Each crowd point must be a JSON object or CSV row.")
    # Publish only known public-safe schema fields, not arbitrary extra CSV/JSON
    # columns a source owner may have included. Names/source still need review.
    allowed = ("id", "name", "source", "kind", "data_mode", "lat", "lon", "radius_m",
               "weight", "confidence", "half_life_minutes", "starts_at", "ends_at", "updated_at")
    point = {key: raw.get(key) for key in allowed}
    for name in ("id", "name", "source"):
        if not isinstance(point.get(name), str) or not point[name].strip():
            raise ValueError("Crowd point requires " + name)
    point["id"] = str(point["id"])
    if point.get("kind") not in {"class", "event", "manual"}:
        raise ValueError("Crowd kind must be class, event or manual.")
    if point.get("data_mode") not in {"simulated", "predicted", "observed"}:
        raise ValueError("Crowd data_mode must describe its source, not imply live observation.")
    for field in ("lat", "lon", "radius_m", "weight", "confidence", "half_life_minutes"):
        point[field] = float(point[field])
        if not math.isfinite(point[field]):
            raise ValueError("Crowd numbers must be finite: " + field)
    if not (-90 <= point["lat"] <= 90 and -180 <= point["lon"] <= 180):
        raise ValueError("Crowd coordinates are outside the geographic range.")
    if not (1 <= point["radius_m"] <= 500 and 0 <= point["weight"] <= 1 and
            0 <= point["confidence"] <= 1 and 1 <= point["half_life_minutes"] <= 10080):
        raise ValueError("Radius, weight, confidence or half-life is outside its allowed range.")
    if timestamp(point["ends_at"]) <= timestamp(point["starts_at"]):
        raise ValueError("Crowd end must follow start.")
    timestamp(point["updated_at"])
    return point


def effective_weight(point, at):
    """Weight fades with age, and applies only inside the stated active window.

    A future updated_at has age zero (clock skew is visible in original metadata).
    It does not increase confidence above one or activate an inactive point.
    """
    if not timestamp(point["starts_at"]) <= at < timestamp(point["ends_at"]):
        return 0.0
    age_seconds = max(0.0, at - timestamp(point["updated_at"]))
    freshness = 2 ** (-age_seconds / (point["half_life_minutes"] * 60))
    return point["weight"] * point["confidence"] * freshness


def prepare_points(points, start, end):
    """Peak influence overlapping a planning window, conservative within that window.

    For a point that starts during the window, evaluate at its start. Because its
    freshness decays monotonically, this is its maximum during the overlap.
    """
    prepared = []
    for point in points:
        at = max(start, timestamp(point["starts_at"]))
        if at >= min(end, timestamp(point["ends_at"])):
            continue
        weight = effective_weight(point, at)
        if weight > 0:
            prepared.append({**point, "effective_weight": weight})
    return prepared


def density_at(lat, lon, prepared):
    """Bounded relative crowd index, 0..1, with quadratic distance falloff.

    Combine overlaps as 1 - product(1 - contribution). This saturates at one.
    It is an engineering score, not a probability or a people-per-square-meter unit.
    Duplicate record IDs are rejected by the importer before this is called.
    """
    remaining = 1.0
    for point in prepared:
        d = distance_m(lat, lon, point["lat"], point["lon"])
        kernel = max(0.0, 1.0 - d / point["radius_m"]) ** 2
        remaining *= 1.0 - point["effective_weight"] * kernel
    return min(1.0, max(0.0, 1.0 - remaining))


def sample_polyline(coords, spacing_m=10):
    """Return length-weighted segment MIDPOINTS; catch crowds between routing nodes.

    The input is [(latitude, longitude), ...]. Each sample represents a short
    stretch of the original walkway. No extra nodes are inserted in the team graph.
    """
    samples = []
    for a, b in zip(coords, coords[1:]):
        length = distance_m(*a, *b)
        if length <= 0:
            continue
        count = max(1, math.ceil(length / spacing_m))
        for i in range(count):
            fraction = (i + 0.5) / count
            samples.append((a[0] + fraction * (b[0] - a[0]),
                            a[1] + fraction * (b[1] - a[1]), length / count))
    return samples


def edge_exposure(samples, prepared):
    length = sum(part_length for _, _, part_length in samples)
    if not prepared or length <= 0:
        return 0.0
    return sum(density_at(lat, lon, prepared) * part_length
               for lat, lon, part_length in samples) / length


def travel_seconds(length_m, speed_mps, exposure):
    if speed_mps <= 0 or not 0 <= exposure <= 1:
        raise ValueError("Speed must be positive and exposure must be 0..1.")
    # A fully exposed edge takes four times its uncongested demonstration time.
    # This coefficient is tunable and requires calibration before real-world use.
    return length_m / speed_mps * (1 + 3 * exposure)
