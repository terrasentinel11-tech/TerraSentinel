# PDF → React conversion notes

Source: user-provided ZIP containing 12 one-page BLACK PIXEL PDF interface designs, dated 2026-11-03.

| Source PDF | React route |
|---|---|
| Mission Overview.pdf | `#/overview` |
| Satellite Operations.pdf | `#/satellite` |
| Camera & Payload.pdf | `#/camera` |
| Image Transmission.pdf | `#/transmission` |
| Ground Station Operations.pdf | `#/ground` |
| Defense Engine.pdf | `#/defense` |
| Security Alerts.pdf | `#/alerts` |
| Image Forensics.pdf | `#/forensics` |
| Mission Timeline.pdf | `#/timeline` |
| Analytics & Reports.pdf | `#/analytics` |
| System Diagnostics.pdf | `#/diagnostics` |
| Settings.pdf | `#/settings` |

All source PDFs were 1600-pt-wide, single-page design mockups. The implementation retains the shared top bar, telemetry strip, 12-page navigation, four-transfer simulated test fixture, typography hierarchy, colors, tables, notices, indicators and footer. Content is recreated as responsive DOM and React components, not PDF images.

Specific limitations: PDF inputs contain no real camera/image bytes; no runnable hardware/backend repositories, protocol contract, auth service, WebSocket or TCP receiver were included. UI elements requiring these external capabilities are intentionally demo-only and surface an explanatory notification. Generated reports use the explicitly labeled fixture data.

Offline QA completed: all JSX/JS files passed the TypeScript JS/JSX syntax parser and transpilation with zero diagnostics. Browser/runtime build was not performed in this sandbox because the npm package registry could not be resolved (`EAI_AGAIN`). Run `npm install` and `npm run build` on a machine with internet access before deployment.
