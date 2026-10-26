"use strict";

// A small Leaflet canvas layer, built here so no extra heat-map plugin is needed.
// It evaluates the same weighted field as Python at each 12-pixel grid midpoint.
// This is a sampled visual representation, not surveyed counts or exact boundaries.
const WeightedHeatLayer = L.Layer.extend({
  initialize: function () { this.points = []; },
  onAdd: function (map) {
    this.map = map;
    let pane = map.getPane("weightedHeatPane");
    if (!pane) { pane = map.createPane("weightedHeatPane"); pane.style.zIndex = 350; }
    this.canvas = L.DomUtil.create("canvas", "weighted-heat-canvas", pane);
    this.canvas.style.pointerEvents = "none";
    map.on("moveend zoomend resize", this.draw, this);
    map.on("movestart zoomstart", this.hide, this);
    this.draw();
  },
  onRemove: function (map) {
    map.off("moveend zoomend resize", this.draw, this);
    map.off("movestart zoomstart", this.hide, this);
    this.canvas.remove(); this.canvas = null; this.map = null;
  },
  hide: function () { if (this.canvas) this.canvas.style.visibility = "hidden"; },
  setPoints: function (points) { this.points = points; this.draw(); return this; },
  draw: function () {
    if (!this.map || !this.canvas) return;
    const size = this.map.getSize();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(size.x * ratio);
    this.canvas.height = Math.round(size.y * ratio);
    this.canvas.style.width = size.x + "px";
    this.canvas.style.height = size.y + "px";
    L.DomUtil.setPosition(this.canvas, this.map.containerPointToLayerPoint([0, 0]));
    const ctx = this.canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);
    const step = 12;
    for (let y = 0; y < size.y; y += step) {
      for (let x = 0; x < size.x; x += step) {
        const position = this.map.containerPointToLatLng([x + step / 2, y + step / 2]);
        const value = DaveHeatField.densityAt(position.lat, position.lng, this.points);
        if (value < 0.005) continue;
        // Green -> yellow -> red uses the SAME fixed 0..1 scale on every refresh.
        // Do not renormalize every frame: that would make quiet and busy days look alike.
        const hue = 120 * (1 - value);
        ctx.fillStyle = "hsla(" + hue + ", 95%, 46%, " + (0.15 + 0.5 * value) + ")";
        ctx.fillRect(x, y, step + 0.5, step + 0.5);
      }
    }
    this.canvas.style.visibility = "visible";
  }
});
