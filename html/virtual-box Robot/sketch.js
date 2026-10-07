
let gridSizeX = 10;
let gridSizeY = 10;
let tileSize = 25;

let truckEmptyImage;
let truckCargoImage;
let roadblockImage;
let noPackageImage;
let deliveredImage;
let HubImg;

let mapGrid = [];
let overlayPaths = [];
deliveryGoals = [];
let metaBounds = [];


function preload() {
  window.truckEmptyImage = loadImage("Empty_Truck.png",
    () => console.log("✅ Empty_Truck.png loaded"),
    () => console.error("❌ Failed to load Empty_Truck.png")
  );

  window.truckCargoImage = loadImage("Truck_with_cargo.png",
    () => console.log("✅ Truck_with_cargo.png loaded"),
    () => console.error("❌ Failed to load Truck_with_cargo.png")
  );

  roadblockImage = loadImage("RoadBlock.png");
  noPackageImage = loadImage("NoPackage.png");
  deliveredImage = loadImage("Delivered.png");
 

  HubImg = loadImage("TheHub.png");
}

function isNavigable(type) {
  const base = [
    "road", "sidewalk", "path", "cycleway", "ramp", "crossing", "kerb"
  ];

  if (routingStrategy === "block") {
    return base.includes(type);
  }

  if (routingStrategy === "prefer") {
    return base.includes(type) || type === "stairs"; // stairs are allowed, but deprioritized
  }

  if (routingStrategy === "allow") {
    return base.includes(type) || type === "stairs";
  }

  return false;
}

function getColorForType(type) {
  switch (type) {
    case "road": return "#888";
    case "sidewalk": return "#eeee88";
    case "path": return "#c6c6ff";
    case "cycleway": return "#a0dfff";
    case "stairs": return "#ff00ff";
    case "ramp": return "#00dddd";
    case "crossing": return "#fff200";
    case "kerb": return "#bbbbbb";
    case "barrier": return "#ff4444";
    case "entrance": return "#4444ff";
    case "building": return "#333333";
    case "man_made_building": return "#333333";
    case "leisure_park": return "#88cc88";
    case "landuse_grass": return "#b6e3a1";
    case "landuse_forest": return "#6eab6e";
    case "landuse_residential": return "#e0e0e0";
    case "natural_forest":
    case "natural_wood": return "#7aa35c";
    case "natural_water": return "#99ccff";
    case "surface_gravel": return "#aaa";
    case "surface_dirt": return "#c2b280";
    case "surface_asphalt": return "#555555";
    case "surface_paved": return "#777777";
    case "tourism_museum": return "#ffd700";
    case "amenity_bench": return "#996600";
    case "natural": return "#99cc99";
    case "landuse": return "#bbbbbb";
    case "other": return "#bbbbbb";
    default: return "#f0f0f0";
  }
}

function setup() {
  if (window.mapGrid && window.mapGrid.length > 0) {
    mapGrid = window.mapGrid;
    gridSizeY = mapGrid.length;
    gridSizeX = mapGrid[0].length;
  } else {
    gridSizeY = 10;
    gridSizeX = 10;
    mapGrid = Array.from({ length: gridSizeY }, () =>
      Array.from({ length: gridSizeX }, () => ({
        type: "road",
        navigable: true,
        visual: null
      }))
    );
  }

  const canvas = createCanvas(gridSizeX * tileSize, gridSizeY * tileSize);
  canvas.parent('canvas-container');

  window.robot = new Robot(0, 0, "E");  // ✅ Makes it global
robot = window.robot;
  frameRate(1);
}

function draw() {
  background(230);
  drawGrid();
  highlightNavigableTiles();
  drawSidewalkOverlay();
  drawObstacles();
  drawGoals();
  drawGoalTilesFromMap();

  if (window.robot) {
    window.robot.display();
  }

  if (commandQueue.length > 0) {
    const nextCommand = commandQueue.shift();
    nextCommand();
  }
  for (let y = 0; y < mapGrid.length; y++) {
    for (let x = 0; x < mapGrid[0].length; x++) {
      const tile = mapGrid[y][x];
      if (tile && tile.type === "hub") {
        image(HubImg, x * tileSize, y * tileSize, tileSize, tileSize);
      }
    }
  }
}

function highlightNavigableTiles() {
  if (!showNavigableOverlay) return;

  noStroke();
  fill(0, 255, 0, 80);

  for (let y = 0; y < gridSizeY; y++) {
    for (let x = 0; x < gridSizeX; x++) {
      const tile = mapGrid[y][x];
      if (
        tile?.navigable &&
        !(window.routingStrategy === "block" && tile.type === "stairs")
      ) {
        rect(x * tileSize, y * tileSize, tileSize, tileSize);
      }
    }
  }
}

function drawSidewalkOverlay() {
  if (!overlayPaths || overlayPaths.length === 0) return;
  stroke(0, 255, 0, 150);
  strokeWeight(2);
  noFill();
  for (let path of overlayPaths) {
    beginShape();
    for (let coord of path) {
      const gx = (coord[0] - metaBounds[0]) / (metaBounds[2] - metaBounds[0]) * gridSizeX * tileSize;
      const gy = (metaBounds[3] - coord[1]) / (metaBounds[3] - metaBounds[1]) * gridSizeY * tileSize;
      vertex(gx, gy);
    }
    endShape();
  }
}

function drawGrid() {
  stroke(105);
  for (let y = 0; y < gridSizeY; y++) {
    for (let x = 0; x < gridSizeX; x++) {
      const tile = mapGrid[y][x] || { type: "empty" };
      fill(getColorForType(tile.type));
      rect(x * tileSize, y * tileSize, tileSize, tileSize);
    }
  }
}

function drawObstacles() {
  for (const obs of obstacles) {
    if (roadblockImage) {
      image(roadblockImage, obs.x * tileSize, obs.y * tileSize, tileSize, tileSize);
    } else {
      fill(50);
      rect(obs.x * tileSize, obs.y * tileSize, tileSize, tileSize);
    }
  }
}
function pathExists(start, end, mapGrid) {
  const queue = [start];
  const visited = new Set([`${start.x},${start.y}`]);
  const directions = [[0,1],[1,0],[0,-1],[-1,0]];

  while (queue.length > 0) {
    const { x, y } = queue.shift();
    if (x === end.x && y === end.y) return true;

    for (const [dx, dy] of directions) {
      const nx = x + dx;
      const ny = y + dy;
      const key = `${nx},${ny}`;

      if (
        nx >= 0 && ny >= 0 &&
        ny < mapGrid.length &&
        nx < mapGrid[0].length &&
        !visited.has(key) &&
        mapGrid[ny][nx]?.navigable
      ) {
        visited.add(key);
        queue.push({ x: nx, y: ny });
      }
    }
  }

  return false;
}

function findClosestReachableTile(origin, from, mapGrid, maxRadius = 10) {
  const directions = [
    [0,1],[1,0],[0,-1],[-1,0],
    [1,1],[-1,1],[1,-1],[-1,-1]
  ];

  for (let radius = 1; radius <= maxRadius; radius++) {
    for (let dx = -radius; dx <= radius; dx++) {
      for (let dy = -radius; dy <= radius; dy++) {
        const x = origin.x + dx;
        const y = origin.y + dy;

        if (
          y >= 0 && y < mapGrid.length &&
          x >= 0 && x < mapGrid[0].length &&
          mapGrid[y][x]?.navigable
        ) {
          // 🪜 Option A: skip stairs if strategy is block
          if (routingStrategy === "block" && mapGrid[y][x].type === "stairs") {
            continue;
          }
        
          // ✅ Only run path check after tile is allowed
          if (pathExists(from, { x, y }, mapGrid)) {
            return { x, y };
          }
        }
      }
    }
  }

  return null;
}

function drawGoals() {
  textAlign(CENTER, CENTER);
  textSize(12);
  for (let goal of deliveryGoals) {
    let img = goal.delivered ? deliveredImage : noPackageImage;
    if (img) {
      image(img, goal.x * tileSize, goal.y * tileSize, tileSize, tileSize);
    } else {
      fill(goal.delivered ? color(0, 200, 255) : color(0, 200, 0));
      rect(goal.x * tileSize + 5, goal.y * tileSize + 5, 40, 40);
    }

    fill(0);
    text(goal.orderId, goal.x * tileSize + tileSize / 2, goal.y * tileSize + tileSize / 2);
  }
}
function drawGoalTilesFromMap() {
  textAlign(CENTER, CENTER);
  textSize(12);

  for (let y = 0; y < mapGrid.length; y++) {
    for (let x = 0; x < mapGrid[0].length; x++) {
      const tile = mapGrid[y][x];
      if (tile?.type === "goal") {
        // Draw goal image or fallback
        if (noPackageImage) {
          image(noPackageImage, x * tileSize, y * tileSize, tileSize, tileSize);
        } else {
          fill(255, 215, 0);
          rect(x * tileSize + 5, y * tileSize + 5, 15, 15);
        }

        // Draw goal label above the icon
        if (tile.id) {
          const labelX = x * tileSize + tileSize / 2;
          const labelY = y * tileSize - 4;
          const labelText = tile.id;

          textAlign(CENTER, BOTTOM);
          textSize(12);
          stroke(255);
          strokeWeight(3);
          fill(0);
          text(labelText, labelX, labelY);
          noStroke();
        }
      }
    }
  }
}
