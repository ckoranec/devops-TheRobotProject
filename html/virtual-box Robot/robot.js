// robot.js
class Robot {
  constructor(x, y, direction) {
    this.x = x;
    this.y = y;
    this.direction = direction;
    this.hasDelivered = false;
    this.battery = 100;
    this.lastScanResult = "unknown";
    this.facing = direction;
  }

  
  peekForward() {
    let x = this.x;
    let y = this.y;
    switch (this.direction) {
      case "N": y--; break;
      case "E": x++; break;
      case "S": y++; break;
      case "W": x--; break;
    }
    if (x < 0 || y < 0 || x >= gridSizeX || y >= gridSizeY) return { type: "wall", x, y };
    if (obstacles.some(o => o.x === x && o.y === y)) return { type: "obstacle", x, y };
    if (deliveryGoals.some(g => g.x === x && g.y === y)) return { type: "goal", x, y };
    return { type: "empty", x, y };
  }

  moveForward() {
    if (this.battery <= 0) {
      logMessage("🔋 Battery depleted.");
      return false;
    }
  
    const drain = randomBatteryDrain();
    this.battery = Math.max(0, this.battery - drain);
    if (this.battery <= 20) logMessage("⚠️ Battery low!");
  
    let x = this.x;
    let y = this.y;
  
    switch (this.direction) {
      case "N": y--; break;
      case "E": x++; break;
      case "S": y++; break;
      case "W": x--; break;
    }
  
    if (
      x < 0 || y < 0 ||
      y >= mapGrid.length || x >= mapGrid[0].length
    ) {
      logMessage("❌ Move blocked: out of bounds.");
      return false;
    }
  
    const nextTile = mapGrid[y][x];
    if (!nextTile?.navigable) {
      logMessage(`❌ Move blocked: (${x}, ${y}) is not navigable.`);
      return false;
    }
  
    this.x = x;
    this.y = y;
  
    logMessage(`Moved to (${this.x}, ${this.y})`);
    updateBatteryDisplay();
    return true;
  }

  moveBackward() {
    if (this.battery <= 0) {
      logMessage("🔋 Battery depleted.");
      return false;
    }
  
    const drain = randomBatteryDrain();
    this.battery = Math.max(0, this.battery - drain);
    if (this.battery <= 20) logMessage("⚠️ Battery low!");
  
    let x = this.x;
    let y = this.y;
  
    switch (this.direction) {
      case "N": y++; break;
      case "E": x--; break;
      case "S": y--; break;
      case "W": x++; break;
    }
  
    if (
      x < 0 || y < 0 ||
      y >= mapGrid.length || x >= mapGrid[0].length
    ) {
      logMessage("❌ Move blocked: out of bounds.");
      return false;
    }
  
    const nextTile = mapGrid[y][x];
    if (!nextTile?.navigable) {
      logMessage(`❌ Move blocked: (${x}, ${y}) is not navigable.`);
      return false;
    }
  
    this.x = x;
    this.y = y;
  
    logMessage(`Moved backward to (${this.x}, ${this.y})`);
    updateBatteryDisplay();
    return true;
  }
  
  turnRight() {
    const dirs = ["N", "E", "S", "W"];
    const idx = dirs.indexOf(this.direction);
    this.direction = dirs[(idx + 1) % 4];
    this.facing = this.direction;
    logMessage(`Turned right, now facing ${this.direction}`);
  }

  turnLeft() {
    const dirs = ["N", "W", "S", "E"];
    const idx = dirs.indexOf(this.direction);
    this.direction = dirs[(idx + 1) % 4];
    this.facing = this.direction;
    logMessage(`Turned left, now facing ${this.direction}`);
  }

  deliver(orderId) {
    if (this.battery <= 0) {
      logMessage("🔋 Battery depleted.");
      return false;
    }
  
    const drain = randomBatteryDrain();
    this.battery = Math.max(0, this.battery - drain);
    if (this.battery <= 20) logMessage("⚠️ Battery low!");
  
    // 🔍 Use helper to get goal at current position
    const goal = getDeliveryGoalAt(this.x, this.y);
    if (!goal) {
      logMessage(`❌ No delivery point at (${this.x}, ${this.y})`);
      return false;
    }
  
    if (goal.orderId !== orderId) {
      logMessage(`❌ Failed delivery. Package ${orderId} does not match this location (${goal.orderId})`);
      return false;
    }
  
    if (goal.delivered) {
      logMessage(`ℹ️ Order '${orderId}' already delivered.`);
      return false;
    }
  
    goal.delivered = true;
    this.hasDelivered = true;
    deliveries.push({ x: this.x, y: this.y, orderId });
  
    logMessage(`📦 Delivered: ${orderId} at (${this.x}, ${this.y})`);
    updateBatteryDisplay();
  
    setTimeout(() => {
      checkAllDeliveriesComplete();
    }, 800);
  
    return true;
  }

  scan() {
    if (this.battery <= 0) {
      logMessage("🔋 Battery depleted. Recharge required.");
      return "battery-dead";
    }

    const drain = randomBatteryDrain();
    this.battery = Math.max(0, this.battery - drain);
    if (this.battery <= 20) logMessage("⚠️ Battery low!");

    let x = this.x;
    let y = this.y;
    switch (this.direction) {
      case "N": y -= 1; break;
      case "S": y += 1; break;
      case "E": x += 1; break;
      case "W": x -= 1; break;
    }

    const found = mapGrid[y]?.[x];
    const result = found ? found.type + (found.id ? ` (${found.id})` : "") : "empty";
    this.lastScanResult = result;
    logMessage(`🧭 Scan Result: ${result}`);
    updateBatteryDisplay();
    return result;
  }

  recharge() {
    this.battery = 100;
    logMessage("🔌 Recharging complete. Battery full!");
    updateBatteryDisplay();
  }

  display() {
    const empty = window.truckEmptyImage;
    const cargo = window.truckCargoImage;
    const img = this.hasDelivered ? empty : cargo;

    if (!img) {
      console.warn("⚠️ No truck image loaded, using fallback");
      fill("blue");
      rect(this.x * tileSize, this.y * tileSize, tileSize, tileSize);
      return;
    }

    let angle = 0;
    let flipX = false;

    switch (this.direction) {
      case "N": angle = -HALF_PI; flipX = true; break;
      case "E": angle = 0; flipX = true; break;
      case "S": angle = HALF_PI; flipX = true; break;
      case "W": angle = 0; flipX = false; break;
    }

    push();
    translate(this.x * tileSize + tileSize / 2, this.y * tileSize + tileSize / 2);
    rotate(angle);
    if (flipX) scale(-1, 1);
    imageMode(CENTER);
    image(img, 0, 0, tileSize, tileSize);
    pop();
  }
}

let stepIndex = 0;
let runStartTime = null;
let rechargeCount = 0;
let lastBatteryLevel = 100;

function updateBatteryDisplay() {
  const el = document.getElementById("batteryDisplay");
  if (el) el.textContent = `🔋 Battery: ${window.robot.battery}%`;
}

function randomBatteryDrain(min = 1, max = 10) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function checkAllDeliveriesComplete() {
  const allDelivered = deliveryGoals.every(goal => goal.delivered);
  if (allDelivered) {
    logToConsole("🎉 All deliveries complete!");
    if (typeof showSuccessMessage === "function") showSuccessMessage();
  }
}
function runRobotActionQueue() {
  const robot = window.robot;

  if (!window.allTelemetryRuns) {
    window.allTelemetryRuns = [];
  }

  if (!window.robotActionQueue || window.robotActionQueue.length === 0) {
    showSuccessMessage();
    return;
  }

  if (robot.battery <= 0) {
    logMessage("🔋 Battery depleted.");
    return;
  }

  if (!runStartTime) runStartTime = Date.now();

  // Check for recharge need before step execution
  if (
    robot.battery <= 15 &&
    window.robotActionQueue[0]?.action !== "recharge"
  ) {
    logMessage("⚠️ Battery low! Queuing recharge...");
    window.robotActionQueue.unshift({ action: "recharge" });
  }

  const step = window.robotActionQueue.shift();

  // Get tile info before movement
  const currentTile = mapGrid[robot.y]?.[robot.x];
  const currentTileType = currentTile?.type || "unknown";

  // Persist current goal based on undelivered delivery
  let currentGoal = deliveryGoals.find(g => !g.delivered);
  let currentOrderId = currentGoal?.orderId || "None";

  const prevBattery = robot.battery;
  let rechargeTriggered = false;
  let didSomething = false;

  // Execute action
  switch (step.action) {
    case "turn":
      faceDirection(step.direction);
      logMessage(`↩️ Turned to ${step.direction}`);
      didSomething = true;
      break;
    case "move":
      didSomething = robot.moveForward();
      logMessage(didSomething ? "➡️ Moved forward" : "🚫 Move blocked");
      break;
    case "deliver":
      didSomething = robot.deliver(step.orderId);
      if (didSomething) {
        logMessage(`📦 Delivered: ${step.orderId}`);
        // Refresh to next goal if delivery succeeded
        currentGoal = deliveryGoals.find(g => !g.delivered);
        currentOrderId = currentGoal?.orderId || "None";
      }
      break;
    case "recharge":
      robot.recharge();
      rechargeCount++;
      rechargeTriggered = true;
      logMessage("🔋 Recharged to 100%");
      didSomething = true;
      break;
  }

  // Metrics
  const batteryDrainThisStep = Math.max(0, prevBattery - robot.battery);
  const distanceToGoal = currentGoal
    ? Math.abs(robot.x - currentGoal.x) + Math.abs(robot.y - currentGoal.y)
    : 0;
  const isAtGoal = currentGoal
    ? robot.x === currentGoal.x && robot.y === currentGoal.y
    : false;
  const totalDeliveries = deliveryGoals.length;
  const completedDeliveries = deliveryGoals.filter(g => g.delivered).length;
  const timeElapsedSinceStart = ((Date.now() - runStartTime) / 1000).toFixed(2);

  // Save telemetry snapshot
  window.allTelemetryRuns.push({
    timestamp: Date.now(),
    stepIndex: stepIndex++,
    action: step.action,
    x: robot.x,
    y: robot.y,
    direction: robot.direction,
    batteryRemaining: robot.battery,
    batteryDrainThisStep,
    tileType: currentTileType,
    orderId: currentOrderId,
    distanceToGoal,
    isAtGoal,
    rechargeTriggered,
    rechargeCount,
    totalDeliveries,
    completedDeliveries,
    timeElapsedSinceStart
  });

  updateBatteryDisplay();

  const speed = parseInt(document.getElementById("speedSelector")?.value || 1000, 10);
  setTimeout(runRobotActionQueue, speed);
}



function faceDirection(targetDir) {
  const current = window.robot.direction;
  const dirs = ["N", "E", "S", "W"];
  const iCur = dirs.indexOf(current);
  const iTarget = dirs.indexOf(targetDir);
  const diff = (iTarget - iCur + 4) % 4;

  if (diff === 0) return;
  if (diff === 1) robot.turnRight();
  else if (diff === 3) robot.turnLeft();
  else if (diff === 2) robot.turnAround();
}


function getDeliveryGoalAt(x, y) {
  return deliveryGoals.find(g => g.x === x && g.y === y);
}