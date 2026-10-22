"use strict";

// Keep this script's variables inside its own function.
// This avoids naming conflicts with other scripts.
(async function loadCampusLayers() {
  // Each key matches properties.layer in our exported GeoJSON.
  const categories = {
    walkways: { label: "Walkways", color: "#15803d" },
    buildings: { label: "Buildings", color: "#2563eb" },
    delivery: { label: "Delivery points", color: "#c2410c" },
    restricted: { label: "Restrictions", color: "#dc2626" }
  };

  const statusMessage = document.getElementById("gis-status");
  const legend = document.getElementById("gis-key");

  // Stop with a useful console message if the HTML is incomplete.
  if (!statusMessage || !legend) {
    console.error("The page needs elements named gis-status and gis-key.");
    return;
  }

  try {
    // campusMap must already have been created by the HTML page.
    if (typeof campusMap === "undefined") {
      throw new Error("Create campusMap before loading campus-layers.js.");
    }

    const layerGroups = {};
    const overlayChoices = {};
    const counts = {};

    // Create an independent layer for each category.
    for (const [key, category] of Object.entries(categories)) {
      counts[key] = 0;

      const group = L.geoJSON(null, {
        // Style lines and polygon outlines.
        style: {
          color: category.color,
          weight: 4,
          fillColor: category.color,
          fillOpacity: 0.25
        },

        // Draw point features as circles instead of standard map pins.
        pointToLayer: function (feature, location) {
          return L.circleMarker(location, {
            radius: 7,
            color: category.color,
            fillColor: category.color,
            fillOpacity: 1
          });
        },

        // Attach a popup containing the feature's name.
        onEachFeature: function (feature, drawnLayer) {
          const label = document.createElement("span");

          // textContent treats the supplied name as plain text.
          label.textContent = feature.properties?.name || category.label;
          drawnLayer.bindPopup(label);
        }
      });

      // Initially show this category on the existing map.
      group.addTo(campusMap);

      // Save the layer for loading features and creating its checkbox.
      layerGroups[key] = group;
      overlayChoices[category.label] = group;

      // Use the same category settings to build the color key.
      const item = document.createElement("li");
      const swatch = document.createElement("span");

      swatch.textContent = "■ ";
      swatch.style.color = category.color;
      swatch.setAttribute("aria-hidden", "true");

      item.append(swatch, document.createTextNode(category.label));
      legend.append(item);
    }

    // Leaflet creates the category checkboxes.
    L.control.layers(null, overlayChoices, {
      collapsed: false
    }).addTo(campusMap);

    // Read our export without modifying its contents.
    const response = await fetch("./campus-layers.geojson");

    if (!response.ok) {
      throw new Error("Data request returned HTTP " + response.status);
    }

    const data = await response.json();

    // Check the expected document structure before using it.
    if (
      data.type !== "FeatureCollection" ||
      !Array.isArray(data.features)
    ) {
      throw new Error("Expected a GeoJSON FeatureCollection.");
    }

    // Assign every recognized feature to its matching category.
    for (const feature of data.features) {
      const key = feature.properties?.layer;

      if (Object.hasOwn(layerGroups, key)) {
        layerGroups[key].addData(feature);
        counts[key] += 1;
      }
    }

    // Display actual counts rather than assuming data is available.
    statusMessage.textContent = Object.entries(categories)
      .map(([key, category]) => category.label + ": " + counts[key])
      .join(" | ");

    const missing = Object.keys(categories)
      .filter(key => counts[key] === 0)
      .map(key => categories[key].label);

    if (missing.length > 0) {
      statusMessage.textContent +=
        ". No supplied features for: " + missing.join(", ") + ".";
    }
  } catch (error) {
    statusMessage.textContent = "Layer loading failed: " + error.message;
    console.error(error);
  }
})();