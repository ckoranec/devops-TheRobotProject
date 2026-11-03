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
 

  // Stop with a useful console message if the HTML is incomplete.
  if (!statusMessage ) {
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

     
    }

    // Leaflet creates the category checkboxes.
      L.control.layers(null, overlayChoices, {
        collapsed: false
      }).addTo(campusMap);

      // Tint each checkbox with its category color.
      const colorByLabel = {};
      for (const category of Object.values(categories)) {
        colorByLabel[category.label] = category.color;
      }

      document
        .querySelectorAll(".leaflet-control-layers-overlays label")
        .forEach(function (label) {
          const color = colorByLabel[label.textContent.trim()];
          if (color) {
            label.querySelector("input").style.accentColor = color;
          }
        });

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
// 2026-11-03 - Identify every existing restriction without changing backend code.
(async function showRestrictionDirectory() { // Run this independent frontend addition.
  "use strict"; // Catch accidental undeclared variables.
  const panel = document.createElement("section"); // Create a directory below the map.
  document.getElementById("gis-status").after(panel); // Position the directory after the counts.

  try { // Display an explanation if loading fails.
    const response = await fetch("./campus-layers.geojson", { cache: "no-store" }); // Load current map features.
    if (!response.ok) throw new Error("HTTP " + response.status); // Reject failed downloads.
    const data = await response.json(); // Read the GeoJSON document.
    const restrictions = data.features.filter(feature => feature.properties?.layer === "restricted"); // Select actual restriction features.
    const heading = document.createElement("h2"); // Create a visible heading.
    heading.textContent = "Mapped restrictions: " + restrictions.length; // Show the actual count.
    panel.append(heading); // Display the heading.
    const note = document.createElement("p"); // Explain the numbered markers.
    note.textContent = "Each number identifies one mapped access feature. Markers locate feature centers, not exact physical barriers. Use the list when markers overlap."; // Describe the display accurately.
    panel.append(note); // Show the explanation.
    const showAll = document.createElement("button"); // Create a button for the full restriction view.
    showAll.type = "button"; // Prevent form submission.
    showAll.textContent = "Show all " + restrictions.length + " restrictions"; // Label the button.
    panel.append(showAll); // Place the button above the list.
    const list = document.createElement("ol"); // Create one numbered row per restriction.
    panel.append(list); // Display the directory.
    const markers = L.featureGroup().addTo(campusMap); // Display numbered markers independently of existing layers.
    const allBounds = L.latLngBounds([]); // Collect the extent of all restriction features.
    let highlight = null; // Track the selected feature's temporary highlight.

    restrictions.forEach(function (feature, index) { // Process every restriction exactly once.
      const number = index + 1; // Start numbering at one.
      const properties = feature.properties || {}; // Read the existing feature details.
      const shape = L.geoJSON(feature, { style: { color: "#dc2626", weight: 8 } }); // Prepare a highlight of the real geometry.
      const bounds = shape.getBounds(); // Find the feature's geographic extent.
      if (!bounds.isValid()) throw new Error("Invalid geometry for restriction " + number); // Report unusable geometry.
      allBounds.extend(bounds); // Include the complete feature in the full view.
      const tags = Object.entries(properties.access_tags || {}).map(([key, value]) => key + "=" + value).join("; "); // Display the supplied access tags.
      const description = (properties.name || "Unnamed feature") + " | OSM " + (properties.osm_id || "unknown") + " | " + (tags || "No access details supplied"); // Identify the feature.
      const badge = document.createElement("span"); // Create the marker's numbered badge.
      badge.textContent = String(number); // Write its number safely.
      badge.style.cssText = "display:block;width:28px;height:28px;line-height:28px;background:#b91c1c;color:white;border:2px solid white;border-radius:50%;text-align:center;font-weight:bold;box-shadow:0 1px 4px #333;"; // Make the marker readable.
      const icon = L.divIcon({ html: badge, className: "", iconSize: [32, 32], iconAnchor: [16, 16] }); // Create a Leaflet icon.
      const marker = L.marker(bounds.getCenter(), { icon: icon, title: number + ": " + description }).addTo(markers); // Mark the feature's bounding-box center.
      const popup = document.createElement("span"); // Create safe popup content.
      popup.textContent = number + ": " + description; // Include the number, identity, and tags.
      marker.bindPopup(popup); // Attach the details to the marker.

      function focus() { // Select this restriction from either the map or list.
        if (highlight) campusMap.removeLayer(highlight); // Clear the previous temporary highlight.
        highlight = shape.addTo(campusMap); // Display this feature's real shape.
        highlight.bringToFront(); // Keep the selected shape visible.
        campusMap.fitBounds(bounds, { padding: [45, 45], maxZoom: 19 }); // Zoom to the selected restriction.
        marker.openPopup(); // Show its identifying details.
      } // Finish the selection action.

      marker.on("click", focus); // Enable selection through the numbered marker.
      const item = document.createElement("li"); // Create this restriction's numbered row.
      const button = document.createElement("button"); // Create its individual selection button.
      button.type = "button"; // Prevent form submission.
      button.textContent = description; // Show the identifying details.
      button.style.cssText = "margin:4px 0;text-align:left;white-space:normal;"; // Keep the list readable.
      button.addEventListener("click", focus); // Connect the list entry to its map feature.
      item.append(button); // Put the button inside the row.
      list.append(item); // Add the row to the directory.
    }); // Finish creating all restriction entries.

    showAll.disabled = restrictions.length === 0; // Disable fitting when no features exist.
    showAll.addEventListener("click", function () { // Change the view when explicitly requested.
      campusMap.fitBounds(allBounds, { padding: [45, 45], maxZoom: 17 }); // Fit all restriction geometries inside the map.
    }); // Finish the show-all action.
  } catch (error) { // Report errors visibly below the map.
    const message = document.createElement("p"); // Create an error message.
    message.textContent = "Restriction directory failed: " + error.message; // Explain the failure.
    panel.append(message); // Display the message.
    console.error(error); // Preserve technical details.
  } // Finish error handling.
})(); // Finish and execute the complete addition.
