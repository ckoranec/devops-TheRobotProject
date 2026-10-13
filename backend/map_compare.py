"""
Usage:
    changes = compare_maps(fresh_data, saved_data)
    if not is_in_sync(changes):
        print(changes)
"""
def simplify(overpass_data):
    """Keep only what matters for each path: its points and its tags.

    """
    ways = {}
    for element in overpass_data["elements"]:
        if element["type"] == "way":
            ways[element["id"]] = {
                "points": [(point["lat"], point["lon"]) for point in element["geometry"]],
                "tags": element.get("tags", {}),
            }
    return ways


def compare_maps(fresh_data, saved_data):
    """ list which paths were added, removed or changed in the live map."""
    new = simplify(fresh_data)
    old = simplify(saved_data)
    return {
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "changed": sorted(way_id for way_id in new.keys() & old.keys()
                          if new[way_id] != old[way_id]),
    }


def is_in_sync(changes):
    """True when nothing was added, removed or changed."""
    return not (changes["added"] or changes["removed"] or changes["changed"])



# TESTS 

"""
uncomment this to test with sample data
def way(way_id, points, highway="footway"):
    """Build one path the way Overpass returns it with 'out geom'."""
    return {
        "type": "way",
        "id": way_id,
        "geometry": [{"lat": lat, "lon": lon} for lat, lon in points],
        "tags": {"highway": highway},
    }


def overpass(*ways, timestamp="2026-10-13T09:00:00Z"):
    """Build a full Overpass response around some paths."""
    return {"osm3s": {"timestamp_osm_base": timestamp}, "elements": list(ways)}


PATH_A = way(1, [(38.830, -77.310), (38.831, -77.309)])
PATH_B = way(2, [(38.831, -77.309), (38.832, -77.308)])

"""
def test_same_map_downloaded_twice_is_in_sync():
    # different timestamp and element order, same map
    first = overpass(PATH_A, PATH_B, timestamp="2026-10-13T09:00:00Z")
    second = overpass(PATH_B, PATH_A, timestamp="2026-10-13T09:05:00Z")
    assert is_in_sync(compare_maps(first, second))


def test_new_path_is_added():
    changes = compare_maps(overpass(PATH_A, PATH_B), overpass(PATH_A))
    assert changes["added"] == [2]


def test_deleted_path_is_removed():
    changes = compare_maps(overpass(PATH_A), overpass(PATH_A, PATH_B))
    assert changes["removed"] == [2]


def test_moved_path_is_changed():
    moved = way(1, [(38.8305, -77.310), (38.831, -77.309)])
    changes = compare_maps(overpass(moved), overpass(PATH_A))
    assert changes["changed"] == [1]


def test_reversed_path_is_changed():
    reversed_path = way(1, [(38.831, -77.309), (38.830, -77.310)])
    changes = compare_maps(overpass(reversed_path), overpass(PATH_A))
    assert changes["changed"] == [1]


def test_footway_becoming_steps_is_changed():
    # the robot can't climb steps, so this change matters
    steps = way(1, [(38.830, -77.310), (38.831, -77.309)], highway="steps")
    changes = compare_maps(overpass(steps), overpass(PATH_A))
    assert changes["changed"] == [1]


def test_out_of_sync_when_anything_differs():
    assert not is_in_sync({"added": [], "removed": [], "changed": [1]})