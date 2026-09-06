# FPL Pi Manager · Gaffer room

Issue #58 is a read-only browser prototype for seeing the gaffer and the season snapshot at a glance. It uses a deliberately small Vite + TypeScript setup so the Pi remains responsible for data and the browser handles presentation.

## Run locally

```sh
npm install
npm run dev
```

Open the local Vite URL. The gameweek cards are interactive: choose a GW or use the previous/next controls to update the score summary, match log, captain call, and squad points. Data is currently canned in `src/main.ts`, based on the committed `season-state.json`; a real snapshot feed can replace that seam later.

The dashboard is read-only. Approvals and transfers remain in Telegram.
