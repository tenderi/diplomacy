# Frontend testing

The frontend uses **Vitest** for unit/component tests and **React Testing Library** for rendering and querying components. This fits the existing Vite + React + TypeScript setup.

## Commands

- `npm run test` — run tests in watch mode
- `npm run test:run` — single run (CI)
- `npm run test:coverage` — run with coverage report

## Test utilities

- **`src/test/setup.ts`** — imports `@testing-library/jest-dom/vitest` for matchers like `toBeInTheDocument()`, `toBeDisabled()`.
- **`src/test/test-utils.tsx`** — `renderWithProviders(ui, options?)` wraps with `MemoryRouter` and `AuthProvider`; re-exports `screen`, `fireEvent`, `waitFor`, `within`. Use for component/page tests that need router and auth. Optional `routerProps.initialEntries` for route.
- **`src/test/mocks/api.ts`** — helpers: `createMockFetch()`, `mockFetchJsonResponse()`, `mockFetchTextResponse()`, `stubGlobalFetch()` for stubbing `fetch` in tests.

## Mocking API and auth

- **API:** Stub global `fetch` with `vi.stubGlobal('fetch', vi.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve({...}) })))`. Match on `url.includes('/path')` to return different payloads per endpoint. Reset with `clearTokens()` and fresh stubs in `beforeEach`.
- **Auth:** For real auth flow use `AuthProvider` and stub `fetch` for `/auth/login`, `/auth/me`, `/auth/refresh`. For a fixed user, wrap with `<AuthContext.Provider value={{ user: mockUser, loading: false, login, logout, ... }}>` (export `AuthContext` from `AuthContext.tsx`). Stub `localStorage` in tests that need refresh-token behaviour.

## Test file map

| File | Coverage |
|------|----------|
| `src/api/client.test.ts` | `errorDetailToMessage`, token helpers, `apiJson`/`apiFetch`, 401 refresh flow |
| `src/lib/orderParsing.test.ts` | `parseLegalOrder`, `groupLegalOrdersByType`, `getOrderTypesFromGrouped`, `getTargetOptionsForType`, `extractUnitFromOrderString` |
| `src/lib/utils.test.ts` | `cn()` merge and Tailwind override behaviour |
| `src/components/ui/button.test.tsx` | Button render, onClick, disabled |
| `src/components/ui/input.test.tsx` | Input value, onChange, disabled, label association |
| `src/components/ui/label.test.tsx` | Label render, htmlFor association |
| `src/components/ui/card.test.tsx` | Card, CardHeader, CardTitle, CardContent, CardDescription |
| `src/components/ui/alert.test.tsx` | Alert role, variants, AlertTitle/AlertDescription |
| `src/components/ui/select.test.tsx` | Select trigger, placeholder, combobox |
| `src/components/ui/textarea.test.tsx` | Textarea value, onChange, disabled |
| `src/contexts/AuthContext.test.tsx` | Loading/user when no refresh, login sets user, logout clears user |
| `src/App.test.tsx` | ProtectedRoute redirect when unauthenticated, protected content when user set |
| `src/components/AppLayout.test.tsx` | Nav links when logged out/in, loading in nav |
| `src/pages/Home.test.tsx` | Login/Register when logged out, greeting and nav when logged in, loading |
| `src/pages/Login.test.tsx` | Form render, error on failure, navigate home on success |
| `src/pages/Register.test.tsx` | Form render, client validation (password length), error on API failure |
| `src/pages/ForgotPassword.test.tsx` | Form render, success message after submit, error on failure |
| `src/pages/ResetPassword.test.tsx` | Invalid link when no token, form when token present, password mismatch, success message |
| `src/pages/LinkTelegram.test.tsx` | Heading and generate code, code display on success, already-linked state |
| `src/pages/GameList.test.tsx` | Loading then content, empty state and Create button, my games list, create API call |
| `src/pages/GameView.test.tsx` | Renders and shows loading initially |

## What to test

### 1. Pure logic (unit tests)

- **`src/lib/orderParsing.ts`** — `parseLegalOrder`, `groupLegalOrdersByType`, `getOrderTypesFromGrouped`, `extractUnitFromOrderString`, etc. No mocks needed; fast and stable.
- **`src/lib/utils.ts`** — e.g. `cn()` if you add more helpers.
- **API helpers** — `errorDetailToMessage` in `src/api/client.ts` can be unit-tested by exporting it (or testing via `apiJson` with mocked `fetch`).

### 2. React components (component tests)

- **UI primitives** (`src/components/ui/*`) — render with different props, assert labels, disabled state, and `onClick`/`onChange`.
- **Pages** — wrap with required providers (`AuthProvider`, `BrowserRouter`) and mock `useAuth` or API:
  - Login/Register: mock `login`/`register`, fill form, submit, assert navigation or error.
  - GameList / GameView: mock `apiJson` or `apiFetch`, render, assert loading and list content.
- **ProtectedRoute** — render with/without user, assert redirect to `/login` or children.

### 3. Context and hooks

- **AuthContext** — render `AuthProvider` with a test wrapper that mocks `apiJson`/`fetch` for `/auth/me` and `/auth/login`; assert `user`, `loading`, and that `login`/`logout` update state.

## Patterns

- Use **React Testing Library** queries: `getByRole`, `getByLabelText`, `getByPlaceholderText` to reflect how users interact.
- Mock **API** with `vi.stubGlobal('fetch', …)` or by injecting a small API wrapper; avoid real network in tests.
- For **router**: wrap the component in `<MemoryRouter>` or `<BrowserRouter>` and use `useNavigate()`; for assertions use a test router or check `window.location`.
- For **AuthContext**: create a wrapper that provides `AuthProvider` (and optionally a mock auth state) so pages and `ProtectedRoute` behave as in the app.

## Optional: E2E tests

For full user flows (e.g. login → open game list → open a game), add **Playwright** or **Cypress** in a separate step. These run against the built app and a real or mocked backend. Start with Vitest + RTL for speed and stability, then add E2E for a few critical paths.
