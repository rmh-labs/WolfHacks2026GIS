Integration guide and example JavaScript for a static HTML site to fetch GeoJSON from the API and render with Leaflet.

1) Requirements
- Host the Flask API (api/app_cors.py) on a server reachable by your static site (use HTTPS in production).
- Ensure CORS is allowed (app_cors.py enables it).

2) Minimal HTML + JS example (Leaflet)

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Map Integration Example</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.3/dist/leaflet.css" />
  <style> #map { height: 100vh; } </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <script>
	const API_BASE = 'https://api.example.com'; // replace with your API host

	const map = L.map('map').setView([37.8, -96], 4);
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
	  maxZoom: 19,
	}).addTo(map);

	async function loadFeaturesForView() {
	  const bounds = map.getBounds();
	  const bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].join(',');
	  const url = `${API_BASE}/features?bbox=${encodeURIComponent(bbox)}&limit=1000`;
	  try {
		const res = await fetch(url);
		const geojson = await res.json();
		// Remove previous layer if exists
		if (window.obLayer) { map.removeLayer(window.obLayer); }
		window.obLayer = L.geoJSON(geojson, {
		  onEachFeature: (feature, layer) => {
			const p = feature.properties || {};
			layer.bindPopup(`<pre>${JSON.stringify(p, null, 2)}</pre>`);
		  }
		}).addTo(map);
	  } catch (e) {
		console.error('Failed to load features', e);
	  }
	}

	map.on('moveend', () => { loadFeaturesForView(); });
	// initial load
	loadFeaturesForView();
  </script>
</body>
</html>
```

3) Notes
- Replace API_BASE with your deployed API URL (including https://).
- Ensure the API is publicly reachable from the static site.
- If you need authentication, implement token-based auth and send Authorization headers from the client.
- Tune limit and server-side filters to avoid sending too much data to the browser.

