import {
  Component,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { ArrowRight, LogOut, Moon, Sun } from "lucide-react";
import "@fontsource/geist/400.css";
import "@fontsource/geist/500.css";
import "@fontsource/geist/700.css";
import "@fontsource/geist-mono/400.css";
import { Client, type Me } from "./api";
import { CaseFile } from "./CaseFile";
import { Intake } from "./Intake";
import { Queue } from "./Queue";
import { Badge, ErrorNotice } from "./ui";
import "./style.css";

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    /* No source content or credentials in console telemetry. */
  }
  render() {
    return this.state.failed ? (
      <main id="main">
        <h1>Response needs review</h1>
        <p>
          An API record could not be rendered safely. No financial action has
          been taken.
        </p>
        <button onClick={() => window.location.reload()}>
          Reload application
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
function Mark() {
  return (
    <svg
      width="29"
      height="29"
      viewBox="0 0 29 29"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 4H4v21h8M17 4h8v21h-8M9 11h11M9 18h11"
        stroke="currentColor"
        strokeWidth="1.8"
      />
    </svg>
  );
}
function FocusRoute() {
  const location = useLocation();
  useEffect(() => {
    document.title = `ClearLedger · ${location.pathname.startsWith("/cases/") ? "Case file" : location.pathname === "/intake" ? "Import & documents" : "Exception register"}`;
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>("h1")?.focus(),
    );
  }, [location.pathname]);
  return null;
}
function App() {
  const [session, setSession] = useState<{ api: Client; me: Me }>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("clearledger-theme") || "light";
    } catch {
      return "light";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("clearledger-theme", theme);
    } catch {
      /* Preferences are optional. */
    }
  }, [theme]);
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(undefined);
    const form = new FormData(e.currentTarget);
    try {
      const result = await new Client("").request<{ access_token: string }>(
        "/review/demo/login",
        "POST",
        { username: form.get("username"), password: form.get("password") },
      );
      const api = new Client(result.access_token),
        me = await api.request<Me>("/review/me");
      if (
        !["AR_ANALYST", "CONTROLLER", "AUDITOR"].includes(me.role) ||
        me.financial_authority !== false
      )
        throw new Error("Invalid session");
      setSession({ api, me });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    try {
      await session?.api.request("/review/demo/logout", "POST", {});
    } catch {
      setError(new Error("Server session revocation unavailable"));
    } finally {
      setSession(undefined);
    }
  }
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to case content
      </a>
      <header className="app-header">
        <Link to="/" className="brand">
          <Mark />
          <span>ClearLedger</span>
          <small>Receivables workstation</small>
        </Link>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            Exceptions
          </NavLink>
          <NavLink to="/intake">Import & documents</NavLink>
        </nav>
        <div className="session-controls">
          <button
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            aria-label={theme === "light" ? "Use dark mode" : "Use light mode"}
          >
            {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
          </button>
          {session && (
            <>
              <Badge>
                {session.me.authority === "LOCAL_DEMO_ONLY"
                  ? "Local synthetic session"
                  : "Verified review session"}
              </Badge>
              <button onClick={() => void logout()}>
                <LogOut size={15} aria-hidden="true" />
                <span>Sign out</span>
              </button>
            </>
          )}
        </div>
      </header>
      {!session ? (
        <main id="main" className="login-page">
          <section className="login-explanation">
            <span className="folio-index" aria-hidden="true">
              ↳
            </span>
            <h1 tabIndex={-1}>
              A receipt is a fact.
              <br />A deduction is a claim.
            </h1>
            <p>
              Bring the bank record, invoice and source proof together. Keep the
              human decision visible.
            </p>
            <div className="login-rule">
              <span>Cash received</span>
              <span>Evidence checked</span>
              <span>Human reviewed</span>
            </div>
          </section>
          <section className="login-form">
            <h2>Open your workstation</h2>
            <p>
              Use a provisioned local review session. These credentials confer
              no financial authority.
            </p>
            <form onSubmit={(e) => void login(e)}>
              <label>
                Username
                <input
                  name="username"
                  autoComplete="username"
                  required
                  spellCheck={false}
                />
              </label>
              <label>
                Password
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </label>
              {error !== undefined && <ErrorNotice error={error} />}
              <button className="primary" type="submit" disabled={busy}>
                {busy ? "Checking session…" : "Open exception register"}
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </form>
            <small>
              Session credentials remain in memory. Reloading requires sign-in.
            </small>
          </section>
        </main>
      ) : (
        <>
          <FocusRoute />
          <Boundary key={session.me.subject}>
            <Routes>
              <Route path="/" element={<Queue api={session.api} />} />
              <Route
                path="/cases/:id"
                element={<CaseFile api={session.api} me={session.me} />}
              />
              <Route
                path="/intake"
                element={
                  <Intake
                    api={session.api}
                    readOnly={session.me.role === "AUDITOR"}
                  />
                }
              />
              <Route
                path="*"
                element={
                  <main id="main">
                    <h1 tabIndex={-1}>Case route not found</h1>
                    <Link to="/">Return to exception register</Link>
                  </main>
                }
              />
            </Routes>
          </Boundary>
        </>
      )}
      <footer className="app-footer">
        <span>Evidence-led review. No autonomous financial decisions.</span>
        <span>INR / integer paise</span>
      </footer>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
