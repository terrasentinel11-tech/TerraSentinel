# BLACK PIXEL — React Dashboard

A React + Vite implementation of all **12 dashboard screens** from the supplied BLACK PIXEL PDF set.

## Run

Requirements: Node.js 20+ and npm.

```bash
npm install
npm run dev
```

Open the URL Vite prints (normally `http://localhost:5173`). To build for production:

```bash
npm run build
npm run preview
```

## Included pages

1. Command Center
2. Attack Terminal
3. Satellite Monitor
4. TCP Network Operations
5. Attack Arsenal
6. Image Laboratory
7. Defense Intelligence
8. Experiments
9. Dataset Manager
10. Analytics & Reports
11. Mission Replay
12. System Settings

## Working frontend interactions

- Sidebar navigation and URL hashes for all 12 pages; responsive desktop/mobile layout.
- Terminal documentation browser, searches, command insertion and local **documentation** history. Nothing is executed on the host.
- Local Settings form and browser-only saving of non-secret configuration drafts via `localStorage`.
- Browser file upload of local JPEG / PNG / TIFF / WebP / GIF images (50 files at a time, 25 MB maximum each).
- Browser SHA-256 for imported images (where supported), original-image preview, download, JSON manifest export, dataset filters and searches.
- Tabs, navigation shortcuts, stage selection, filters and report section options.

## Intentionally not simulated

**No satellite, TCP relay, ground station, attack engine, replay service, experiment database or authorization/audit backend is included.** Until the corresponding adapters and authenticated backend are integrated, operational actions are disabled and results remain unavailable. The UI does not claim that attacks, checks, captures, bypasses or network transfers have happened.

To integrate the real project, create a typed API client for your own authorized endpoints (e.g. `GET /api/status`, `GET /api/registry`, `GET /api/events`, `GET /api/experiments`, `POST /api/experiments`), authenticated access controls, WebSocket event subscriptions, input validation and correlation IDs. Do not store secrets, private signing keys or authorization tokens in browser `localStorage`.

## Source layout

- `src/App.jsx`: app shell, shared components, 12 dashboard screens and local-only interactions.
- `src/styles.css`: original dark visual system and responsive grid.
- `src/main.jsx`: React entry.

Dependencies: React 19, Vite 6 and Lucide React.
