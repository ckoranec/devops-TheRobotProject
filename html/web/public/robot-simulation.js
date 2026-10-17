// MAX BYTE ROBOT PROJECT
// GIS Phase 4 - Interactive robot simulation controls.
// This is a demonstration, not a live robot connection.

"use strict";

(function () {
    const UPDATE_INTERVAL_MS = 10000;
    const SIMULATED_SPEED_MPH = 3;
    const MAX_SPEED_MPH = 15;
    const metersPerSecond = SIMULATED_SPEED_MPH * 0.44704;

    if (typeof L === "undefined" || typeof campusMap === "undefined") {
        console.error("Robot simulation: Leaflet map unavailable.");
        return;
    }

    const mapElement = document.getElementById("gmu-campus-map");
    const panel = document.createElement("div");

    panel.id = "robot-control-panel";
    panel.style.cssText =
        "background:white;color:#222;padding:20px;margin:15px 0;" +
        "border-radius:12px;box-shadow:0 2px 8px #0002;";

    mapElement.insertAdjacentElement("afterend", panel);

    panel.innerHTML = `
        <h3>MAX Byte Robot - Control Center</h3>
        <p><strong>Simulation controls</strong></p>
        <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:15px;">
            <button id="robot-start" type="button">Start</button>
            <button id="robot-pause" type="button">Pause</button>
            <button id="robot-reset" type="button">Reset</button>
        </div>
        <label for="robot-direction">Route direction:</label>
        <select id="robot-direction">
            <option value="forward">Campus out-and-back loop</option>
            <option value="reverse">Reverse campus loop</option>
        </select>
        <div id="robot-simulation-status" aria-live="polite">
            Loading simulated route...
        </div>
    `;

    const status = document.getElementById("robot-simulation-status");
    const startButton = document.getElementById("robot-start");
    const pauseButton = document.getElementById("robot-pause");
    const resetButton = document.getElementById("robot-reset");
    const directionSelect = document.getElementById("robot-direction");

    fetch("data/gmu_map.json")
        .then(response => {
            if (!response.ok) {
                throw new Error("GIS HTTP " + response.status);
            }
            return response.json();
        })
        .then(data => {
            const road = (data.elements || []).find(element =>
                element.type === "way" &&
                element.tags?.highway === "service" &&
                Array.isArray(element.geometry) &&
                element.geometry.length >= 2
            );

            if (!road) {
                throw new Error("No service-road route available.");
            }

            // MAX_BYTE_ROUTE_POLISH_V11: mapped out-and-back trip, no invented geometry.
            const lane = road.geometry.map(point => [point.lat, point.lon]);
            const originalRoute = lane.concat(lane.slice(0,-1).reverse());

            const radians = degrees => degrees * Math.PI / 180;

            function distanceMeters(a, b) {
                const R = 6371000;
                const dLat = radians(b[0] - a[0]);
                const dLon = radians(b[1] - a[1]);

                const value =
                    Math.sin(dLat / 2) ** 2 +
                    Math.cos(radians(a[0])) *
                    Math.cos(radians(b[0])) *
                    Math.sin(dLon / 2) ** 2;

                return 2 * R * Math.atan2(
                    Math.sqrt(value),
                    Math.sqrt(1 - value)
                );
            }

            // MAX_BYTE_CUTE_MASCOT_V1
            // Friendly inline SVG mascot with animated floating effect.
            const robotIcon = L.divIcon({
                className: "max-byte-cute-marker",
                html: `<div class="mb-polished" role="img" aria-label="MAX Byte rolling delivery robot"><div class="mb-polished-antenna"></div><div class="mb-polished-ear left"></div><div class="mb-polished-ear right"></div><div class="mb-polished-head"><div class="mb-polished-face"><i></i><i></i></div></div><div class="mb-polished-body"></div><div class="mb-polished-ball"></div></div>`,
                iconSize: [52, 52],
                iconAnchor: [26, 26],
                popupAnchor: [0, -65]
            });

            const base = L.circleMarker(originalRoute[0], {
                radius: 12,
                color: "#1d4ed8",
                fillColor: "#fff",
                fillOpacity: 1
            }).addTo(campusMap).bindPopup("MAX Byte BASE");

            const destination = L.circleMarker(
                originalRoute[originalRoute.length - 1],
                {
                    radius: 12,
                    color: "#15803d",
                    fillColor: "#22c55e",
                    fillOpacity: 1
                }
            ).addTo(campusMap).bindPopup("Return to MAX Byte base");

            const robot = L.marker(originalRoute[0], {
                icon: robotIcon
            }).addTo(campusMap);

            window.maxByteDeliveryRobot = robot;

            const routeLine = L.polyline(originalRoute, {
                color: "#2563eb",
                weight: 5,
                dashArray: "8,8"
            }).addTo(campusMap);

            let route = originalRoute;
            let segments = [];
            let totalMeters = 0;
            let traveledMeters = 0;
            let state = "Ready";

            function prepareRoute() {
                route = directionSelect.value === "reverse"
                    ? [...originalRoute].reverse()
                    : [...originalRoute];

                segments = [];
                for (let i = 1; i < route.length; i++) {
                    segments.push(
                        distanceMeters(route[i - 1], route[i])
                    );
                }

                totalMeters = segments.reduce(
                    (sum, value) => sum + value, 0
                );

                traveledMeters = 0;
                robot.setLatLng(route[0]);
            }

            function positionAtDistance(distance) {
                let accumulated = 0;

                for (let i = 0; i < segments.length; i++) {
                    const segment = segments[i];

                    if (distance <= accumulated + segment) {
                        const fraction = segment === 0
                            ? 1
                            : (distance - accumulated) / segment;

                        return [
                            route[i][0] +
                            (route[i + 1][0] - route[i][0]) * fraction,
                            route[i][1] +
                            (route[i + 1][1] - route[i][1]) * fraction
                        ];
                    }

                    accumulated += segment;
                }

                return route[route.length - 1];
            }

            function updateStatus() {
                const remaining = Math.max(
                    0, totalMeters - traveledMeters
                );

                const progress = totalMeters > 0
                    ? traveledMeters / totalMeters * 100
                    : 100;

                const eta = Math.ceil(
                    remaining / metersPerSecond / 60
                );

                status.innerHTML = `
                    <p><strong>Status:</strong> ${state}</p>
                    <p><strong>Speed:</strong> ${SIMULATED_SPEED_MPH} mph
                    (configured maximum ${MAX_SPEED_MPH} mph)</p>
                    <p><strong>Progress:</strong> ${progress.toFixed(1)}%</p>
                    <p><strong>Remaining:</strong> ${remaining.toFixed(0)} meters</p>
                    <p><strong>ETA:</strong> ${eta} minute(s)</p>
                    <p><strong>Movement:</strong> Continuous animation</p>
                `;
            }


            // Smooth movement using the browser's animation frame clock.
            // Elapsed time determines distance, not frame count.
            let animationFrame = null;
            let lastFrameTime = null;
            let lastStatusUpdate = 0;

            function animateRobot(timestamp) {
                if (state !== "En route") return;

                if (lastFrameTime === null) {
                    lastFrameTime = timestamp;
                }

                // Limit large jumps after background-tab suspension.
                const elapsedSeconds = Math.min(
                    Math.max(0, (timestamp - lastFrameTime) / 1000),
                    0.1
                );

                lastFrameTime = timestamp;

                traveledMeters = Math.min(
                    totalMeters,
                    traveledMeters + metersPerSecond * elapsedSeconds
                );

                robot.setLatLng(
                    positionAtDistance(traveledMeters)
                );

                // MAX_BYTE_STATUS_THROTTLE_V1
                // Keep robot movement at full animation-frame speed.
                // Refresh the text panel only four times per second.
                if (timestamp - lastStatusUpdate >= 250) {
                    updateStatus();
                    lastStatusUpdate = timestamp;
                }

                if (traveledMeters >= totalMeters) {
                    state = "Delivered";
                    animationFrame = null;
                    lastFrameTime = null;
                    updateStatus();
                    return;
                }

                animationFrame = requestAnimationFrame(animateRobot);
            }

            function stopAnimation() {
                if (animationFrame !== null) {
                    cancelAnimationFrame(animationFrame);
                    animationFrame = null;
                }
                lastFrameTime = null;
            }

            startButton.addEventListener("click", () => {
                if (state === "En route") return;

                if (state === "Delivered") {
                    prepareRoute();
                }

                state = "En route";
                lastFrameTime = performance.now();
                animationFrame = requestAnimationFrame(animateRobot);
                updateStatus();
            });

            pauseButton.addEventListener("click", () => {
                if (state !== "En route") return;

                stopAnimation();
                state = "Paused";
                updateStatus();
            });

            resetButton.addEventListener("click", () => {
                stopAnimation();
                prepareRoute();
                state = "Ready";
                updateStatus();
            });

            directionSelect.addEventListener("change", () => {
                stopAnimation();
                prepareRoute();
                state = "Ready";
                updateStatus();
            });

            prepareRoute();
            updateStatus();

            campusMap.fitBounds(routeLine.getBounds(), {
                padding: [28, 28],
                maxZoom: 16
            });
        })
        .catch(error => {
            status.textContent =
                "Robot simulation error: " + error.message;
            console.error(error);
        });
})();
