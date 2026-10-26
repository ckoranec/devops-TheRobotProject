"use strict";

// Pure functions shared by the canvas renderer and cross-language verification.
// effective_weight is calculated by Python at the snapshot time; the browser
// does not independently age a snapshot and silently disagree with its backend.
(function (root) {
  function distanceMeters(lat1, lon1, lat2, lon2) {
    const x = (lon2 - lon1) * 111320 * Math.cos((lat1 + lat2) / 2 * Math.PI / 180);
    const y = (lat2 - lat1) * 111320;
    return Math.hypot(x, y);
  }
  function densityAt(lat, lon, points) {
    let remaining = 1;
    for (const point of points) {
      const distance = distanceMeters(lat, lon, point.lat, point.lon);
      const kernel = Math.max(0, 1 - distance / point.radius_m) ** 2;
      remaining *= 1 - point.effective_weight * kernel;
    }
    return Math.min(1, Math.max(0, 1 - remaining));
  }
  root.DaveHeatField = {distanceMeters, densityAt};
  if (typeof module !== "undefined") module.exports = root.DaveHeatField;
})(globalThis);
