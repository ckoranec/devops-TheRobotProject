"""Lesson 4: route validity is a graph check, not a visual guess."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Campus, Simulation, edge_key

campus = Campus()  # Read the bundled team graph and building snapshot.
robot = Simulation(campus)
state = robot.configure('2', 'closure', 1)
# zip pairs adjacent route nodes. Every pair must avoid a closed edge.
valid = all(edge_key(a, b) not in robot.blocked
            for a, b in zip(robot.outbound, robot.outbound[1:]))
print('Outbound avoids closure:', valid)
print('Return kind:', state['return_kind'])
print('Round-trip meters:', state['total_meters'])
