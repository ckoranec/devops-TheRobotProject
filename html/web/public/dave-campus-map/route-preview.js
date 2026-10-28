"use strict"; // Catch accidental undeclared variables.
(async function displayReviewedPreview() { // Keep this script's state private.
  const status = document.getElementById("route-status"); // Reuse the team's existing status element.
  if (!status) return; // Stop safely if this HTML contract is missing.
  const root = new URL("../../../../", location.href); // Serve from the repository root for dependency checks.
  const checked = new Map(); // Reuse downloads within this one freshness check.
  async function bytes(path) { // Read exact bytes so formatting changes also invalidate artifacts.
    if (!/^[A-Za-z0-9_./-]+$/.test(path) || path.split("/").includes("..") || path.startsWith("/")) { // Reject unsafe manifest paths.
      throw new Error("Unsafe dependency path in manifest"); // Never fetch arbitrary origins or parent paths.
    } // End path validation.
    if (!checked.has(path)) { // Avoid fetching the same file twice.
      const response = await fetch(new URL(path, root), { cache: "no-store" }); // Cache bypass alone is not a freshness guarantee.
      if (!response.ok) throw new Error(`Missing input/output: ${path} (${response.status})`); // Explain failed requests.
      checked.set(path, await response.arrayBuffer()); // Keep immutable response bytes for hash and JSON parsing.
    } // End first fetch.
    return checked.get(path); // Return the downloaded bytes.
  } // End byte reader.
  function decode(data) { // Convert only verified JSON bytes into JavaScript objects.
    return JSON.parse(new TextDecoder().decode(data)); // Use the browser's UTF-8 decoder.
  } // End decoder.
  try { // Make every failure visible beside the map.
    if (typeof campusMap === "undefined") throw new Error("Create campusMap before this script"); // Preserve the HTML contract.
    if (!globalThis.crypto?.subtle) throw new Error("Freshness check requires localhost or HTTPS"); // Avoid pretending an unavailable check passed.
    const folder = "html/web/public/dave-campus-map/"; // Match the checked-in folder layout.
    const manifest = decode(await bytes(folder + "preview-manifest.json")); // Read the last-published build marker.
    if (manifest.schema !== 1 || !Array.isArray(manifest.inputs) || !Array.isArray(manifest.outputs)) { // Validate the expected envelope.
      throw new Error("Unsupported preview manifest; rebuild"); // Do not interpret an unknown schema.
    } // End manifest validation.
    if (manifest.crowd_sources_enabled !== false) throw new Error("Rebuild with crowd sources disabled"); // Require explicit crowd-free provenance.
    for (const item of [...manifest.inputs, ...manifest.outputs]) { // Check map, backend, configuration and generated files.
      if (!/^[a-f0-9]{64}$/.test(item.sha256)) throw new Error("Invalid dependency fingerprint"); // Validate the expected digest shape.
      const hash = await crypto.subtle.digest("SHA-256", await bytes(item.path)); // Hash exact bytes in the browser.
      const hex = [...new Uint8Array(hash)].map(n => n.toString(16).padStart(2, "0")).join(""); // Convert the digest to the builder's hex format.
      if (hex !== item.sha256) throw new Error(`STALE preview: ${item.path}; rebuild`); // Hide the route until its dependencies match.
    } // End dependency verification.
    const route = decode(await bytes(folder + "route-preview.geojson")); // Use the same verified route bytes.
    const points = route.geometry?.coordinates; // Read the shaped path, not a straight address connector.
    const validPoint = p => ( // Validate one WGS84 longitude/latitude pair.
      Array.isArray(p) && p.length === 2 && // Require exactly one coordinate pair.
      p.every(Number.isFinite) && // Reject strings, NaN and infinity.
      Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90 // Enforce longitude/latitude bounds.
    ); // End the reusable position predicate.
    if ( // Validate the complete route before passing it to Leaflet.
      route.type !== "Feature" || // A collection is not this saved-route contract.
      route.geometry?.type !== "LineString" || // Do not interpret polygons as routes.
      !Array.isArray(points) || points.length < 2 || // Require a nonzero line shape.
      !points.every(validPoint) // Every coordinate must pass the same validation.
    ) { // Enter the failure branch if any required condition is missing.
      throw new Error("Invalid route geometry"); // Refuse malformed output.
    } // End route shape check.
    if (!Number.isFinite(route.properties?.length_m) || route.properties.length_m < 0) throw new Error("Invalid route distance"); // Reject missing/negative distance.
    const line = L.geoJSON(route, { style: { color: "#7c3aed", weight: 6, opacity: 0.9 } }); // Retain the familiar purple route.
    const group = L.featureGroup([line]); // Keep the route and endpoints switchable together.
    for (const [point, label] of [[points[0], "Snapped graph start"], [points.at(-1), "Snapped graph destination"]]) { // Label only the snapped routing nodes.
      const text = document.createElement("span"); // Use a DOM node for safe popup text.
      text.textContent = label; // Treat the label as text, not HTML.
      L.circleMarker([point[1], point[0]], { radius: 7, color: "#172b3a", fillColor: "#ffffff", fillOpacity: 1 }).bindPopup(text).addTo(group); // Leaflet expects latitude first.
    } // End endpoint markers.
    group.addTo(campusMap); // Draw only AFTER the freshness check succeeds.
    L.control.layers(null, { "Reviewed saved graph candidate": group }, { collapsed: false }).addTo(campusMap); // Preserve a route visibility checkbox.
    campusMap.fitBounds(group.getBounds(), { padding: [25, 25], maxZoom: 17 }); // Fit once, not on every pan/poll.
    status.textContent = `Current saved graph candidate: ${(route.properties.length_m / 1000).toFixed(2)} km; built ${manifest.generated_at}. Source: ${manifest.map}. Crowd sources: disabled. Not a closure-aware physical navigation approval.`; // Explain freshness and scope.
    const banner = [...document.querySelectorAll("p")].find(p => p.textContent.trim().startsWith("GIS source:")); // Find the old dated-source banner without changing Shek's HTML file.
    if (banner) banner.textContent = `GIS source: ${manifest.map}; supplemental inputs fingerprinted in preview-manifest.json. Restriction features represent access tags. Delivery points are planned targets; verify entrances and permissions.`; // Display the actual declared source.
  } catch (error) { // A stale or missing input must not look like a healthy saved route.
    status.textContent = "Preview unavailable/stale: " + error.message + ". Run build_preview.py --replace, then refresh."; // Give the teammate a recovery action.
    console.error(error); // Preserve technical detail for debugging.
  } // End error reporting.
})(); // Execute once when the existing HTML loads this script.
