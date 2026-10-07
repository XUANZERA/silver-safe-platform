# Vue 3 + Vite

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).

## Local REAL and DEMO development

Run these commands from `frontend/`:

```powershell
npm run dev:real
npm run dev:demo
```

Both commands bind only to `127.0.0.1:5173` and fail if that port is already
in use. Open `http://127.0.0.1:5173/#/login`; avoid `localhost`, which may
resolve to the separate IPv6 loopback address `::1`.

`dev:real` always sets `VITE_API_BASE_URL` to
`http://127.0.0.1:8000/api/v1`. `dev:demo` always clears it. These commands
use Vite's `real` and `demo` modes and override an inherited shell value so the
selected mode is repeatable. The plain `npm run dev` command is an alias for
DEMO mode.
