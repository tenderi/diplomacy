# Frontend UI framework: Tailwind CSS + shadcn/ui

## Decision

Use **Tailwind CSS** and **shadcn/ui** for the browser client UI. Keep the current stack: **React 18, Vite, TypeScript, React Router**. The backend remains **FastAPI**; no change to API contracts.

This spec documents the decision, scope, and what should be done.

---

## Rationale

- **Current state:** React + Vite + TypeScript SPA with inline styles and minimal structure. Works, but looks basic and is brittle for layout and error states.
- **Goal:** A consistent, maintainable UI that looks and behaves like a proper product, without replacing the framework or backend.
- **Why Tailwind + shadcn/ui:**
  - **Tailwind:** Utility-first CSS, small bundle, no runtime. Fits Vite and component-based React. Easy to adopt incrementally.
  - **shadcn/ui:** Copy-paste components (Button, Input, Card, Dialog, Toast, etc.) into the repo; full control, no heavy dependency. Built on Radix primitives (accessibility), styled with Tailwind. Aligns with the “optionally shadcn/ui” note in `browser_client_plan.md` §6.
- **Alternatives considered:** MUI (heavier, Material look); Chakra (good but smaller ecosystem); Ant Design (very opinionated). For a small/medium app and a single FastAPI backend, Tailwind + shadcn is a good fit.

---

## Scope

- **In scope:** Add Tailwind and shadcn to the existing `frontend/` app. Migrate or rebuild pages to use shared components and Tailwind utilities. Improve layout, forms, feedback (errors, loading, toasts).
- **Out of scope:** Changing backend (FastAPI), auth flow, or API design. No SSR/meta-framework (Next/Remix) unless required later.

---

## Current frontend stack (reference)

- React 18, React DOM, React Router DOM  
- Vite 5, TypeScript 5.6  
- React Hook Form, Zod, @hookform/resolvers  
- No CSS framework or component library today  

---

## What should be done

### Phase 1: Setup

1. **Add Tailwind CSS**
   - Install `tailwindcss`, `postcss`, `autoprefixer`.
   - Add `tailwind.config.js` and `postcss.config.js` (content: `./index.html`, `./src/**/*.{ts,tsx}`).
   - Introduce a root CSS file (e.g. `src/index.css`) with Tailwind directives; import it in `main.tsx`.
   - Verify build and dev still work; optionally convert one existing page to Tailwind utilities only (no shadcn yet) to confirm.

2. **Add shadcn/ui**
   - Follow [shadcn/ui installation](https://ui.shadcn.com/docs/installation) for Vite + React + TypeScript.
   - Run `npx shadcn@latest init`: choose style (e.g. Default), base color (e.g. Slate or Zinc), CSS variables, no `src/` alias conflict with existing setup.
   - Ensure `components.json` is created and that Tailwind content paths include the new `components/ui` (or chosen) directory.
   - Add a minimal set of components: e.g. `Button`, `Input`, `Card`, `Label` via `npx shadcn@latest add button input card label`. Verify they render.

3. **Documentation**
   - In `frontend/README.md` (or equivalent): note that the UI uses Tailwind + shadcn; add one-line “add a new component” instruction (`npx shadcn@latest add <component>`).
   - Optionally add a short “UI components” section in `docs/BROWSER_CLIENT.md` or in this spec.

### Phase 2: Migrate core flows

4. **Layout and shell**
   - Define a simple app layout (e.g. header with nav, main content area) using Tailwind + shadcn `Card` or plain divs. Ensure responsive behavior (e.g. padding, max-width).
   - Use the layout in the root route or a layout route so all pages share it.

5. **Auth pages (Register, Login)**
   - Replace raw `<input>` and `<button>` with shadcn `Input`, `Label`, `Button`.
   - Use Tailwind for spacing, typography, and error text. Keep existing React Hook Form + Zod logic; only swap presentational pieces.
   - Show validation and API errors clearly (e.g. under fields or in a small `Alert`).

6. **Home and navigation**
   - Home links (e.g. “My games”, “Link Telegram”, “Register/Login”) as shadcn `Button` or styled links with Tailwind.
   - Consistent spacing and hierarchy.

7. **Game list**
   - “Create new game” as shadcn `Button`. List of games in `Card` or a simple table/list with Tailwind. Loading and error states using existing state; present with Tailwind + optional `Alert` or inline message.

8. **Game view**
   - Same layout shell. Map image, phase info, and controls (Join, Orders, Process turn, Messages) with shadcn `Button`, `Select`, `Textarea` where appropriate. Error and loading states visible (reuse the “error + Back to games” behavior already added).

9. **Link Telegram and other minor pages**
   - Same pattern: shadcn form controls + Tailwind. Optional: toast (shadcn `Sonner` or `Toast`) for “Link code generated” or similar.

### Phase 3: Polish and consistency

10. **Toasts / feedback**
    - Add shadcn toast (e.g. Sonner) for success/error feedback (e.g. “Game created”, “Orders submitted”, “Failed to load”).
    - Replace or complement inline error text where it improves UX.

11. **Accessibility and theming**
    - Rely on Radix/shadcn defaults for focus and ARIA. Optionally add a theme toggle (light/dark) using CSS variables already set by shadcn init.
    - Ensure form labels and error messages are associated correctly.

12. **Cleanup**
    - Remove redundant inline styles from migrated components. Standardize on Tailwind + shadcn tokens. No duplicate CSS files unless needed for a specific override.

---

## Dependencies to add (reference)

- **Tailwind:** `tailwindcss`, `postcss`, `autoprefixer` (dev).
- **shadcn/ui:** Installed via CLI; brings in Radix UI primitives and `class-variance-authority`, `clsx`, `tailwind-merge` as needed. No single “shadcn” package; components live in repo.
- **Optional:** `lucide-react` (icons) if shadcn init adds it or components use it.

Exact versions should be decided at implementation time (e.g. latest compatible with current React/Vite).

---

## Success criteria

- All existing flows still work: register, login, link Telegram, game list, create game, game view, orders, messages.
- UI uses Tailwind utilities and shadcn components consistently; no or minimal inline styles in migrated pages.
- Errors and loading states are visible and understandable.
- Build and dev scripts unchanged from a consumer perspective (`npm run dev`, `npm run build`).
- Docs updated (frontend README and optionally BROWSER_CLIENT / this spec).

---

## References

- [Tailwind CSS](https://tailwindcss.com/docs/installation)
- [shadcn/ui](https://ui.shadcn.com/) — Installation, components, theming.
- `specs/browser_client_plan.md` — Frontend stack and goals (§6).
- `docs/BROWSER_CLIENT.md` — Run and use the browser client.
