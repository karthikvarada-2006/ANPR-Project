/**
 * City ANPR Real-Time Surveillance & Traffic Command Dashboard
 * Single Page Vanilla JS Application
 *
 * Modules:
 * 1. Global Setup & Dark Map Tile Helpers
 * 2. Navigation & Tab Switching
 * 3. Tab 1: Overview KPIs, Flow Chart, Congestion & Coverage Map
 * 4. Tab 2: Trajectory Reconstruction, Impossible Hops & Animation Playback
 * 5. Tab 3: Heatmap Density, OD Matrix & Segment Loads
 * 6. Tab 4: Live Surveillance WebSocket Replayer & Radar Map
 * 7. Tab 5: Security Blacklist Watchlist Management
 */

// ==============================================================================
// 1. GLOBAL STATE & CONSTANTS
// ==============================================================================
const API_BASE = window.location.origin;
const WS_BASE = (window.location.protocol === "https:" ? "wss:" : "ws:") + "//" + window.location.host;

// Global Data Caches
let camerasList = [];
let camerasById = {};
let overviewFlowChart = null;

// Leaflet Map Instances
let overviewMap = null;
let trajectoryMap = null;
let heatmapMap = null;
let alertsRadarMap = null;

// Layers
let overviewCamLayer = null;
let trajRouteLayer = null;
let trajHopsLayer = null;
let trajMarkersLayer = null;
let trajMovingMarker = null;
let heatmapLayer = null;
let heatmapCamLayer = null;
let alertsCamLayer = null;
let alertsRadarMarker = null;

// Trajectory Playback Animation State
let trajAnimationTimer = null;
let trajAnimationPoints = [];
let trajAnimationIdx = 0;
let isTrajPlaying = false;

// Live WebSocket State
let liveWebSocket = null;
let liveAlertsHistory = [];
let liveAlertCounts = { total: 0, blacklist: 0, cloned: 0, curfew: 0, speed: 0 };

// Dark Tile Layer Helper using OpenStreetMap and CSS Dark Filter (Zero API Key required)
function createDarkTileLayer() {
  return L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
    className: "dark-tiles",
  });
}

// Toast Notification Helper
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️"}</span>
    <div>${message}</div>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}


// ==============================================================================
// 2. NAVIGATION & TAB SWITCHING
// ==============================================================================
function initNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;

      // Update active nav button
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      // Show target tab pane
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.remove("active");
      });
      const activePane = document.getElementById(`tab-${targetId}`);
      if (activePane) activePane.classList.add("active");

      // Invalidate Leaflet map size on visibility change so tiles render properly
      setTimeout(() => {
        if (targetId === "overview" && overviewMap) overviewMap.invalidateSize();
        if (targetId === "trajectory" && trajectoryMap) trajectoryMap.invalidateSize();
        if (targetId === "heatmap" && heatmapMap) heatmapMap.invalidateSize();
        if (targetId === "alerts" && alertsRadarMap) alertsRadarMap.invalidateSize();
      }, 60);
    });
  });
}


// ==============================================================================
// 3. TAB 1: OVERVIEW LOGIC
// ==============================================================================
async function initOverviewTab() {
  // 1. Initialize Small Overview Map centered on Bangalore
  if (!overviewMap) {
    const initCenter = [12.9716, 77.5946];
    const initZoom = 12;
    overviewMap = L.map("overview-map", {
      zoomControl: true,
      attributionControl: false,
    }).setView(initCenter, initZoom);
    createDarkTileLayer().addTo(overviewMap);
    overviewCamLayer = L.layerGroup().addTo(overviewMap);
  }

  await loadOverviewData();
}

async function loadOverviewData() {
  // 2. Fetch System Health & KPI Metrics (Simulated Bangalore dataset)
  try {
    const resSummary = await fetch(`${API_BASE}/api/analytics/summary`);
    if (resSummary.ok) {
      const summary = await resSummary.json();
      document.getElementById("kpi-events").textContent = summary.total_events.toLocaleString();
      document.getElementById("kpi-vehicles").textContent = summary.total_unique_plates.toLocaleString();
      document.getElementById("kpi-speed").innerHTML = `${summary.average_speed_kmh} <span class="unit">km/h</span>`;
      document.getElementById("kpi-alerts").textContent = summary.total_alerts.toLocaleString();
    }
  } catch (err) {
    console.warn("Could not load summary metrics:", err);
  }

  // 3. Fetch Cameras and plot onto overview map
  try {
    const resCams = await fetch(`${API_BASE}/api/cameras`);
    if (resCams.ok) {
      camerasList = await resCams.json();
      camerasById = {};
      overviewCamLayer.clearLayers();

      const latLngs = [];
      camerasList.forEach((c) => {
        camerasById[c.camera_id] = c;
        const pt = [c.lat, c.lon];
        latLngs.push(pt);

        const circle = L.circleMarker(pt, {
          radius: 5,
          fillColor: "#06b6d4",
          color: "#ffffff",
          weight: 1,
          opacity: 0.9,
          fillOpacity: 0.8,
        });

        circle.bindPopup(`
          <div class="popup-title">${c.name || c.camera_id}</div>
          <div class="popup-row"><span>Camera ID:</span><span class="popup-val">${c.camera_id}</span></div>
          <div class="popup-row"><span>GPS:</span><span class="popup-val">${c.lat.toFixed(4)}, ${c.lon.toFixed(4)}</span></div>
        `);
        overviewCamLayer.addLayer(circle);
      });

      if (latLngs.length > 0) {
        overviewMap.fitBounds(L.latLngBounds(latLngs), { padding: [15, 15] });
      }
      document.getElementById("overview-cam-count").textContent = `${camerasList.length} Active`;
    }
  } catch (err) {
    console.warn("Could not load cameras list:", err);
  }

  // 4. Render City Flow Chart (Chart.js)
  try {
    const resFlow = await fetch(`${API_BASE}/api/analytics/flow-trend?window=15`);
    if (resFlow.ok) {
      const flowData = await resFlow.json();
      renderOverviewFlowChart(flowData);
    }
  } catch (err) {
    console.warn("Could not load flow trends:", err);
  }

  // 5. Populate Top Congested Table
  try {
    const resCong = await fetch(`${API_BASE}/api/analytics/congestion`);
    if (resCong.ok) {
      const congList = await resCong.json();
      const worstByCamera = new Map();
      congList.forEach((item) => {
        const existing = worstByCamera.get(item.camera_id);
        if (!existing || item.severity > existing.severity) {
          worstByCamera.set(item.camera_id, item);
        }
      });
      const top5 = Array.from(worstByCamera.values())
        .sort((a, b) => b.severity - a.severity)
        .slice(0, 5);

      const tbody = document.querySelector("#top-congested-table tbody");
      if (top5.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No active congestion bottlenecks detected.</td></tr>`;
      } else {
        tbody.innerHTML = top5
          .map((c) => {
            const sevPct = Math.round(c.severity * 100);
            const peakTime = c.window_start ? c.window_start.substring(11, 16) : "";
            const camName = c.camera_name ? c.camera_name.split("&")[0] : c.camera_id;
            return `
              <tr>
                <td><strong>${c.camera_id}</strong> <br><small class="text-muted">${camName} (${peakTime} peak)</small></td>
                <td><span class="text-rose font-bold">${c.avg_speed_kmh.toFixed(1)} km/h</span></td>
                <td>${c.free_flow_speed_kmh.toFixed(1)} km/h</td>
                <td><span class="sev-badge ${sevPct > 50 ? "high" : "medium"}">${sevPct}% Deficit</span></td>
              </tr>
            `;
          })
          .join("");
      }
    }
  } catch (err) {
    console.warn("Could not load congestion table:", err);
  }
}

function renderOverviewFlowChart(flowData) {
  const ctx = document.getElementById("overview-flow-chart");
  if (!ctx) return;

  const labels = flowData.map((d) => d.window_start.substring(11, 16));
  const counts = flowData.map((d) => d.vehicle_count);
  const speeds = flowData.map((d) => d.avg_speed_kmh);

  if (overviewFlowChart) {
    overviewFlowChart.destroy();
  }

  overviewFlowChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Vehicle Volume",
          data: counts,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.12)",
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          yAxisID: "yVolume",
          pointRadius: 0,
          pointHitRadius: 10,
        },
        {
          label: "Average Speed (km/h)",
          data: speeds,
          borderColor: "#f59e0b",
          borderWidth: 2.5,
          borderDash: [5, 4],
          tension: 0.35,
          fill: false,
          yAxisID: "ySpeed",
          pointRadius: 0,
          pointHitRadius: 10,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          titleColor: "#ffffff",
          bodyColor: "#94a3b8",
          borderColor: "rgba(255, 255, 255, 0.15)",
          borderWidth: 1,
          padding: 12,
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#64748b", maxTicksLimit: 12, font: { size: 11 } },
        },
        yVolume: {
          type: "linear",
          position: "left",
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#06b6d4", font: { size: 11 } },
          title: { display: true, text: "Vehicles / 15m", color: "#06b6d4", font: { size: 11 } },
        },
        ySpeed: {
          type: "linear",
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#f59e0b", font: { size: 11 } },
          title: { display: true, text: "Speed (km/h)", color: "#f59e0b", font: { size: 11 } },
        },
      },
    },
  });
}


// ==============================================================================
// 4. TAB 2: TRAJECTORY SEARCH & ANIMATION LOGIC
// ==============================================================================
function initTrajectoryTab() {
  if (!trajectoryMap) {
    trajectoryMap = L.map("trajectory-map", {
      zoomControl: true,
      attributionControl: false,
    }).setView([12.9716, 77.5946], 12);
    createDarkTileLayer().addTo(trajectoryMap);

    trajRouteLayer = L.layerGroup().addTo(trajectoryMap);
    trajHopsLayer = L.layerGroup().addTo(trajectoryMap);
    trajMarkersLayer = L.layerGroup().addTo(trajectoryMap);
  }

  const searchInput = document.getElementById("traj-search-input");
  const autocompleteList = document.getElementById("autocomplete-list");
  const searchBtn = document.getElementById("traj-search-btn");
  const fuzzyToggle = document.getElementById("traj-fuzzy-toggle");

  // Autocomplete debounce
  let debounceTimer = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const query = searchInput.value.trim().toUpperCase();
    if (query.length < 2) {
      autocompleteList.classList.add("hidden");
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/plates/search?q=${encodeURIComponent(query)}&limit=8`);
        if (res.ok) {
          const suggestions = await res.json();
          if (suggestions.length > 0) {
            autocompleteList.innerHTML = suggestions
              .map(
                (s) => `
                <div class="autocomplete-item" data-plate="${s.plate}">
                  <span class="autocomplete-plate">${s.plate}</span>
                  <span class="autocomplete-count">${s.count} sightings</span>
                </div>
              `
              )
              .join("");
            autocompleteList.classList.remove("hidden");

            // Attach click listeners to suggestions
            autocompleteList.querySelectorAll(".autocomplete-item").forEach((el) => {
              el.addEventListener("click", () => {
                searchInput.value = el.dataset.plate;
                autocompleteList.classList.add("hidden");
                loadVehicleTrajectory(el.dataset.plate, fuzzyToggle.checked);
              });
            });
          } else {
            autocompleteList.classList.add("hidden");
          }
        }
      } catch (e) {
        console.warn("Autocomplete error:", e);
      }
    }, 220);
  });

  // Hide dropdown on click outside
  document.addEventListener("click", (e) => {
    if (!searchInput.contains(e.target) && !autocompleteList.contains(e.target)) {
      autocompleteList.classList.add("hidden");
    }
  });

  // Search button and Enter key
  searchBtn.addEventListener("click", () => {
    const plate = searchInput.value.trim().toUpperCase();
    if (plate) loadVehicleTrajectory(plate, fuzzyToggle.checked);
  });
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      autocompleteList.classList.add("hidden");
      const plate = searchInput.value.trim().toUpperCase();
      if (plate) loadVehicleTrajectory(plate, fuzzyToggle.checked);
    }
  });

  // Sample plate chips
  document.querySelectorAll(".chip-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const plate = btn.dataset.plate;
      searchInput.value = plate;
      loadVehicleTrajectory(plate, fuzzyToggle.checked);
    });
  });

  // Animation Play/Pause & Slider
  const playBtn = document.getElementById("traj-play-btn");
  const timeSlider = document.getElementById("traj-time-slider");

  playBtn.addEventListener("click", toggleTrajectoryPlayback);
  timeSlider.addEventListener("input", (e) => {
    seekTrajectoryPlayback(parseInt(e.target.value, 10));
  });

  document.getElementById("traj-fit-btn").addEventListener("click", () => {
    if (trajAnimationPoints.length > 0) {
      trajectoryMap.fitBounds(L.latLngBounds(trajAnimationPoints), { padding: [30, 30] });
    }
  });
}

async function loadVehicleTrajectory(plate, fuzzy = true) {
  const notFoundBanner = document.getElementById("traj-not-found-banner");
  notFoundBanner.classList.add("hidden");

  // Reset playback
  stopTrajectoryPlayback();

  try {
    const res = await fetch(`${API_BASE}/api/trajectory/${encodeURIComponent(plate)}?fuzzy=${fuzzy}`);
    if (!res.ok) {
      if (res.status === 404) {
        notFoundBanner.classList.remove("hidden");
        document.getElementById("traj-not-found-msg").textContent = `Vehicle ID '${plate}' was not found in the camera registry. Try clicking one of the sample vehicles below.`;
        return;
      }
      throw new Error(`Trajectory query failed with status ${res.status}`);
    }

    const data = await res.json();
    renderTrajectoryResult(data);
    showToast(`Loaded trajectory for ${data.plate} (${data.total_trips} trips, ${data.points.length} sightings)`, "success");
  } catch (err) {
    showToast(err.message, "error");
    notFoundBanner.classList.remove("hidden");
    document.getElementById("traj-not-found-msg").textContent = `Failed to reconstruct trajectory: ${err.message}`;
  }
}

function renderTrajectoryResult(trajData) {
  // Update header badges & stats
  document.getElementById("traj-display-plate").textContent = trajData.plate;
  document.getElementById("traj-trips-summary").textContent = `${trajData.total_trips} ${trajData.total_trips === 1 ? "Trip" : "Trips"}`;
  document.getElementById("traj-sightings-count").textContent = `${trajData.points.length} Sightings`;
  document.getElementById("traj-total-dist").textContent = `${trajData.total_distance_km.toFixed(1)} km`;
  document.getElementById("traj-total-dur").textContent = `${Math.round(trajData.total_duration_seconds / 60)} min`;

  const avgSpeed = trajData.total_duration_seconds > 0 ? (trajData.total_distance_km / (trajData.total_duration_seconds / 3600)).toFixed(1) : 0;
  document.getElementById("traj-avg-speed").textContent = `${avgSpeed} km/h`;

  // Clear previous map layers
  trajRouteLayer.clearLayers();
  trajHopsLayer.clearLayers();
  trajMarkersLayer.clearLayers();
  if (trajMovingMarker) {
    trajectoryMap.removeLayer(trajMovingMarker);
    trajMovingMarker = null;
  }

  // 1. Render Separate Polylines for each Trip (Never join two trips into one line!)
  const tripPalette = ["#38bdf8", "#a855f7", "#ec4899", "#10b981", "#f59e0b", "#06b6d4"];
  trajAnimationPoints = [];

  if (trajData.trips && trajData.trips.length > 0) {
    trajData.trips.forEach((trip, tIdx) => {
      const tripCoords = (trip.route_geometry && trip.route_geometry.length > 0)
        ? trip.route_geometry
        : (trip.points || []).map((p) => [p.lat, p.lon]);

      if (tripCoords.length > 1) {
        const polyline = L.polyline(tripCoords, {
          color: tripPalette[tIdx % tripPalette.length],
          weight: 4.5,
          opacity: 0.88,
          lineCap: "round",
          lineJoin: "round",
        });
        const tripTrack = trip.track_id ? ` (Track: ${trip.track_id})` : "";
        polyline.bindPopup(`<strong>Trip #${trip.trip_id}</strong>${tripTrack}<br>${trip.num_sightings} sightings<br>${trip.total_distance_km.toFixed(1)} km`);
        trajRouteLayer.addLayer(polyline);
      }
      tripCoords.forEach((pt) => trajAnimationPoints.push(pt));
    });
  } else if (trajData.route_geometry && trajData.route_geometry.length > 0) {
    const polyline = L.polyline(trajData.route_geometry, {
      color: "#38bdf8",
      weight: 5,
      opacity: 0.85,
      lineCap: "round",
      lineJoin: "round",
    });
    trajRouteLayer.addLayer(polyline);
    trajAnimationPoints = trajData.route_geometry;
  } else if (trajData.points && trajData.points.length > 0) {
    trajAnimationPoints = trajData.points.map((p) => [p.lat, p.lon]);
  }

  // 2. Render Flagged Impossible Hops (Red Dashed Lines)
  const flaggedHops = trajData.flagged_hops || [];
  const flaggedBox = document.getElementById("traj-flagged-box");
  const flaggedList = document.getElementById("traj-flagged-list");

  if (flaggedHops.length > 0) {
    flaggedBox.classList.remove("hidden");
    flaggedList.innerHTML = flaggedHops
      .map(
        (h) => `
        <div>• Hop between <strong>${h.previous_camera}</strong> and <strong>${h.camera_id}</strong> (${Math.round(h.distance_meters)}m in ${Math.round(h.time_delta_seconds)}s) &rarr; <span class="font-bold text-rose">${h.implied_speed_kmh.toFixed(1)} km/h</span> (${h.reason})</div>
      `
      )
      .join("");

    // Draw dashed lines between the flagged camera pairs
    flaggedHops.forEach((h) => {
      const c1 = camerasById[h.previous_camera];
      const c2 = camerasById[h.camera_id];
      if (c1 && c2) {
        const dashedHop = L.polyline(
          [
            [c1.lat, c1.lon],
            [c2.lat, c2.lon],
          ],
          {
            color: "#ef4444",
            weight: 3.5,
            dashArray: "8, 8",
            opacity: 0.95,
          }
        );
        dashedHop.bindPopup(`<strong>Flagged Hop:</strong> ${h.implied_speed_kmh.toFixed(1)} km/h between ${h.previous_camera} and ${h.camera_id}`);
        trajHopsLayer.addLayer(dashedHop);
      }
    });
  } else {
    flaggedBox.classList.add("hidden");
  }

  // 3. Render Numbered Camera Waypoint Markers
  const points = trajData.points || [];
  points.forEach((p, idx) => {
    const isFirst = idx === 0;
    const isLast = idx === points.length - 1;

    let markerClass = "numbered-marker";
    if (isFirst) markerClass += " first";
    else if (isLast) markerClass += " last";

    const customIcon = L.divIcon({
      className: "custom-pin-wrapper",
      html: `<div class="${markerClass}">${idx + 1}</div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });

    const marker = L.marker([p.lat, p.lon], { icon: customIcon });
    const speedText = p.speed != null ? `${p.speed.toFixed(1)} km/h` : "N/A";
    const speedLabel = p.speed_label ? ` <span style="font-size:0.75rem; color:#94a3b8;">(${p.speed_label})</span>` : "";
    const confText = p.confidence != null ? `${(p.confidence * 100).toFixed(1)}%` : "N/A (anonymous)";
    const headingText = p.heading != null ? `${p.heading}&deg; (${p.compass || ""})` : (p.direction || "N/A");

    marker.bindPopup(`
      <div class="popup-title">Stop #${idx + 1}: ${p.name || p.camera}</div>
      <div class="popup-row"><span>Camera:</span><span class="popup-val">${p.camera}</span></div>
      <div class="popup-row"><span>Time:</span><span class="popup-val">${p.time ? p.time.substring(11, 19) : ""}</span></div>
      <div class="popup-row"><span>Speed:</span><span class="popup-val">${speedText}${speedLabel}</span></div>
      <div class="popup-row"><span>Direction:</span><span class="popup-val">${headingText}</span></div>
      <div class="popup-row"><span>OCR Read:</span><span class="popup-val">${p.plate_read || trajData.plate}</span></div>
      <div class="popup-row"><span>Confidence:</span><span class="popup-val">${confText}</span></div>
    `);
    trajMarkersLayer.addLayer(marker);
  });

  // Fit map bounds
  if (trajAnimationPoints.length > 0) {
    trajectoryMap.fitBounds(L.latLngBounds(trajAnimationPoints), { padding: [35, 35] });
  }

  // 4. Render Individual Trips List in Sidebar
  const tripsContainer = document.getElementById("traj-trips-list");
  const tripsCountBadge = document.getElementById("traj-trips-count");
  const trips = trajData.trips || [];
  if (tripsCountBadge) tripsCountBadge.textContent = trips.length;

  if (tripsContainer) {
    if (trips.length === 0) {
      tripsContainer.innerHTML = `<div class="empty-state-text">No distinct trips recorded.</div>`;
    } else {
      tripsContainer.innerHTML = trips
        .map(
          (t) => {
            const longBadge = t.long_trip ? `<span class="badge-pill" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); margin-left: 6px; font-size: 0.72rem; padding: 2px 7px;">Long Trip (>500 pts)</span>` : "";
            const trackText = t.track_id ? `<div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Track: ${t.track_id}</div>` : "";
            return `
            <div class="trip-card" data-trip-id="${t.trip_id}">
              <div class="trip-card-header">
                <span class="trip-title">🚗 Trip #${t.trip_id} ${longBadge}</span>
                <span class="trip-time-range">${t.start_time ? t.start_time.substring(11, 16) : ""} &rarr; ${t.end_time ? t.end_time.substring(11, 16) : ""}</span>
              </div>
              ${trackText}
              <div class="trip-metrics-row">
                <span>📏 <strong>${t.total_distance_km.toFixed(1)} km</strong></span>
                <span>⏱️ <strong>${Math.round(t.duration_seconds / 60)} min</strong></span>
                <span>⚡ <strong>${t.avg_speed_kmh.toFixed(1)} km/h</strong></span>
                <span>📍 <strong>${t.num_sightings} stops</strong></span>
              </div>
            </div>
          `;
          }
        )
        .join("");

      // Add click handler to highlight trip
      tripsContainer.querySelectorAll(".trip-card").forEach((card) => {
        card.addEventListener("click", () => {
          tripsContainer.querySelectorAll(".trip-card").forEach((c) => c.classList.remove("active"));
          card.classList.add("active");
          const tripId = parseInt(card.dataset.tripId, 10);
          const matchedTrip = trips.find((t) => t.trip_id === tripId);
          if (matchedTrip && matchedTrip.points && matchedTrip.points.length > 0) {
            const tripPts = matchedTrip.points.map((p) => [p.lat, p.lon]);
            trajectoryMap.fitBounds(L.latLngBounds(tripPts), { padding: [40, 40] });
          }
        });
      });
    }
  }

  // 5. Render Chronological Timeline in Sidebar
  const timelineList = document.getElementById("traj-timeline-list");
  let timelineHtml = "";
  let lastTripId = null;

  points.forEach((p, idx) => {
    // If point has trip_id and it changes, add a section divider
    if (p.trip_id && p.trip_id !== lastTripId) {
      lastTripId = p.trip_id;
      timelineHtml += `<div class="timeline-trip-header">Trip #${p.trip_id} Sightings</div>`;
    }

    const speedDisplay = p.speed != null ? `${p.speed.toFixed(1)} km/h` : "N/A";
    const compassDisplay = p.compass || p.direction || "--";
    const confDisplay = p.confidence != null ? `${(p.confidence * 100).toFixed(0)}%` : "N/A";

    timelineHtml += `
      <div class="timeline-item" data-idx="${idx}" data-lat="${p.lat}" data-lon="${p.lon}">
        <div class="timeline-idx">${idx + 1}</div>
        <div class="timeline-body">
          <div class="timeline-cam">${p.name || p.camera}</div>
          <div class="timeline-time">${p.time ? p.time.substring(11, 19) : ""} &bull; ${p.camera}</div>
          <div class="timeline-details">
            <span>⚡ ${speedDisplay}</span>
            <span>🧭 ${compassDisplay}</span>
            <span>🎯 ${confDisplay}</span>
          </div>
        </div>
      </div>
    `;
  });

  timelineList.innerHTML = timelineHtml;

  // Timeline click listener to fly to marker
  timelineList.querySelectorAll(".timeline-item").forEach((el) => {
    el.addEventListener("click", () => {
      const lat = parseFloat(el.dataset.lat);
      const lon = parseFloat(el.dataset.lon);
      trajectoryMap.flyTo([lat, lon], 14, { duration: 0.8 });
    });
  });

  // Initialize playback slider
  const slider = document.getElementById("traj-time-slider");
  slider.max = trajAnimationPoints.length - 1;
  slider.value = 0;
  trajAnimationIdx = 0;

  if (points.length > 0) {
    document.getElementById("slider-start-label").textContent = points[0].time.substring(11, 16);
    document.getElementById("slider-end-label").textContent = points[points.length - 1].time.substring(11, 16);
    document.getElementById("slider-current-label").textContent = points[0].time.substring(11, 19);
  }
}

// Trajectory Animated Moving Marker Controller
function toggleTrajectoryPlayback() {
  if (trajAnimationPoints.length === 0) return;

  if (isTrajPlaying) {
    stopTrajectoryPlayback();
  } else {
    startTrajectoryPlayback();
  }
}

function startTrajectoryPlayback() {
  isTrajPlaying = true;
  document.getElementById("play-icon").textContent = "⏸";

  if (!trajMovingMarker && trajAnimationPoints.length > 0) {
    const carIcon = L.divIcon({
      className: "custom-car-pin",
      html: `<div class="vehicle-moving-pin"></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
    trajMovingMarker = L.marker(trajAnimationPoints[trajAnimationIdx], { icon: carIcon }).addTo(trajectoryMap);
  }

  const speedMultiplier = parseInt(document.getElementById("traj-playback-speed").value, 10) || 2;
  const intervalMs = Math.max(30, 200 / speedMultiplier);

  trajAnimationTimer = setInterval(() => {
    trajAnimationIdx++;
    if (trajAnimationIdx >= trajAnimationPoints.length) {
      trajAnimationIdx = 0; // Loop or stop
    }

    seekTrajectoryPlayback(trajAnimationIdx);
  }, intervalMs);
}

function stopTrajectoryPlayback() {
  isTrajPlaying = false;
  document.getElementById("play-icon").textContent = "▶";
  if (trajAnimationTimer) {
    clearInterval(trajAnimationTimer);
    trajAnimationTimer = null;
  }
}

function seekTrajectoryPlayback(idx) {
  if (trajAnimationPoints.length === 0) return;
  trajAnimationIdx = Math.max(0, Math.min(idx, trajAnimationPoints.length - 1));

  document.getElementById("traj-time-slider").value = trajAnimationIdx;
  const currentCoord = trajAnimationPoints[trajAnimationIdx];

  if (!trajMovingMarker) {
    const carIcon = L.divIcon({
      className: "custom-car-pin",
      html: `<div class="vehicle-moving-pin"></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
    trajMovingMarker = L.marker(currentCoord, { icon: carIcon }).addTo(trajectoryMap);
  } else {
    trajMovingMarker.setLatLng(currentCoord);
  }

  // Update slider label
  document.getElementById("slider-current-label").textContent = `Step ${trajAnimationIdx + 1} / ${trajAnimationPoints.length}`;
}


// ==============================================================================
// 5. TAB 3: TRAFFIC HEATMAP LOGIC
// ==============================================================================
async function initHeatmapTab() {
  if (!heatmapMap) {
    const initCenter = [12.9716, 77.5946];
    const initZoom = 12;
    heatmapMap = L.map("traffic-heatmap-map", {
      zoomControl: true,
      attributionControl: false,
    }).setView(initCenter, initZoom);
    createDarkTileLayer().addTo(heatmapMap);

    heatmapCamLayer = L.layerGroup().addTo(heatmapMap);
  }

  // 1. Populate 15-Minute Windows Dropdown from flow trend
  const windowSelect = document.getElementById("heatmap-window-select");
  const windowSlider = document.getElementById("heatmap-slider");
  let windowsList = [];

  try {
    const res = await fetch(`${API_BASE}/api/analytics/flow-trend?window=15`);
    if (res.ok) {
      windowsList = await res.json();
      windowSlider.max = windowsList.length - 1;

      windowSelect.innerHTML = `<option value="">Whole Day Peak Window (Busiest)</option>` +
        windowsList.map((w, i) => `
          <option value="${w.window_start}">${w.window_start.substring(11, 16)} - ${w.window_end.substring(11, 16)} (${w.vehicle_count} vehicles, ${w.avg_speed_kmh} km/h)</option>
        `).join("");
    }
  } catch (err) {
    console.warn("Could not load windows list:", err);
  }

  // Window selection change
  windowSelect.addEventListener("change", () => {
    const selectedWindow = windowSelect.value;
    loadHeatmapData(selectedWindow);
    document.getElementById("heatmap-window-display").textContent = selectedWindow ? selectedWindow.substring(11, 16) : "Peak Window";
  });

  windowSlider.addEventListener("input", (e) => {
    const idx = parseInt(e.target.value, 10);
    if (windowsList[idx]) {
      const w = windowsList[idx];
      windowSelect.value = w.window_start;
      document.getElementById("heatmap-window-display").textContent = `${w.window_start.substring(11, 16)} - ${w.window_end.substring(11, 16)}`;
      loadHeatmapData(w.window_start);
    }
  });

  document.getElementById("heatmap-prev-btn").addEventListener("click", () => {
    windowSlider.value = Math.max(0, parseInt(windowSlider.value, 10) - 1);
    windowSlider.dispatchEvent(new Event("input"));
  });

  document.getElementById("heatmap-next-btn").addEventListener("click", () => {
    windowSlider.value = Math.min(parseInt(windowSlider.max, 10), parseInt(windowSlider.value, 10) + 1);
    windowSlider.dispatchEvent(new Event("input"));
  });

  document.getElementById("heatmap-refresh-btn").addEventListener("click", () => {
    loadHeatmapData(windowSelect.value);
  });

  // Initial load
  loadHeatmapData("");
  loadODMatrixTable();
  loadBusiestSegments();
}

async function loadHeatmapData(windowParam = "") {
  try {
    const url = windowParam
      ? `${API_BASE}/api/analytics/heatmap?window=${encodeURIComponent(windowParam)}`
      : `${API_BASE}/api/analytics/heatmap`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Heatmap points request failed");
    const points = await res.json();

    // 1. Render Leaflet Heat Layer
    if (heatmapLayer) {
      heatmapMap.removeLayer(heatmapLayer);
      heatmapLayer = null;
    }

    const heatArray = points.map((p) => [p.lat, p.lon, p.weight]);
    heatmapLayer = L.heatLayer(heatArray, {
      radius: 32,
      blur: 22,
      maxZoom: 16,
      max: 1.0,
      gradient: {
        0.2: "#10b981",
        0.5: "#f59e0b",
        0.8: "#ef4444",
        1.0: "#dc2626",
      },
    }).addTo(heatmapMap);

    // 2. Render Color-coded Camera Markers
    heatmapCamLayer.clearLayers();
    points.forEach((p) => {
      let pinColor = "#10b981"; // Free flow
      if (p.weight > 0.65) pinColor = "#ef4444"; // Congested
      else if (p.weight > 0.4) pinColor = "#f59e0b"; // Moderate

      const circle = L.circleMarker([p.lat, p.lon], {
        radius: 6,
        fillColor: pinColor,
        color: "#ffffff",
        weight: 1.5,
        opacity: 0.95,
        fillOpacity: 0.9,
      });

      circle.bindPopup(`
        <div class="popup-title">${p.camera_name || p.camera_id}</div>
        <div class="popup-row"><span>Camera:</span><span class="popup-val">${p.camera_id}</span></div>
        <div class="popup-row"><span>Vehicles:</span><span class="popup-val">${p.vehicle_count}</span></div>
        <div class="popup-row"><span>Avg Speed:</span><span class="popup-val">${p.avg_speed_kmh != null ? p.avg_speed_kmh.toFixed(1) + " km/h" : "N/A"}</span></div>
        <div class="popup-row"><span>Weight:</span><span class="popup-val">${(p.weight * 100).toFixed(0)}%</span></div>
      `);
      heatmapCamLayer.addLayer(circle);
    });
  } catch (err) {
    console.warn("Could not load heatmap points:", err);
  }
}

async function loadODMatrixTable() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/od-matrix`);
    if (!res.ok) return;
    const odData = await res.json();
    document.getElementById("od-total-trips-badge").textContent = `${odData.total_trips.toLocaleString()} trips`;

    const table = document.getElementById("od-matrix-table");
    const zones = odData.zones;

    let thead = `<tr><th>Origin \\ Dest</th>` + zones.map((z) => `<th>${z.split("(")[0]}</th>`).join("") + `</tr>`;
    let tbody = zones
      .map((origin) => {
        let rowHtml = `<tr><td class="origin-label">${origin}</td>`;
        zones.forEach((dest) => {
          const count = odData.matrix[origin] ? odData.matrix[origin][dest] || 0 : 0;
          let cellStyle = "";
          if (count > 400) cellStyle = "background: rgba(239, 68, 68, 0.4); color: #fca5a5;";
          else if (count > 200) cellStyle = "background: rgba(245, 158, 11, 0.3); color: #fde68a;";
          else if (count > 50) cellStyle = "background: rgba(6, 182, 212, 0.2); color: #a5f3fc;";
          rowHtml += `<td style="${cellStyle}">${count}</td>`;
        });
        rowHtml += `</tr>`;
        return rowHtml;
      })
      .join("");

    table.querySelector("thead").innerHTML = thead;
    table.querySelector("tbody").innerHTML = tbody;
  } catch (err) {
    console.warn("Could not load OD matrix:", err);
  }
}

async function loadBusiestSegments() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/route-density`);
    if (!res.ok) return;
    const segments = await res.json();
    const tbody = document.querySelector("#busiest-segments-table tbody");

    // Group and sum vehicle counts by segment_id across all windows
    const segMap = {};
    segments.forEach((s) => {
      segMap[s.segment_id] = (segMap[s.segment_id] || 0) + s.vehicle_count;
    });

    const sorted = Object.entries(segMap)
      .map(([seg, count]) => ({ segment: seg, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);

    if (sorted.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">No segment loads recorded.</td></tr>`;
      return;
    }

    tbody.innerHTML = sorted
      .map((s, idx) => `
        <tr>
          <td><span class="badge-outline">#${idx + 1}</span></td>
          <td class="font-semibold" style="font-size: 0.78rem; color: #f8fafc;">${s.segment}</td>
          <td><span class="text-cyan font-bold">${s.count.toLocaleString()} vehicles</span></td>
        </tr>
      `)
      .join("");
  } catch (err) {
    console.warn("Could not load route density segments:", err);
  }
}


// ==============================================================================
// 6. TAB 4: LIVE ALERTS LOGIC (WEBSOCKET STREAM)
// ==============================================================================
function initLiveAlertsTab() {
  if (!alertsRadarMap) {
    alertsRadarMap = L.map("alerts-radar-map", {
      zoomControl: true,
      attributionControl: false,
    }).setView([12.9716, 77.5946], 12);
    createDarkTileLayer().addTo(alertsRadarMap);

    alertsCamLayer = L.layerGroup().addTo(alertsRadarMap);
  }

  // Populate cameras on alerts map
  if (camerasList.length > 0) {
    alertsCamLayer.clearLayers();
    camerasList.forEach((c) => {
      const circle = L.circleMarker([c.lat, c.lon], {
        radius: 4,
        fillColor: "#64748b",
        color: "#ffffff",
        weight: 1,
        opacity: 0.7,
        fillOpacity: 0.6,
      });
      circle.bindPopup(`<strong>${c.name}</strong><br>ID: ${c.camera_id}`);
      alertsCamLayer.addLayer(circle);
    });
  }

  const startBtn = document.getElementById("ws-start-btn");
  const stopBtn = document.getElementById("ws-stop-btn");
  const speedSelect = document.getElementById("ws-speed-select");

  startBtn.addEventListener("click", () => {
    const speed = speedSelect.value;
    startLiveAlertsStream(speed);
  });

  stopBtn.addEventListener("click", () => {
    stopLiveAlertsStream();
  });

  // Filters for Live Alert Feed
  document.getElementById("alert-filter-severity").addEventListener("change", applyAlertFilters);
  document.getElementById("alert-filter-type").addEventListener("change", applyAlertFilters);
}

function startLiveAlertsStream(speed = "200") {
  const startBtn = document.getElementById("ws-start-btn");
  const stopBtn = document.getElementById("ws-stop-btn");
  const statusText = document.getElementById("ws-status-text");

  if (liveWebSocket && liveWebSocket.readyState === WebSocket.OPEN) {
    liveWebSocket.close();
  }

  const wsUrl = `${WS_BASE}/ws/live?speed=${speed}`;
  liveWebSocket = new WebSocket(wsUrl);

  startBtn.disabled = true;
  stopBtn.disabled = false;
  statusText.textContent = `Connecting to ANPR surveillance live stream at ${speed}x speed...`;

  // Reset feed on new stream
  liveAlertsHistory = [];
  liveAlertCounts = { total: 0, blacklist: 0, cloned: 0, curfew: 0, speed: 0 };
  updateAlertCounters();
  document.getElementById("alerts-feed-container").innerHTML = "";

  liveWebSocket.onopen = () => {
    statusText.textContent = `Streaming ANPR sighting events live through AlertEngine (${speed}x)...`;
    showToast("Connected to live surveillance WebSocket feed.", "success");
  };

  liveWebSocket.onmessage = (event) => {
    try {
      const packet = JSON.parse(event.data);

      if (packet.type === "progress") {
        const pct = packet.percent_complete || 0;
        document.getElementById("ws-progress-fill").style.width = `${pct}%`;
        document.getElementById("ws-progress-numbers").textContent = `${packet.events_processed.toLocaleString()} / ${packet.total_events.toLocaleString()} events (${pct}%)`;
        document.getElementById("live-sim-clock").textContent = packet.simulated_clock.substring(11, 19);
      } else if (packet.type === "alert") {
        handleIncomingAlert(packet.data);
      } else if (packet.type === "complete") {
        statusText.textContent = `Replay completed: ${packet.events_processed.toLocaleString()} events, ${packet.total_alerts} alerts raised.`;
        showToast("Surveillance stream replay complete.", "info");
        stopLiveAlertsStream();
      }
    } catch (e) {
      console.warn("WebSocket parse error:", e);
    }
  };

  liveWebSocket.onerror = (err) => {
    console.error("WebSocket error:", err);
    statusText.textContent = "WebSocket connection error. Check server status.";
    showToast("Live stream connection error.", "error");
    stopLiveAlertsStream();
  };

  liveWebSocket.onclose = () => {
    startBtn.disabled = false;
    stopBtn.disabled = true;
  };
}

function stopLiveAlertsStream() {
  if (liveWebSocket) {
    liveWebSocket.close();
    liveWebSocket = null;
  }
  document.getElementById("ws-start-btn").disabled = false;
  document.getElementById("ws-stop-btn").disabled = true;
  document.getElementById("ws-status-text").textContent = "Live stream paused / disconnected.";
}

function handleIncomingAlert(alert) {
  liveAlertsHistory.unshift(alert);

  // Update Counters
  liveAlertCounts.total++;
  const atype = alert.alert_type;
  if (atype === "BLACKLIST") liveAlertCounts.blacklist++;
  else if (atype === "CLONED_PLATE") liveAlertCounts.cloned++;
  else if (atype === "RESTRICTED_ZONE") liveAlertCounts.curfew++;
  else if (atype === "OVERSPEED") liveAlertCounts.speed++;

  updateAlertCounters();
  renderAlertFeedCard(alert, true);
}

function updateAlertCounters() {
  document.getElementById("alert-cnt-total").textContent = liveAlertCounts.total;
  document.getElementById("alert-cnt-blacklist").textContent = liveAlertCounts.blacklist;
  document.getElementById("alert-cnt-cloned").textContent = liveAlertCounts.cloned;
  document.getElementById("alert-cnt-curfew").textContent = liveAlertCounts.curfew;
  document.getElementById("alert-cnt-speed").textContent = liveAlertCounts.speed;
  document.getElementById("nav-alert-counter").textContent = liveAlertCounts.total;
}

function renderAlertFeedCard(alert, prepend = false) {
  const container = document.getElementById("alerts-feed-container");
  const sev = (alert.severity || "LOW").toUpperCase();
  const sevClass = sev === "HIGH" ? "sev-high" : sev === "MEDIUM" ? "sev-medium" : "sev-low";

  const card = document.createElement("div");
  card.className = `alert-feed-item ${sevClass}`;
  card.dataset.severity = sev;
  card.dataset.type = alert.alert_type;
  card.dataset.camera = alert.camera_id;

  const desc = alert.details ? alert.details.message || alert.details.reason || "" : "";
  const timeStr = alert.timestamp ? alert.timestamp.substring(11, 19) : "";

  card.innerHTML = `
    <div class="alert-feed-top">
      <div class="alert-badge-group">
        <span class="sev-badge ${sev.toLowerCase()}">${sev}</span>
        <span class="alert-feed-plate">${alert.plate}</span>
      </div>
      <span class="alert-feed-time">${timeStr}</span>
    </div>
    <div class="alert-feed-desc">${desc}</div>
    <div class="alert-feed-cam">📍 Camera: <strong>${alert.camera_id}</strong> (${alert.alert_type})</div>
  `;

  // Clicking an alert card highlights the camera on the radar map
  card.addEventListener("click", () => {
    document.querySelectorAll(".alert-feed-item").forEach((el) => el.classList.remove("selected"));
    card.classList.add("selected");
    highlightCameraOnRadarMap(alert);
  });

  if (prepend && container.firstChild) {
    container.insertBefore(card, container.firstChild);
  } else {
    container.appendChild(card);
  }
}

function highlightCameraOnRadarMap(alert) {
  const cid = alert.camera_id;
  const cam = camerasById[cid];
  if (!cam || !alertsRadarMap) return;

  document.getElementById("selected-alert-cam-label").innerHTML = `Target: <strong class="text-cyan">${alert.plate}</strong> @ ${cam.name}`;

  if (alertsRadarMarker) {
    alertsRadarMap.removeLayer(alertsRadarMarker);
    alertsRadarMarker = null;
  }

  const radarIcon = L.divIcon({
    className: "custom-radar-wrapper",
    html: `<div class="radar-marker"></div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });

  alertsRadarMarker = L.marker([cam.lat, cam.lon], { icon: radarIcon }).addTo(alertsRadarMap);
  alertsRadarMap.flyTo([cam.lat, cam.lon], 15, { duration: 0.9 });

  const desc = alert.details ? alert.details.message || "" : "";
  alertsRadarMarker.bindPopup(`
    <div class="popup-title">🚨 ${alert.alert_type} Alert</div>
    <div class="popup-row"><span>Severity:</span><span class="popup-val text-rose">${alert.severity}</span></div>
    <div class="popup-row"><span>Plate:</span><span class="popup-val">${alert.plate}</span></div>
    <div class="popup-row"><span>Location:</span><span class="popup-val">${cam.name}</span></div>
    <div class="popup-row"><span>Message:</span><span class="popup-val">${desc}</span></div>
  `).openPopup();
}

function applyAlertFilters() {
  const sevFilter = document.getElementById("alert-filter-severity").value;
  const typeFilter = document.getElementById("alert-filter-type").value;

  const items = document.querySelectorAll(".alert-feed-item");
  items.forEach((item) => {
    const itemSev = item.dataset.severity;
    const itemType = item.dataset.type;

    const matchSev = sevFilter === "ALL" || itemSev === sevFilter;
    const matchType = typeFilter === "ALL" || itemType === typeFilter;

    if (matchSev && matchType) {
      item.classList.remove("hidden");
    } else {
      item.classList.add("hidden");
    }
  });
}


// ==============================================================================
// 7. TAB 5: BLACKLIST WATCHLIST LOGIC
// ==============================================================================
function initBlacklistTab() {
  loadBlacklistRegistry();

  const addForm = document.getElementById("add-blacklist-form");
  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const plateInput = document.getElementById("bl-plate-input");
    const reasonInput = document.getElementById("bl-reason-input");

    const plate = plateInput.value.trim().toUpperCase();
    const reason = reasonInput.value.trim();

    if (!plate || !reason) return;

    try {
      const res = await fetch(`${API_BASE}/api/blacklist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plate, reason }),
      });

      if (!res.ok) throw new Error("Failed to add plate to watchlist.");

      showToast(`Added vehicle ${plate} to security blacklist.`, "success");
      plateInput.value = "";
      reasonInput.value = "";
      loadBlacklistRegistry();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("bl-refresh-btn").addEventListener("click", () => {
    loadBlacklistRegistry();
  });
}

async function loadBlacklistRegistry() {
  const tbody = document.getElementById("blacklist-table-body");
  const countBadge = document.getElementById("bl-active-count");

  try {
    const res = await fetch(`${API_BASE}/api/blacklist`);
    if (!res.ok) throw new Error("Could not load blacklist");
    const items = await res.json();

    countBadge.textContent = `${items.length} Targets`;

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No vehicles currently on the security blacklist.</td></tr>`;
      return;
    }

    tbody.innerHTML = items
      .map(
        (b) => `
        <tr>
          <td><span class="plate-badge-sm">${b.plate}</span></td>
          <td>${b.reason}</td>
          <td><span class="mono text-muted">${b.added_at.substring(0, 10)}</span></td>
          <td><span class="sev-badge high">WANTED</span></td>
          <td class="text-right">
            <button class="btn btn-danger btn-sm" onclick="removeBlacklistPlate('${b.plate}')">
              🗑️ Remove
            </button>
          </td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-rose">Error loading watchlist: ${err.message}</td></tr>`;
  }
}

// Global removal function called by button inline onclick
window.removeBlacklistPlate = async function (plate) {
  if (!confirm(`Are you sure you want to remove plate '${plate}' from the surveillance blacklist?`)) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/blacklist/${encodeURIComponent(plate)}`, {
      method: "DELETE",
    });

    if (!res.ok) throw new Error("Failed to remove plate.");

    showToast(`Removed plate ${plate} from security blacklist.`, "info");
    loadBlacklistRegistry();
  } catch (err) {
    showToast(err.message, "error");
  }
};


// ==============================================================================
// 7. TAB 6: PLATE READER & VIDEO ANPR EVENTS LOGIC
// ==============================================================================
let prCurrentFile = null;

// Global helper to jump from plate reader result to trajectory search tab
window.openPlateInTrajectorySearch = function (plate) {
  if (!plate) return;
  // 1. Switch active nav tab
  const trajTabBtn = document.getElementById("tab-btn-trajectory");
  if (trajTabBtn) trajTabBtn.click();

  // 2. Populate input
  const input = document.getElementById("traj-search-input");
  if (input) {
    input.value = plate.trim();
  }

  // 3. Trigger search
  const searchBtn = document.getElementById("traj-search-btn");
  if (searchBtn) {
    setTimeout(() => searchBtn.click(), 120);
  }
};

async function initPlateReaderTab() {
  const dropzone = document.getElementById("pr-dropzone");
  const fileInput = document.getElementById("pr-file-input");
  const browseBtn = document.getElementById("pr-browse-btn");
  const sampleSelect = document.getElementById("pr-sample-select");
  const readBtn = document.getElementById("pr-read-btn");
  const statusBanner = document.getElementById("pr-status-banner");
  const annotatedImg = document.getElementById("pr-annotated-img");
  const emptyState = document.getElementById("pr-empty-state");
  const detectedTbody = document.getElementById("pr-detected-tbody");
  const resultsBadge = document.getElementById("pr-results-badge");
  const videoFilterPlate = document.getElementById("pr-video-filter-plate");
  const videoFilterCam = document.getElementById("pr-video-filter-cam");
  const videoRefreshBtn = document.getElementById("pr-video-refresh-btn");

  if (!dropzone || !fileInput || !readBtn) return;

  function showStatus(message, type = "info") {
    statusBanner.className = `status-banner ${type}`;
    statusBanner.innerHTML = `<span>${type === "error" ? "❌" : type === "warning" ? "⚠️" : "ℹ️"}</span><div>${message}</div>`;
    statusBanner.style.display = "flex";
  }

  function hideStatus() {
    statusBanner.style.display = "none";
  }

  function setSelectedFile(file, displayName) {
    hideStatus();
    // Validate file type
    const validExtensions = [".jpg", ".jpeg", ".png"];
    const fileName = (file ? file.name : displayName || "").toLowerCase();
    const isValidExt = validExtensions.some((ext) => fileName.endsWith(ext));

    if (!isValidExt) {
      showStatus("Wrong file type. Only JPG and PNG images are supported.", "error");
      prCurrentFile = null;
      readBtn.disabled = true;
      return;
    }

    // Validate 10 MB limit
    if (file && file.size > 10 * 1024 * 1024) {
      showStatus("File too large. Maximum image size is 10 MB.", "error");
      prCurrentFile = null;
      readBtn.disabled = true;
      return;
    }

    prCurrentFile = file;
    readBtn.disabled = false;

    const promptEl = dropzone.querySelector(".dropzone-prompt");
    if (promptEl) {
      promptEl.innerHTML = `Selected: <strong class="text-cyan">${file ? file.name : displayName}</strong>`;
    }
  }

  // 1. File Upload Dropzone Listeners
  if (browseBtn) {
    browseBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  });

  // 2. Load 10 Sample Test Images
  try {
    const res = await fetch(`${API_BASE}/api/plates/sample-images`);
    if (res.ok) {
      const data = await res.json();
      sampleSelect.innerHTML = '<option value="">-- Choose from 10 sample test images --</option>';
      data.samples.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.url;
        opt.textContent = `${s.name} (${s.filename})`;
        sampleSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn("Could not load sample test images:", err);
  }

  // Handle sample select change
  sampleSelect.addEventListener("change", async (e) => {
    const url = e.target.value;
    if (!url) return;
    try {
      showStatus("Loading sample test photo...", "info");
      const resp = await fetch(url);
      if (!resp.ok) throw new Error("Could not load sample photo.");
      const blob = await resp.blob();
      const filename = url.split("/").pop();
      const file = new File([blob], filename, { type: blob.type || "image/jpeg" });
      setSelectedFile(file, filename);
      hideStatus();
    } catch (err) {
      showStatus(`Error loading sample: ${err.message}`, "error");
    }
  });

  // 3. Run Plate Reader on Click
  readBtn.addEventListener("click", async () => {
    if (!prCurrentFile) return;

    readBtn.disabled = true;
    readBtn.innerHTML = "<span>⏳</span> Running AI Reader...";
    hideStatus();

    const formData = new FormData();
    formData.append("file", prCurrentFile);

    try {
      const resp = await fetch(`${API_BASE}/api/plates/read`, {
        method: "POST",
        body: formData,
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Plate reading request failed.");
      }

      if (data.detected_count === 0) {
        showStatus("No license plate detected in this image.", "warning");
        resultsBadge.textContent = "0 Plates Detected";
        resultsBadge.className = "badge-pill";
        annotatedImg.style.display = "none";
        emptyState.style.display = "block";
        detectedTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No license plates found in the analyzed frame.</td></tr>`;
      } else {
        resultsBadge.textContent = `${data.detected_count} Plate(s) Detected`;
        resultsBadge.className = "badge-pill";
        emptyState.style.display = "none";
        annotatedImg.src = data.annotated_image_base64;
        annotatedImg.style.display = "block";

        detectedTbody.innerHTML = data.plates
          .map((p) => {
            const blBadge = p.is_blacklisted
              ? `<span class="badge-pill" style="background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid #ef4444;" title="${p.blacklist_reason || 'Wanted'}">🚨 BLACKLISTED</span>`
              : `<span class="badge-pill" style="background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981;">✅ CLEAN</span>`;

            const sightingsLabel = p.known_sightings > 0
              ? `<span class="text-cyan font-bold">${p.known_sightings.toLocaleString()} sightings</span>`
              : `<span class="text-muted">0 sightings</span>`;

            const actionBtn = p.known_sightings > 0
              ? `<button class="btn btn-primary btn-sm" onclick="openPlateInTrajectorySearch('${p.plate}')">🗺️ Reconstruct Trajectory</button>`
              : `<button class="btn btn-secondary btn-sm" onclick="openPlateInTrajectorySearch('${p.plate}')" title="Check network history">🔍 Search History</button>`;

            return `
              <tr>
                <td><span class="plate-badge-sm">${p.plate}</span></td>
                <td><strong class="text-cyan">${Math.round(p.detector_confidence * 100)}%</strong></td>
                <td><strong class="text-emerald">${Math.round(p.ocr_confidence * 100)}%</strong></td>
                <td>${blBadge}</td>
                <td>${sightingsLabel}</td>
                <td class="text-right">${actionBtn}</td>
              </tr>
            `;
          })
          .join("");

        showToast(`Successfully detected ${data.detected_count} license plate(s)!`, "success");
      }
    } catch (err) {
      showStatus(err.message, "error");
      showToast(err.message, "error");
    } finally {
      readBtn.disabled = false;
      readBtn.innerHTML = "<span>🔍</span> Read Plate";
    }
  });

  // 4. Load Video ANPR Events Table
  async function loadVideoEvents() {
    const tbody = document.getElementById("pr-video-events-tbody");
    if (!tbody) return;

    const plateVal = videoFilterPlate ? videoFilterPlate.value.trim() : "";
    const camVal = videoFilterCam ? videoFilterCam.value.trim() : "";

    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Loading video events...</td></tr>`;

    try {
      let url = `${API_BASE}/api/events?source=video&limit=50`;
      if (plateVal) url += `&plate=${encodeURIComponent(plateVal)}`;
      if (camVal) url += `&camera=${encodeURIComponent(camVal)}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load video events.");
      const data = await res.json();

      if (!data.events || data.events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No video events recorded yet. Run 'python ingest_video_events.py' to import video detections.</td></tr>`;
        const titleEl = document.getElementById("pr-video-events-title");
        if (titleEl) titleEl.textContent = "📹 Video ANPR Events";
        return;
      }

      // Update title to 'Video ANPR Events (voted)' only when n_frames > 1
      const titleEl = document.getElementById("pr-video-events-title");
      if (titleEl) {
        const hasVoted = data.events.some((ev) => ev.n_frames && ev.n_frames > 1);
        titleEl.textContent = hasVoted ? "📹 Video ANPR Events (voted)" : "📹 Video ANPR Events";
      }

      tbody.innerHTML = data.events
        .map((ev) => {
          const cropUrl = ev.best_crop_path ? `/${ev.best_crop_path}` : "";
          const imgEl = cropUrl
            ? `<img src="${cropUrl}" class="crop-thumbnail" alt="${ev.plate}" title="Click to view crop" onclick="window.open('${cropUrl}','_blank')" onerror="this.parentElement.innerHTML='<span class=\\'text-muted\\'>N/A</span>'" />`
            : `<span class="text-muted">N/A</span>`;

          const marginDisplay = ev.vote_margin != null ? Number(ev.vote_margin).toFixed(2) : "--";
          const ocrConfDisplay = ev.ocr_confidence != null ? `${(Number(ev.ocr_confidence) * 100).toFixed(1)}%` : "--";

          return `
          <tr>
            <td>${imgEl}</td>
            <td><span class="plate-badge-sm">${ev.plate}</span></td>
            <td><span class="text-cyan font-bold">${ev.camera_id}</span></td>
            <td class="text-muted" style="font-size: 0.8rem;">${ev.timestamp.replace("T", " ").slice(0, 19)}</td>
            <td><strong class="text-purple">${ev.n_frames || 1} frame(s)</strong></td>
            <td><span class="text-emerald font-bold">${marginDisplay}</span></td>
            <td><strong class="text-cyan">${ocrConfDisplay}</strong></td>
            <td class="text-right">
              <button class="btn btn-secondary btn-sm" onclick="openPlateInTrajectorySearch('${ev.plate}')" title="Reconstruct vehicle path">
                🗺️ Trajectory
              </button>
            </td>
          </tr>
        `;
        })
        .join("");
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-rose">Error loading video events: ${err.message}</td></tr>`;
    }
  }

  if (videoRefreshBtn) {
    videoRefreshBtn.addEventListener("click", () => loadVideoEvents());
  }
  if (videoFilterPlate) {
    videoFilterPlate.addEventListener("input", () => loadVideoEvents());
  }
  if (videoFilterCam) {
    videoFilterCam.addEventListener("input", () => loadVideoEvents());
  }

  // Initial load of video events
  loadVideoEvents();
}


// ==============================================================================
// 8. MASTER INITIALIZATION ON DOM CONTENT LOADED
// ==============================================================================
document.addEventListener("DOMContentLoaded", () => {
  console.log("Initializing City ANPR Command Dashboard...");
  initNavigation();
  initOverviewTab();
  initTrajectoryTab();
  initHeatmapTab();
  initLiveAlertsTab();
  initBlacklistTab();
  initPlateReaderTab();
});
