// runner.js

const telemetryLog = [];
window.allTelemetryRuns = []; // Ensure global access

function runUserCode() {
  const code = document.getElementById("userCode").value;
  resetRobot();
  telemetryLog.length = 0;

  try {
    new Function(code)();
  } catch (err) {
    logToConsole(`❌ Error: ${err.message}`);
  }

  runCommandQueue(() => {
    window.allTelemetryRuns.push(...telemetryLog); // Append to cumulative log
    checkAllDeliveriesComplete();
  });
}

function runCommandQueue(callback) {
  if (commandQueue.length === 0) {
    callback();
    return;
  }

  const nextCommand = commandQueue.shift();
  if (typeof nextCommand === "function") {
    nextCommand();
  }

  setTimeout(() => runCommandQueue(callback), 400); // Delay between commands
}

function checkAllDeliveriesComplete() {
  const allDelivered = deliveryGoals.every(goal => goal.delivered);
  if (allDelivered) {
    logToConsole("🎉 All deliveries complete!");
    alert("🎉 All deliveries complete!");
  }
}

function logTelemetry(action) {
  const telemetryEntry = {
    timestamp: new Date().toISOString(),
    robot_id: "alpha-001",
    position: { x: window.robot.x, y: window.robot.y },
    facing: window.robot.facing,
    action: action,
    success: true,
    current_tile_type: mapGrid[window.robot.y][window.robot.x].type,
    scanned_tile_ahead: {
      type: window.robot.lastScanResult || "unknown",
      distance: 1,
      scan_resolution: "low"
    },
    battery_level: window.robot.battery,
    logs: [`Executed ${action}`],
    sensor_noise_level: Math.random() * 0.01,
    cpu_usage: Math.random() * 20,
    mem_usage: Math.random() * 25,
    env_conditions: {
      virtual_light: 1,
      virtual_wind: 0
    },
    debug_flags: {
      retry_on_failure: true
    }
  };

  telemetryLog.push(telemetryEntry);
}

function downloadTelemetry() {
  const telemetryData = window.allTelemetryRuns || [];

  if (telemetryData.length === 0) {
    alert("No telemetry data to export.");
    return;
  }

  const headers = Object.keys(telemetryData[0]);
  const csvRows = [headers.join(",")];

  for (const row of telemetryData) {
    const csvRow = headers.map(h => {
      const val = row[h];
      return typeof val === "object" ? JSON.stringify(val).replaceAll(",", ";") : String(val);
    });
    csvRows.push(csvRow.join(","));
  }

  const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `telemetry_combined.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
