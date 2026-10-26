"""Lesson 2: distinguish meters, model seconds and demo playback seconds."""
# Units matter: meters divided by meters/second produces seconds.
distance_m = 120
speed_mps = 1.2
travel_seconds = distance_m / speed_mps
# An accelerated clock shortens presentation time, not the modeled route.
playback_rate = 10
print('Model travel seconds:', travel_seconds)  # 100 seconds
print('10x presentation seconds:', travel_seconds / playback_rate)  # 10 seconds
