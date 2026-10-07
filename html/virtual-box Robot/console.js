function logMessage(msg) {
    const log = document.getElementById("log");
    log.textContent += msg + "\n";
  }
  function runUserCode() {
    const code = document.getElementById("userCode").value;
  
    try {
      const sandbox = {
        moveForward,
        turnRight,
        scan,
        deliver,
        logMessage
      };
  
      const userFunc = new Function(...Object.keys(sandbox), code);
      userFunc(...Object.values(sandbox));
  
      logMessage("✅ User code executed.");
    } catch (err) {
      logMessage("❌ Error in user code: " + err.message);
    }
  }
  function resetRobot() {
    const dropdown = document.getElementById("buildingDropdown");
    const selectedName = dropdown?.value;
  
    const building = window.namedBuildings?.find(b => b.name === selectedName);
    if (!building) {
      logMessage("⚠️ No valid building selected — resetting to (0,0)");
      window.robot = new Robot(0, 0, "E");
    } else {
      const position = findClosestNavigable(building.gridCoords, window.mapGrid);
      if (position) {
        window.robot = new Robot(position.x, position.y, "E");
        logMessage(`🔄 Robot reset to ${selectedName} at (${position.x}, ${position.y})`);
      } else {
        window.robot = new Robot(0, 0, "E");
        logMessage(`⚠️ Could not find valid tile near ${selectedName} — reset to (0,0)`);
      }
    }
  
    // 🧹 Clear queues
    commandQueue = [];
    if (window.robotActionQueue) {
      window.robotActionQueue.length = 0;
    }
  
    // 🧼 Kill running loop
    if (window.activeRobotTimer) {
      clearTimeout(window.activeRobotTimer);
      window.activeRobotTimer = null;
    }
  
    updateBatteryDisplay();
  }
  
  function logToConsole(message) {
    const logEl = document.getElementById("log");
    logEl.textContent += message + "\n";
    logEl.scrollTop = logEl.scrollHeight;
  }

  