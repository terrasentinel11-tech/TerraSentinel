# BLACK PIXEL — React Dashboard

React recreation of the **12-page BLACK PIXEL Satellite & Ground Station Command Center** PDF design package.

## Quick start

Requirements: Node.js 20.19+ or 22.12+ and npm.

```bash
npm install
npm run dev
```

Open the URL shown by Vite (usually http://localhost:5173).

Production build:

```bash
npm run build
npm run preview
```

## Included routes

1. Mission Overview — `#/overview`
2. Satellite Operations — `#/satellite`
3. Camera & Payload — `#/camera`
4. Image Transmission — `#/transmission`
5. Ground Station Operations — `#/ground`
6. Defense Engine — `#/defense`
7. Security Alerts — `#/alerts`
8. Image Forensics — `#/forensics`
9. Mission Timeline — `#/timeline`
10. Analytics & Reports — `#/analytics`
11. System Diagnostics — `#/diagnostics`
12. Settings — `#/settings`

## Project structure

- `src/App.jsx`: navigation, reusable dashboard components, all 12 screens, event filters, downloads and demo controls.
- `src/fixtures.js`: clearly labeled four-transfer dataset from PDF.
- `src/styles.css`: responsive dark command-center UI.
- `src/main.jsx`: React bootstrap.

## Behaviors

- Sidebar navigation, image/alert selection, event filtering/search, JSONL/CSV/JSON exports and copy action are implemented.
- Settings mode selection changes **local frontend preview state only**; the demo pages continue to show simulated data.
- Controls requiring actual devices, permission enforcement or persistence produce explanatory notifications. They do **not** claim to send commands to a satellite or ground station.
- No backend, real authentication, WebSocket, Raspberry Pi adapter, TCP receiver or content anomaly model is supplied by the PDFs.
- Forensic image panels intentionally remain unavailable; the source PDFs did not supply actual satellite image bytes.

## Connecting real systems later

Keep the direct Satellite → Ground TCP path independent from frontend monitoring. Build a separate authorized backend adapter with explicit protocol/event contracts, verification evidence, persistent audit logging, authorization and reconnection handling. Do not promote simulated evidence to live values. `src/fixtures.js` is the demonstration fixture to replace when real adapters exist.

## Fidelity note

This is a **responsive, coded recreation** of the PDF interface and its text/data, not an embedded PDF, screenshot, automatic SVG export or pixel-perfect raster clone. The supplied design surfaces have different page heights; React cards reflow based on screen width and content.
