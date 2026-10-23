"use strict";

// Run an asynchronous function while keeping its variables private.
(async function displayDijkstraRoute() {
  const statusMessage = document.getElementById("route-status");

  // This element must exist in our HTML before displaying results.
  if (!statusMessage) {
    console.error("The HTML needs an element with id='route-status'.");
    return;
  }

  try {
    // The HTML must create campusMap before loading this script.
    if (typeof campusMap === "undefined") {
      throw new Error("Create campusMap before loading the route script.");
    }

    // Request the backend's exported route from this page's folder.
    // no-store avoids reusing a cached route when we refresh.
    const response = await fetch("./route-preview.geojson", {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error("Route request returned HTTP " + response.status);
    }

    // Convert the downloaded JSON text into a JavaScript object.
    const route = await response.json();

    // Confirm the backend exported one geographic line feature.
    if (
      route.type !== "Feature" ||
      route.geometry?.type !== "LineString"
    ) {
      throw new Error("Expected a GeoJSON LineString feature.");
    }

    const positions = route.geometry.coordinates;
    const meters = route.properties?.length_m;

    // Require at least two valid [longitude, latitude] positions.
    if (
      !Array.isArray(positions) ||
      positions.length < 2 ||
      !positions.every(point =>
        Array.isArray(point) &&
        point.length >= 2 &&
        Number.isFinite(point[0]) &&
        Number.isFinite(point[1]) &&
        Math.abs(point[0]) <= 180 &&
        Math.abs(point[1]) <= 90
      )
    ) {
      throw new Error("The route needs at least two valid positions.");
    }

    if (!Number.isFinite(meters) || meters < 0) {
      throw new Error("The route distance is missing or invalid.");
    }

    // Leaflet converts GeoJSON coordinates into its map positions.
    const routeLine = L.geoJSON(route, {
      style: {
        color: "#7c3aed",
        weight: 6,
        opacity: 0.9
      }
    });

    // Keep the line and both endpoint markers in one switchable group.
    const routeGroup = L.featureGroup([routeLine]);

    const first = positions[0];
    const last = positions[positions.length - 1];

    // Circle markers expect [latitude, longitude], so swap the values.
    L.circleMarker([first[1], first[0]], {
      radius: 8,
      color: "#172b3a",
      fillColor: "#ffffff",
      fillOpacity: 1
    }).bindPopup("Snapped route start").addTo(routeGroup);

    L.circleMarker([last[1], last[0]], {
      radius: 8,
      color: "#172b3a",
      fillColor: "#7c3aed",
      fillOpacity: 1
    }).bindPopup("Snapped route destination").addTo(routeGroup);

    routeGroup.addTo(campusMap);

    // Supply a checkbox that controls the route and its markers.
    L.control.layers(null, {
      "Dijkstra demonstration route": routeGroup
    }, {
      collapsed: false
    }).addTo(campusMap);

    // Frame the complete route with space around its edges.
    campusMap.fitBounds(routeGroup.getBounds(), {
      padding: [25, 25],
      maxZoom: 17
    });

    // Add a matching purple entry to our existing color key.
    const legend = document.getElementById("gis-key");

    if (legend) {
      const item = document.createElement("li");
      const swatch = document.createElement("span");

      swatch.textContent = "■ ";
      swatch.style.color = "#7c3aed";
      swatch.setAttribute("aria-hidden", "true");

      item.append(
        swatch,
        document.createTextNode("Dijkstra demonstration route")
      );

      legend.append(item);
    }

    // Convert the backend's meters into kilometers for the viewer.
    statusMessage.textContent =
      "Saved Dijkstra route: " +
      (meters / 1000).toFixed(2) +
      " km between snapped graph nodes. Demonstration only.";
  } catch (error) {
    statusMessage.textContent =
      "Route loading failed: " + error.message;

    console.error(error);
  }
})()