# AlphaNestAgent Frontend

React UI for AlphaNestAgent. The frontend runs separately from the Python backend during development.

## Development Setup

Start the Python backend from the project root:

```bash
uv run python agent_web_api.py
```

The backend listens on:

```txt
http://127.0.0.1:8000
```

Then start the React frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on:

```txt
http://127.0.0.1:5173
```

## API Connection

The frontend calls the backend configured in `src/main.jsx`:

```js
const API_URL = "http://127.0.0.1:8000";
```

Main endpoints:

```txt
GET  /health
POST /chat
POST /reset
```

## Scripts

```bash
npm run dev      # Start Vite dev server
npm run build    # Build production assets into dist/
npm run preview  # Preview the production build
```

## Notes

- Keep the Python backend running while using the React UI.
- If the frontend shows request errors, check that `agent_web_api.py` is running on port `8000`.
- If backend code changes, restart the Python backend.
- If frontend code changes, Vite reloads the page automatically.
