(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD
        define(['leaflet', 'maplibre-gl'], factory);
    } else if (typeof exports === 'object') {
        // Node, CommonJS-like
        module.exports = factory(require('leaflet'), require('maplibre-gl'));
    } else {
        // Browser globals (root is window)
        root.returnExports = factory(root.L, root.maplibregl);
    }
}(typeof globalThis !== 'undefined' ? globalThis : this || self, function (L, maplibregl) {
    L.MaplibreGL = L.Layer.extend({
            options: {
            updateInterval: 32,
            // How much to extend the overlay view (relative to map size)
            // e.g. 0.1 would be 10% of map view in each direction
            padding: 0.1,
            // whether or not to register the mouse and keyboard
            // events on the maplibre overlay
            interactive: false,
            // set the tilepane as the default pane to draw gl tiles
            pane: 'tilePane'
        },

        initialize: function (options) {
            L.setOptions(this, options);

            // setup throttling the update event when panning
            this._throttledUpdate = L.Util.throttle(this._update, this.options.updateInterval, this);
        },

        onAdd: function (map) {
            if (!this._container) {
                this._initContainer();
            }

            var paneName = this.getPaneName();
            map.getPane(paneName).appendChild(this._container);

            this._initGL();

            this._offset = this._map.containerPointToLayerPoint([0, 0]);

            // work around https://github.com/mapbox/mapbox-gl-leaflet/issues/47
            if (map.options.zoomAnimation) {
                L.DomEvent.on(map._proxy, L.DomUtil.TRANSITION_END, this._transitionEnd, this);
            }
        },

        onRemove: function (map) {
            // onAdd can fail before MapLibre exists (for example, no WebGL).
            // Cleanup must finish so Leaflet can unregister every map listener.
            if (map && map._proxy && map.options.zoomAnimation) {
                L.DomEvent.off(map._proxy, L.DomUtil.TRANSITION_END, this._transitionEnd, this);
            }
            var gl = this._glMap;
            this._glMap = null;
            this._zooming = false;
            if (this._container && this._container.parentNode) {
                this._container.parentNode.removeChild(this._container);
            }
            // remove() may itself fail for a partially initialized GL renderer.
            // Never strand the failed overlay or abort the app's other controls.
            if (gl && typeof gl.remove === 'function') {
                try { gl.remove(); } catch (_cleanupError) {}
            }
        },

        getEvents: function () {
            return {
                move: this._throttledUpdate, // sensibly throttle updating while panning
                zoomanim: this._animateZoom, // applys the zoom animation to the <canvas>
                zoom: this._pinchZoom, // animate every zoom event for smoother pinch-zooming
                zoomstart: this._zoomStart, // flag starting a zoom to disable panning
                zoomend: this._zoomEnd,
                resize: this._resize
            };
        },

        getMaplibreMap: function () {
            return this._glMap;
        },

        getCanvas: function () {
            return this._glMap.getCanvas();
        },

        getSize: function () {
            return this._map.getSize().multiplyBy(1 + this.options.padding * 2);
        },

        getBounds: function () {
            var halfSize = this.getSize().multiplyBy(0.5);
            var center = this._map.latLngToContainerPoint(this._map.getCenter());
            return L.latLngBounds(
                this._map.containerPointToLatLng(center.subtract(halfSize)),
                this._map.containerPointToLatLng(center.add(halfSize))
            );
        },

        getContainer: function () {
            return this._container;
        },

        // returns the pane name set in options if it is a valid pane, defaults to tilePane
        getPaneName: function () {
            return this._map.getPane(this.options.pane) ? this.options.pane : 'tilePane';
        },

        _roundPoint: function(p) {
            return {x: Math.round(p.x), y: Math.round(p.y)};
        },

        _initContainer: function () {
            var container = this._container = L.DomUtil.create('div', 'leaflet-gl-layer');

            var size = this.getSize();
            var offset = this._map.getSize().multiplyBy(this.options.padding);
            container.style.width  = size.x + 'px';
            container.style.height = size.y + 'px';

            var topLeft = this._map.containerPointToLayerPoint([0, 0]).subtract(offset);

            L.DomUtil.setPosition(container, this._roundPoint(topLeft));
        },

        _initGL: function () {
            var center = this._map.getCenter();

            var options = L.extend({}, this.options, {
                container: this._container,
                center: [center.lng, center.lat],
                zoom: this._map.getZoom() - 1,
                attributionControl: false
            });

            this._glMap = new maplibregl.Map(options);

            // allow GL base map to pan beyond min/max latitudes
            this._glMap.transform.latRange = null;
            this._glMap.transform.maxValidLatitude = Infinity;

            this._transformGL(this._glMap);

            if (this._glMap._canvas.canvas) {
                // older versions of mapbox-gl surfaced the canvas differently
                this._glMap._actualCanvas = this._glMap._canvas.canvas;
            } else {
                this._glMap._actualCanvas = this._glMap._canvas;
            }

            // treat child <canvas> element like L.ImageOverlay
            var canvas = this._glMap._actualCanvas;
            L.DomUtil.addClass(canvas, 'leaflet-image-layer');
            L.DomUtil.addClass(canvas, 'leaflet-zoom-animated');
            if (this.options.interactive) {
                L.DomUtil.addClass(canvas, 'leaflet-interactive');
            }
            if (this.options.className) {
                L.DomUtil.addClass(canvas, this.options.className);
            }
        },

        _update: function (e) {
            if (!this._map || !this._glMap) {
                return;
            }
            // update the offset so we can correct for it later when we zoom
            this._offset = this._map.containerPointToLayerPoint([0, 0]);

            if (this._zooming) {
                return;
            }

            var size = this.getSize(),
                container = this._container,
                gl = this._glMap,
                offset = this._map.getSize().multiplyBy(this.options.padding),
                topLeft = this._map.containerPointToLayerPoint([0, 0]).subtract(offset);

            L.DomUtil.setPosition(container, this._roundPoint(topLeft));

            // React to real viewport size changes (Compact moves/resizes the map
            // after initialization). Resize only if necessary, never on every pan.
            // The public resize() updates MapLibre's projection/canvas dimensions.
            if (gl.transform.width !== size.x || gl.transform.height !== size.y) {
                container.style.width = size.x + 'px';
                container.style.height = size.y + 'px';
                if (typeof gl.resize === 'function') gl.resize();
            }
            // MapLibre v5 requires an applied transform + move event to render pans.
            // Its old private _update/_resize path causes a frozen background (#64).
            this._transformGL(gl);
        },

        _transformGL: function (gl) {
            if (!this._map || !gl || !gl.transform) return;
            var center = this._map.getCenter();

            // gl.setView([center.lat, center.lng], this._map.getZoom() - 1, 0);
            // calling setView directly causes sync issues because it uses requestAnimFrame

            var tr = gl._getTransformForUpdate ? gl._getTransformForUpdate() : gl.transform;
            if (typeof tr.setCenter === 'function' && typeof tr.setZoom === 'function') {
                // MapLibre GL JS v5: direct writes to center/zoom no longer redraw.
                tr.setCenter(maplibregl.LngLat.convert([center.lng, center.lat]));
                tr.setZoom(this._map.getZoom() - 1);
                gl.transform.apply(tr);
            } else {
                // Compatibility with the earlier MapLibre transform.
                tr.center = maplibregl.LngLat.convert([center.lng, center.lat]);
                tr.zoom = this._map.getZoom() - 1;
            }
            if (typeof gl._fireMoveEvents === 'function') gl._fireMoveEvents();
        },

        // update the map constantly during a pinch zoom
        _pinchZoom: function (e) {
            if (!this._map || !this._glMap) return;
            this._glMap.jumpTo({
                zoom: this._map.getZoom() - 1,
                center: this._map.getCenter()
            });
        },

        // borrowed from L.ImageOverlay
        // https://github.com/Leaflet/Leaflet/blob/master/src/layer/ImageOverlay.js#L139-L144
        _animateZoom: function (e) {
            if (!this._map || !this._glMap || !this._glMap._actualCanvas) return;
            var scale = this._map.getZoomScale(e.zoom);
            var padding = this._map.getSize().multiplyBy(this.options.padding * scale);
            var viewHalf = this.getSize()._divideBy(2);
            // corrections for padding (scaled), adapted from
            // https://github.com/Leaflet/Leaflet/blob/master/src/map/Map.js#L1490-L1508
            var topLeft = this._map.project(e.center, e.zoom)
                ._subtract(viewHalf)
                ._add(this._map._getMapPanePos()
                .add(padding))._round();
            var offset = this._map.project(this._map.getBounds().getNorthWest(), e.zoom)
                ._subtract(topLeft);

            L.DomUtil.setTransform(
                this._glMap._actualCanvas,
                offset.subtract(this._offset),
                scale
            );
        },

        _zoomStart: function (e) {
            if (!this._map || !this._glMap) return;
            this._zooming = true;
        },

        _zoomEnd: function () {
            if (!this._map || !this._glMap || !this._glMap._actualCanvas) return;
            var scale = this._map.getZoomScale(this._map.getZoom());

            L.DomUtil.setTransform(
                this._glMap._actualCanvas,
                // https://github.com/mapbox/mapbox-gl-leaflet/pull/130
                null,
                scale
            );

            this._zooming = false;

            this._update();
        },

        _transitionEnd: function (e) {
            if (!this._map || !this._glMap) return;
            L.Util.requestAnimFrame(function () {
                // A scheduled frame may run after the vector layer was removed.
                if (!this._map || !this._glMap || !this._glMap._actualCanvas) return;
                var zoom = this._map.getZoom();
                var center = this._map.getCenter();
                var offset = this._map.latLngToContainerPoint(
                    this._map.getBounds().getNorthWest()
                );

                // reset the scale and offset
                L.DomUtil.setTransform(this._glMap._actualCanvas, offset, 1);

                // enable panning once the gl map is ready again
                this._glMap.once('moveend', L.Util.bind(function () {
                    this._zoomEnd();
                }, this));

                // update the map position
                this._glMap.jumpTo({
                    center: center,
                    zoom: zoom - 1
                });
            }, this);
        },

        _resize: function (e) {
            this._transitionEnd(e);
        }
    });

    L.maplibreGL = function (options) {
        return new L.MaplibreGL(options);
    };

}));
