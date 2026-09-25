# Frontend testing

**Vitest** + **React Testing Library**, on the existing Vite + React + TypeScript setup.

## Commands

- `npm run test` — watch mode
- `npm run test:run` — single run
- `npm run test:coverage` — single run with the coverage thresholds CI enforces
  (`frontend/vite.config.ts`: lines and statements 90, functions 85, branches 77)

## Test utilities

- **`src/test/setup.ts`** — loads the `@testing-library/jest-dom` matchers
  (`toBeInTheDocument()`, `toBeDisabled()`, …).
- **`src/test/test-utils.tsx`** — `renderWithProviders(ui, options?)` wraps in `MemoryRouter`
  and `AuthProvider` and re-exports `screen`, `fireEvent`, `waitFor`, `within`;
  `routerProps.initialEntries` sets the route.
- **`src/test/mocks/api.ts`** — `createMockFetch()`, `mockFetchJsonResponse()`,
  `mockFetchTextResponse()`, `stubGlobalFetch()`.

## Mocking the API and auth

- **API:** stub global `fetch` (`vi.stubGlobal('fetch', …)`) and match on the URL to return a
  payload per endpoint. Reset with `clearTokens()` and fresh stubs in `beforeEach`. Never hit
  the network.
- **Auth:** for the real flow use `AuthProvider` and stub `/auth/login`, `/auth/me`,
  `/auth/refresh`. For a fixed user, wrap in `<AuthContext.Provider value={…}>`.
- **Routes with parameters:** a `/games/:id` page must be rendered inside
  `<Routes><Route path="/games/:gameId" …>`. A bare `MemoryRouter` leaves `useParams()`
  unresolved, so the test only ever sees the loading spinner and passes without testing
  anything.

## Test file map

| File | Covers |
|------|--------|
| `src/api/client.test.ts` | `errorDetailToMessage`, token helpers, `apiJson`/`apiFetch`, the 401 refresh flow |
| `src/lib/orderParsing.test.ts` | Parsing and grouping legal orders for the order builder |
| `src/lib/provinceNames.test.ts` | Province display names |
| `src/lib/resultText.test.ts` | Human-readable order results |
| `src/contexts/AuthContext.test.tsx` | Loading, login, logout, refresh |
| `src/App.test.tsx` | `ProtectedRoute` redirect and protected content |
| `src/components/AppLayout.test.tsx` | Nav when logged out and in, the source-code link |
| `src/components/MapViewer.test.tsx` | The inline map and its full-size dialog, keyboard access |
| `src/pages/Home.test.tsx` | Logged-out and logged-in home |
| `src/pages/Login.test.tsx`, `Register.test.tsx` | Forms, validation, API errors, navigation |
| `src/pages/ForgotPassword.test.tsx`, `ResetPassword.test.tsx` | The reset flow |
| `src/pages/LinkTelegram.test.tsx` | Code generation and the already-linked state |
| `src/pages/GameList.test.tsx` | Game lists, empty state, creating a game |
| `src/pages/GameView.test.tsx` | The game page: board views, order building and submission, results, retreats and builds, seats, joining, draw votes, wait flags, messages |

## What to test

- **Our logic and our pages.** The `src/components/ui/*` shadcn primitives are third-party
  code; don't write tests for them.
- **Assert what the user sees:** query by role, label or text (`getByRole`,
  `getByLabelText`), and assert the exact text or request body, not just that something
  rendered.
- **Every test must be able to fail.** A new test should fail without the change it covers.
