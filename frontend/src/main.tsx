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
  HashRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { ArrowRight, LogOut, Moon, Sun } from "lucide-react";
import "@fontsource/geist/400.css";
import "@fontsource/geist/500.css";
import "@fontsource/geist/600.css";
import "@fontsource/geist/700.css";
import "@fontsource/geist-mono/400.css";
import { Client, publicPortfolio, type Me } from "./api";
import { CaseFile } from "./CaseFile";
import { Intake } from "./Intake";
import { PortfolioRecords } from "./PortfolioRecords";
import { PortfolioSandbox } from "./PortfolioSandbox";
import { Queue } from "./Queue";
import { Badge, ErrorNotice } from "./ui";
import "./style.css";
import "./visual-system.css";
import "./portfolio.css";

const portfolioSessionKey = "clearledger-portfolio-session";
function savePortfolioSession(token?: string) {
  try {
    if (token) sessionStorage.setItem(portfolioSessionKey, token);
    else sessionStorage.removeItem(portfolioSessionKey);
  } catch {
    /* The public session can stay in memory. */
  }
}
async function demoIdentity(api: Client, signal?: AbortSignal) {
  const me = await api.request<Me>(
    "/portfolio/session",
    "GET",
    undefined,
    undefined,
    signal,
  );
  if (me.role !== "AUDITOR" || me.financial_authority !== false)
    throw new Error("Invalid demo identity");
  return { api, me };
}

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
    const titles: Record<string, string> = {
      "/intake": "Import & documents",
      "/invoices": "Invoices",
      "/receipts": "Receipts",
      "/remittances": "Remittances",
    };
    document.title = `ClearLedger · ${location.pathname.startsWith("/cases/") ? "Case file" : titles[location.pathname] || "Exception register"}`;
    requestAnimationFrame(() =>
      (location.hash === "#live-ai"
        ? document.querySelector<HTMLElement>("#live-ai-heading")
        : document.querySelector<HTMLElement>("main h1")
      )?.focus(),
    );
  }, [location.pathname, location.hash]);
  return null;
}
function App() {
  const navigate = useNavigate();
  const [session, setSession] = useState<{ api: Client; me: Me }>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  useEffect(() => {
    if (!publicPortfolio) return;
    let token: string | null;
    try {
      token = sessionStorage.getItem(portfolioSessionKey);
    } catch {
      return;
    }
    if (!token) return;
    const stop = new AbortController();
    setBusy(true);
    demoIdentity(new Client(token), stop.signal)
      .then((restored) => {
        if (!stop.signal.aborted) setSession(restored);
      })
      .catch((err: unknown) => {
        if (!stop.signal.aborted) {
          savePortfolioSession();
          setError(err);
        }
      })
      .finally(() => {
        if (!stop.signal.aborted) setBusy(false);
      });
    return () => stop.abort();
  }, []);
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
  async function enterDemo() {
    setBusy(true);
    setError(undefined);
    try {
      const { access_token } = await new Client("").request<{
        access_token: string;
      }>("/portfolio/session", "POST");
      const identity = await demoIdentity(new Client(access_token));
      savePortfolioSession(access_token);
      setSession(identity);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    try {
      if (publicPortfolio)
        await session?.api.request("/portfolio/session", "DELETE");
      else await session?.api.request("/review/demo/logout", "POST", {});
    } catch {
      setError(new Error("Server session revocation unavailable"));
    } finally {
      if (publicPortfolio) {
        savePortfolioSession();
        void navigate("/");
      }
      setSession(undefined);
    }
  }
  return (
    <>
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          if (publicPortfolio) {
            event.preventDefault();
            document.querySelector<HTMLElement>("main h1")?.focus();
          }
        }}
      >
        Skip to case content
      </a>
      <header
        className={`app-header${publicPortfolio ? " portfolio-header" : ""}`}
      >
        <Link to="/" className="brand">
          <Mark />
          <span>ClearLedger</span>
          <small>Receivables workstation</small>
        </Link>
        {(!publicPortfolio || session) && (
          <nav aria-label="Main navigation">
            <NavLink to="/" end>
              Exceptions
            </NavLink>
            {publicPortfolio && (
              <>
                <NavLink to="/invoices">Invoices</NavLink>
                <NavLink to="/receipts">Receipts</NavLink>
                <NavLink to="/remittances">Remittances</NavLink>
              </>
            )}
            <NavLink to="/intake">Import & documents</NavLink>
          </nav>
        )}
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
                {publicPortfolio
                  ? "Synthetic demo"
                  : session.me.authority === "LOCAL_DEMO_ONLY"
                    ? "Local synthetic session"
                    : "Verified review session"}
              </Badge>
              <button aria-label="Sign out" onClick={() => void logout()}>
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
            <h2>
              {publicPortfolio
                ? "Enter the demo workstation"
                : "Open your workstation"}
            </h2>
            {publicPortfolio ? (
              <>
                <p>
                  Explore the synthetic receivables ledger and inspect the proof
                  behind a deduction.
                </p>
                <button
                  className="primary"
                  type="button"
                  disabled={busy}
                  onClick={() => void enterDemo()}
                >
                  {error === undefined
                    ? "Continue as Demo Analyst"
                    : "Retry demo entry"}
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
                {busy && <p role="status">Starting portfolio demo API…</p>}
                {error !== undefined && (
                  <p role="alert">
                    The demo API may still be waking up. Try again in a moment.
                  </p>
                )}
                <small>
                  Synthetic portfolio workspace. No financial authority. Upload
                  only synthetic or non-confidential documents. The API can take
                  about a minute to wake.
                </small>
              </>
            ) : (
              <>
                <p>
                  Use a provisioned local review session. These credentials
                  confer no financial authority.
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
                  Session credentials remain in memory. Reloading requires
                  sign-in.
                </small>
              </>
            )}
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
              {publicPortfolio ? (
                <>
                  <Route
                    path="/invoices"
                    element={
                      <PortfolioRecords
                        key="invoices"
                        api={session.api}
                        kind="invoices"
                      />
                    }
                  />
                  <Route
                    path="/receipts"
                    element={
                      <PortfolioRecords
                        key="receipts"
                        api={session.api}
                        kind="receipts"
                      />
                    }
                  />
                  <Route
                    path="/remittances"
                    element={
                      <PortfolioRecords
                        key="remittances"
                        api={session.api}
                        kind="remittances"
                      />
                    }
                  />
                  <Route
                    path="/intake"
                    element={
                      <PortfolioSandbox
                        api={session.api}
                        includedAvailable={
                          session.me.included_available === true
                        }
                      />
                    }
                  />
                </>
              ) : (
                <Route
                  path="/intake"
                  element={
                    <Intake
                      api={session.api}
                      readOnly={session.me.role === "AUDITOR"}
                    />
                  }
                />
              )}
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

const WorkstationRouter = publicPortfolio ? HashRouter : BrowserRouter;
createRoot(document.getElementById("root")!).render(
  <WorkstationRouter>
    <App />
  </WorkstationRouter>,
);
