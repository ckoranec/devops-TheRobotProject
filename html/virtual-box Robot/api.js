// api.js
let commandQueue = [];
let obstacles = [];
let deliveries = [];
window.deliveryGoals = [];
let deliveryQueue = [];
let isQueueRunning = false;

function moveForward() {
  commandQueue.push(() => {
    const success = window.robot.moveForward();
    logTelemetry("move_forward", success);
  });
}

function turnRight() {
  commandQueue.push(() => {
    window.robot.turnRight();
    logTelemetry("turn_right");
  });
}

function turnLeft() {
  commandQueue.push(() => {
    window.robot.turnLeft();
    logTelemetry("turn_left");
  });
}

function moveBackward() {
  commandQueue.push(() => {
    const success = window.robot.moveBackward();
    logTelemetry("move_backward", success);
  });
}

function turnAround() {
  commandQueue.push(() => {
    window.robot.turnRight();
    window.robot.turnRight();
    logTelemetry("turn_around");
  });
}

function recharge() {
  commandQueue.push(() => {
    window.robot.recharge();
    logTelemetry("recharge");
  });
}

function scan() {
  commandQueue.push(() => {
    const result = window.robot.scan();
    window.robot.lastScanResult = result;
    logMessage(`🔍 Scan result: ${result}`);
    logTelemetry("scan");
  });
}

function startDeliveryQueue() {
  if (!window.robot || deliveryQueue.length === 0 || isQueueRunning) return;
  isQueueRunning = true;

  const next = deliveryQueue.shift();
  const start = { x: window.robot.x, y: window.robot.y };
  const path = findPath(start, next, mapGrid);

  if (path.length === 0) {
    logMessage(`❌ No path to (${next.x}, ${next.y})`);
    isQueueRunning = false;
    return;
  }

  followPath(path, () => {
    deliver(next.orderId);
    setTimeout(() => {
      isQueueRunning = false;   // ✅ Reset flag so next call works
      startDeliveryQueue();     // 🔁 Move on to the next delivery
    }, 800);
  });
}

function followPath(path, callback) {
  if (!path.length) return callback();

  const step = path.shift();
  const dx = step.x - window.robot.x;
  const dy = step.y - window.robot.y;

  let desiredDirection = null;
  if (dx === 1) desiredDirection = "E";
  else if (dx === -1) desiredDirection = "W";
  else if (dy === 1) desiredDirection = "S";
  else if (dy === -1) desiredDirection = "N";

  if (!desiredDirection) {
    logMessage("⚠️ Invalid step in path. Skipping.");
    return setTimeout(() => followPath(path, callback), 500);
  }

  const scheduleNextStep = () => {
    // 🔋 Battery check
    if (window.robot.battery < 15) {
      commandQueue.push(() => {
        logMessage("🔋 Auto-recharge triggered (battery < 15%)");
        window.robot.recharge();
        logTelemetry("auto_recharge");
      });
    }

    // 🚶 Movement
    commandQueue.push(() => {
      const moved = window.robot.moveForward();
      logTelemetry("move_forward", moved);
    });

    // 🔁 Next recursive call
    setTimeout(() => followPath(path, callback), 500);
  };

  // 🧭 Only turn if not already facing the correct direction
  if (window.robot.direction !== desiredDirection) {
    commandQueue.push(() => {
      const dirs = ["N", "E", "S", "W"];
      while (window.robot.direction !== desiredDirection) {
        window.robot.turnRight();
        logTelemetry("auto_turn_right");
        window.robot.direction = dirs[(dirs.indexOf(window.robot.direction) + 1) % 4];
      }
    });

    setTimeout(scheduleNextStep, 300);
  } else {
    scheduleNextStep();
  }
}

function turnTo(dir) {
  while (window.robot.direction !== dir) {
    turnRight();
  }
}

function setSafeDeliveryGoal(building, hubPosition, orderId) {
  const target = findClosestNavigable(building.gridCoords, window.mapGrid);

  if (!target) {
    logMessage(`❌ No navigable tile found near '${building.name}'`);
    return;
  }

  if (pathExists(hubPosition, target, window.mapGrid)) {
    setGoal(target.x, target.y, orderId);
  } else {
    // Try nearby fallback options
    const fallback = findClosestReachableTile(target, hubPosition, window.mapGrid);
    if (fallback) {
      logMessage(`⚠️ Path blocked to '${building.name}'. Fallback delivery set near (${fallback.x}, ${fallback.y})`);
      setGoal(fallback.x, fallback.y, orderId);
    } else {
      logMessage(`❌ '${building.name}' is completely unreachable from hub.`);
    }
  }
}

function deliver(orderId) {
  commandQueue.push(() => {
    const success = window.robot.deliver(orderId);
    logTelemetry(`deliver:${orderId}`, success);
  });
}

function injectObstacle(x, y) {
  obstacles.push({ x, y });
  logMessage(`🧱 Obstacle injected at (${x}, ${y})`);
}

function loadOrdersFromJSON(jsonData) {
  try {
    const orders = JSON.parse(jsonData);
    for (let order of orders) {
      setGoal(order.x, order.y, order.orderId);
    }
    logMessage(`📦 Loaded ${orders.length} orders.`);
  } catch (e) {
    logMessage(`❌ Failed to parse orders JSON`);
  }
}
function setGoal(x, y, orderId) {
  // Prevent duplicate entries (optional, but helpful)
  const alreadyExists = deliveryGoals.some(g => g.x === x && g.y === y && g.orderId === orderId);
  if (alreadyExists) {
    console.warn(`⚠️ Goal already exists for ${orderId} at (${x}, ${y})`);
    return;
  }

  // Add goal to delivery goals
  deliveryGoals.push({ x, y, orderId, delivered: false });

  // Preserve existing tile data
  const existingTile = mapGrid[y][x] || { type: "empty", navigable: false };

  // Update type to 'goal', retain navigability
  mapGrid[y][x] = {
    ...existingTile,
    type: "goal",
    id: orderId,
    navigable: true  // ✅ Always mark goals as walkable
  };

  // Add to auto queue for pathing
  deliveryQueue.push({ x, y, orderId });

  logMessage(`🎯 Goal '${orderId}' set at (${x}, ${y})`);
}
window.setGoal = setGoal;

function loadMockData() {
  setGoal(4, 2, "Z-101");
  setGoal(7, 5, "Z-102");
  setGoal(2, 7, "Z-103");

  injectObstacle(3, 3);
  injectObstacle(6, 4);
  injectObstacle(5, 6);
}
