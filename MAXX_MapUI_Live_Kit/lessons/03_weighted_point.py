"""Lesson 3: use the SAME crowd model as the running application."""
import sys
from pathlib import Path
# Running a lesson directly puts lessons/ on the import path. Add its parent.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crowd_model import validate_point, timestamp, effective_weight

# These fixed dates make the exercise reproducible on any day.
point = validate_point({
    'id': 'practice-1', 'name': 'Practice entrance', 'source': 'SIMULATION',
    'kind': 'class', 'data_mode': 'simulated',
    'lat': 38.831, 'lon': -77.307, 'radius_m': 100,
    'weight': 0.8, 'confidence': 0.5, 'half_life_minutes': 60,
    'starts_at': '2026-10-27T09:00:00Z', 'ends_at': '2026-10-27T13:00:00Z',
    'updated_at': '2026-10-27T10:00:00Z',
})
now = timestamp('2026-10-27T10:00:00Z')
# Intensity .8 times confidence .5 gives .4 at update time.
print('Initial effective weight:', effective_weight(point, now))
# Freshness halves after one half-life: .4 becomes .2.
print('One hour later:', effective_weight(point, now + 3600))
