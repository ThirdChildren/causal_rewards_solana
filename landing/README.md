# Causal Rewards Protocol landing

Single page site presenting the Causal Rewards Protocol MVP concept note, built for the Solana Foundation grant submission.

Stack: React 19, TypeScript, Vite 7, Tailwind CSS v4.

## Local development

```bash
npm install
npm run dev
```

## Production build

```bash
npm run build      # type checks, then emits static assets to dist/
npm run preview    # serves the built dist/ locally
```

The `dist/` folder is fully static and can be dropped on any host (Vercel, Netlify, Cloudflare Pages, GitHub Pages). Use the deployed URL in the grant form.

## Structure

- `src/App.tsx` composes the page sections in order.
- `src/components/` holds one file per section plus shared UI primitives in `ui.tsx`.
- `src/index.css` defines the Tailwind v4 theme tokens (colors, fonts).
