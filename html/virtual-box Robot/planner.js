function generateRobotPlan(hubPos, deliveryPoints, mapGrid, initialDirection = "E") {
    const ordered = optimizeDeliveryOrder(hubPos, deliveryPoints);
    const fullPlan = [];
    let currentPos = hubPos;
    let currentDir = initialDirection;
  
    for (const point of ordered) {
      const path = findPath(currentPos, point, mapGrid);
      if (!path.length) {
        console.warn(`⚠️ No path from (${currentPos.x}, ${currentPos.y}) to (${point.x}, ${point.y})`);
        continue;
      }
      const actions = pathToActions(path, currentDir);
      currentDir = actions.finalDirection;
      fullPlan.push(...actions.steps);
      fullPlan.push({ action: "deliver", orderId: point.name });
      currentPos = { x: point.x, y: point.y };
    }
  
    return fullPlan;
  }
  
  function optimizeDeliveryOrder(start, points) {
    const remaining = [...points];
    const ordered = [];
    let current = start;
  
    while (remaining.length) {
      let closestIdx = 0;
      let minDist = Infinity;
      for (let i = 0; i < remaining.length; i++) {
        const dist = Math.abs(current.x - remaining[i].x) + Math.abs(current.y - remaining[i].y);
        if (dist < minDist) {
          minDist = dist;
          closestIdx = i;
        }
      }
      const [next] = remaining.splice(closestIdx, 1);
      ordered.push(next);
      current = { x: next.x, y: next.y };
    }
    return ordered;
  }
  
  function pathToActions(path, startDir) {
    let actions = [];
    let currentDir = startDir;
  
    for (let i = 1; i < path.length; i++) {
      const dx = path[i].x - path[i - 1].x;
      const dy = path[i].y - path[i - 1].y;
      const targetDir = directionFromDelta(dx, dy);
  
      if (currentDir !== targetDir) {
        actions.push({ action: "turn", direction: targetDir });
        currentDir = targetDir;
      }
  
      actions.push({ action: "move" });
    }
  
    return { steps: actions, finalDirection: currentDir };
  }
  
  function directionFromDelta(dx, dy) {
    if (dx === 1 && dy === 0) return "E";
    if (dx === -1 && dy === 0) return "W";
    if (dx === 0 && dy === 1) return "S";
    if (dx === 0 && dy === -1) return "N";
    throw new Error(`Unsupported direction delta: dx=${dx}, dy=${dy}`);
  }
  
  // Required externally
  window.generateRobotPlan = generateRobotPlan;