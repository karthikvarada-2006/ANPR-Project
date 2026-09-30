# Module 9: City Traffic Command Dashboard (`frontend/`)

The **Frontend** is an interactive, real-time command-and-control dashboard built with modern web technologies (React / Vite) for traffic authorities and operators.

## 🎯 Key Objectives

1. **Interactive City Map**:
   - Renders the urban road network with interactive camera markers.
   - Click any camera to view live feeds, recent sightings, and passage statistics.
2. **Trajectory Visualization**:
   - Visualizes vehicle paths traced across multiple cameras.
   - Time-slider playback to reconstruct a target vehicle's historic journey through the city.
3. **Traffic Heatmaps & Flow Layers**:
   - Color-codes road segments based on congestion, average speed, and density.
   - Highlights traffic choke points in real time.
4. **Live Alert Center**:
   - Instant notifications for watchlist hits (wanted/stolen plates) and speed violations.
   - Audio-visual indicators with quick inspection of vehicle snapshot and route.
5. **Analytics Charts**:
   - Origin-Destination flow charts, peak-hour distributions, and vehicle-type breakdowns.

## 🛠️ Tech Stack

- **React 18+** / **Vite**
- **MapLibre GL / Leaflet** for geospatial rendering
- **Recharts / Chart.js** for analytical graphs
- **Lucide Icons** & **TailwindCSS / Vanilla CSS** for modern aesthetics
