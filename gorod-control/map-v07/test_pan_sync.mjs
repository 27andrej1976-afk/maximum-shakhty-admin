// Regression test for maplibre/maplibre-gl-leaflet#64 on MapLibre GL JS v5.
// No network, emulator, APK build or changes to production are required.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const source = readFileSync(resolve(root, 'light-v10/vendor/leaflet-maplibre-gl.js'), 'utf8');
const positions = [];
const L = {
  Layer: { extend: spec => spec },
  DomUtil: { setPosition: (container, point) => positions.push({ container, point }) },
  Util: { throttle: fn => fn }
};
const maplibregl = { LngLat: { convert: ([lng, lat]) => ({ lng, lat }) } };
vm.runInNewContext(source, { L, maplibregl });
const bridge = L.MaplibreGL;
assert.ok(bridge?._update && bridge?._transformGL, 'Leaflet adapter must load');

let view = { lat: 47.7086, lng: 40.2146 };
const applied = [];
let fired = 0;
const transform = {
  setCenter(value) { this.center = value; },
  setZoom(value) { this.zoom = value; }
};
const gl = {
  _getTransformForUpdate: () => transform,
  transform: { apply: tr => applied.push({ lat: tr.center.lat, lng: tr.center.lng, zoom: tr.zoom }) },
  _fireMoveEvents: () => { fired += 1; }
};
const map = {
  getCenter: () => view,
  getZoom: () => 14,
  getSize: () => ({ multiplyBy: () => ({ x: 50, y: 40 }) }),
  containerPointToLayerPoint: () => ({
    subtract: p => ({ x: -p.x, y: -p.y })
  })
};
const layer = {
  _map: map, _glMap: gl, _container: { style: {} }, _zooming: false,
  options: { padding: 0.1 }, getSize: () => ({ x: 550, y: 440 }),
  _roundPoint: bridge._roundPoint, _transformGL: bridge._transformGL
};
bridge._update.call(layer);
assert.equal(applied.length, 1, 'MapLibre transform applied on first render');
assert.equal(applied[0].zoom, 13, 'Keep 256px Leaflet versus 512px MapLibre zoom offset');
assert.equal(applied[0].lng, view.lng);
assert.equal(applied[0].lat, view.lat);
view = { lat: 47.717, lng: 40.237 };
bridge._update.call(layer);
assert.equal(applied.length, 2, 'MapLibre transform must update after Leaflet pan');
assert.equal(applied[1].lng, view.lng);
assert.equal(applied[1].lat, view.lat);
assert.equal(fired, 2, 'Both pan frames should request vector redraw');
assert.equal(positions.length, 2, 'GL container follows Leaflet layout changes');

// Pre-v5 compatibility is retained; no exception if internal update API is absent.
const legacy = { transform: {} };
bridge._transformGL.call({ _map: map }, legacy);
assert.equal(legacy.transform.center.lng, view.lng);
assert.equal(legacy.transform.zoom, 13);

// Classic and Compact must still consume exactly the same corrected adapter.
for (const path of ['index.html', 'compact-v11/index.html']) {
  const html = readFileSync(resolve(root, path), 'utf8');
  assert.ok(html.includes('./light-v10/vendor/leaflet-maplibre-gl.js'), path);
  assert.ok(html.includes('./map-v07/city-map.js'), path);
  assert.ok(html.includes('./map-v07/vendor/leaflet.js'), path);
}
assert.match(readFileSync(resolve(root, 'compact-v11/index.html'), 'utf8'), /<base href="\.\.\/">/);
console.log('PASS MapLibre v5 pan/redraw adapter + Classic/Compact shared reference');
