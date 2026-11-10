import { expect, test, type Page } from "@playwright/test";

test.setTimeout(150_000);
test.use({ viewport: { width: 1440, height: 1000 } });

async function enter(page: Page) {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Continue as Demo Analyst" }),
  ).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Continue as Demo Analyst" }).click();
  await expect(
    page.getByRole("heading", { name: "Exception register" }),
  ).toBeVisible({ timeout: 100_000 });
  await expect(page.locator("tbody tr").first()).toBeVisible({
    timeout: 25_000,
  });
}

function consoleFailures(page: Page) {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning")
      errors.push(msg.type());
  });
  page.on("pageerror", (err) => errors.push(err.name));
  page.on("response", (response) => {
    if (response.status() >= 400) errors.push(`HTTP ${response.status()}`);
  });
  return errors;
}

test("demo entry, public registers, refresh and sign-out", async ({ page }) => {
  const errors = consoleFailures(page);
  await enter(page);
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  for (const name of ["Invoices", "Receipts", "Remittances"]) {
    await nav.getByRole("link", { name, exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Open case", exact: true }).first(),
    ).toBeVisible({ timeout: 20_000 });
  }
  // Reproduce sign-out while the new page's register snapshot is in flight.
  let releaseSnapshot!: () => void;
  const holdSnapshot = new Promise<void>((resolve) => {
    releaseSnapshot = resolve;
  });
  await page.route("**/portfolio/bootstrap", async (route) => {
    await holdSnapshot;
    await route.continue().catch(() => undefined);
  });
  const snapshot = page.waitForRequest("**/portfolio/bootstrap");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Remittances", exact: true }),
  ).toBeVisible();
  await snapshot;
  const revoked = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/portfolio/session" &&
      response.request().method() === "DELETE",
  );
  try {
    await page.getByRole("button", { name: "Sign out" }).click();
  } finally {
    releaseSnapshot();
  }
  await expect(
    page.getByRole("button", { name: "Continue as Demo Analyst" }),
  ).toBeVisible();
  expect((await revoked).ok()).toBe(true);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(errors).toEqual([]);
});

test("current findings, source span, trace and read-only correlation", async ({
  page,
}) => {
  const errors = consoleFailures(page);
  let sourceReads = 0;
  const workflowWrites: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET" && /^\/documents\/[^/]+\/text$/.test(path))
      sourceReads++;
    if (request.method() === "POST" && path.endsWith("/decision"))
      workflowWrites.push(path);
  });
  await enter(page);
  async function open(invoice: string, proposed = false) {
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Exceptions" })
      .click();
    const row = page
      .locator("tbody tr")
      .filter({ hasText: proposed ? `Proposed: ${invoice}` : invoice });
    await row.getByRole("link").first().click();
    await expect(
      page.getByRole("region", { name: "Invoice, payment and difference" }),
    ).toBeVisible({ timeout: 25_000 });
  }
  await open("INV-2026-1042");
  await expect(
    page.getByRole("heading", { name: "Signed POD is missing" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "View evidence", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Invoice INV-2026-1042", exact: true })
    .click();
  await expect(page.getByTestId("source-highlight")).toHaveText(
    "INV-2026-1042",
  );
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  await expect(
    page.getByRole("button", { name: "Close evidence inspector" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "View evidence", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Invoice INV-2026-1042", exact: true })
    .click();
  await expect(page.getByTestId("source-highlight")).toHaveText(
    "INV-2026-1042",
  );
  expect(sourceReads).toBe(1);
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  await page
    .getByRole("link", { name: "Technical trace", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: /^Evidence verification/ }),
  ).toBeVisible();
  await open("INV-2026-1043");
  await expect(
    page.getByRole("heading", { name: "Evidence supports the claim" }),
  ).toBeVisible();
  await open("INV-2026-1044");
  await expect(
    page.getByRole("heading", { name: "Delivery records disagree" }),
  ).toBeVisible();
  await open("INV-2026-1045", true);
  await page
    .getByRole("link", { name: "Match payment to invoice" })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: "Independent proof ready for review" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review & confirm association" }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Inspect independent payment proof" })
    .click();
  await expect(
    page.getByText("Source verified", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  await page
    .getByRole("button", { name: "Review & confirm association" })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Confirm this evidence association?",
  });
  await dialog
    .getByRole("button", { name: "Confirm association", exact: true })
    .click();
  await expect(
    page.getByText(/Demo simulation · Association confirmed for this session/),
  ).toBeVisible();
  expect(workflowWrites).toEqual([]);
  expect(errors).toEqual([]);
});

test("shared register cache, ephemeral review and stale refresh recovery", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (req) => {
    if (req.resourceType() === "fetch")
      requests.push(`${req.method()} ${new URL(req.url()).pathname}`);
  });
  const bootstrap = "GET /portfolio/bootstrap";
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  const queue = () =>
    nav.getByRole("link", { name: "Exceptions", exact: true }).click();
  const draft = page.getByRole("button", {
    name: "Draft evidence request",
    exact: true,
  });
  const message = page.getByText(
    /Demo simulation · Evidence request draft prepared/,
  );
  async function open() {
    await page
      .locator("tbody tr")
      .filter({ hasText: "INV-2026-1042" })
      .getByRole("link")
      .first()
      .click();
    await expect(draft).toBeVisible({ timeout: 35_000 });
  }
  await enter(page);
  expect(requests.filter((r) => r === bootstrap)).toHaveLength(1);
  const beforeRegisters = requests.length;
  for (const name of ["Invoices", "Receipts", "Remittances"]) {
    await nav.getByRole("link", { name, exact: true }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Open case", exact: true }).first(),
    ).toBeVisible();
  }
  await queue();
  await expect(
    page.getByRole("heading", { name: "Exception register" }),
  ).toBeVisible();
  expect(requests).toHaveLength(beforeRegisters);
  await open();
  expect(
    requests.filter((r) => r.startsWith("GET /portfolio/cases/")),
  ).toHaveLength(1);
  const beforeSimulation = requests.length;
  await draft.click();
  const dialog = page.getByRole("dialog", { name: "Draft evidence request" });
  await expect(
    dialog.getByText(/Confirmation stays in this browser session/),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Save draft only" }).click();
  await expect(message).toBeVisible();
  await queue();
  await open();
  await expect(message).toBeVisible();
  expect(requests).toHaveLength(beforeSimulation);

  let refreshFailed = false;
  await page.route("**/portfolio/cases/*", async (route) => {
    if (!refreshFailed) {
      refreshFailed = true;
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Refresh case", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(draft).toBeVisible();
  await expect(message).toBeVisible();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0, { timeout: 35_000 });
  await expect(
    page.getByRole("button", { name: "Refresh case", exact: true }),
  ).toBeEnabled({ timeout: 35_000 });
  expect(
    requests.filter((r) => r.startsWith("GET /portfolio/cases/")),
  ).toHaveLength(3);
  await queue();
  await page
    .getByRole("button", { name: "Refresh queue", exact: true })
    .click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Refresh queue", exact: true }),
  ).toBeEnabled({ timeout: 35_000 });
  expect(requests.filter((r) => r === bootstrap)).toHaveLength(2);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("button", { name: "Continue as Demo Analyst" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continue as Demo Analyst" }).click();
  await expect(
    page.getByRole("heading", { name: "Exception register" }),
  ).toBeVisible();
  await open();
  await expect(message).toHaveCount(0);
  expect(requests.filter((r) => r === bootstrap)).toHaveLength(3);
});

test("ephemeral sample upload and transient key input at mobile width", async ({
  page,
}) => {
  const errors = consoleFailures(page);
  await enter(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("link", { name: "Import & documents" }).click();
  if (process.env.PORTFOLIO_EXPECT_INCLUDED === "off") {
    await expect(
      page.getByRole("button", { name: "Run one live AI investigation" }),
    ).toBeDisabled();
  }
  expect(
    await page.evaluate(() => {
      const nav = document.querySelector("header.app-header nav");
      const heading = document.querySelector("main h1");
      return (
        !!nav &&
        !!heading &&
        nav.getBoundingClientRect().bottom <=
          heading.getBoundingClientRect().top
      );
    }),
  ).toBe(true);
  const link = page.getByRole("link", { name: "Download sample remittance" });
  const path = await link.getAttribute("href");
  const sample = await page.request.get(path!);
  expect(sample.ok()).toBeTruthy();
  await page.getByLabel("Document", { exact: true }).setInputFiles({
    name: "sample-remittance.txt",
    mimeType: "text/plain",
    buffer: await sample.body(),
  });
  await expect(
    page.getByRole("button", { name: "Extract document" }),
  ).toBeDisabled();
  await page.getByLabel(/I confirm this is synthetic/).check();
  await page.getByRole("button", { name: "Extract document" }).click();
  await expect(
    page.getByText("Source checks passed", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "INV-2026-1042", exact: true })
    .click();
  await expect(page.locator("mark")).toHaveText("INV-2026-1042");
  const key = "browser-placeholder-intercepted-locally";
  let observed = false;
  await page.route("**/portfolio/extract", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    observed = route.request().headers()["x-portfolio-gemini-key"] === key;
    await route.fulfill({
      status: 200,
      headers: { "access-control-allow-origin": new URL(page.url()).origin },
      json: {
        filename: "sample-remittance.txt",
        pages: ["sample"],
        parse_status: "READY",
        deterministic_status: "ABSTAINED",
        extraction: null,
        ai: {
          model: "gemini-3.5-flash-lite",
          status: "REJECTED",
          proposal: null,
          validated: null,
        },
      },
    });
  });
  await page.getByLabel("Use my Gemini key").check();
  await page.getByLabel(/I am 18 or older/).check();
  await page.getByLabel("Gemini API key", { exact: true }).fill(key);
  await page.getByRole("button", { name: "Extract document" }).click();
  await expect(page.getByLabel("Gemini API key", { exact: true })).toHaveValue(
    "",
  );
  await expect(page.getByText(/Rejected by source validation/)).toBeVisible();
  expect(observed).toBe(true);
  const storage = await page.evaluate(() =>
    JSON.stringify([localStorage, sessionStorage, location.href]),
  );
  expect(storage).not.toContain(key);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("cold-start error exposes an entry retry", async ({ page }) => {
  let failed = false;
  await page.route("**/portfolio/session", async (route) => {
    if (!failed && route.request().method() === "POST") {
      failed = true;
      await route.abort("failed");
    } else await route.continue();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Demo Analyst" }).click();
  await expect(page.getByRole("alert")).toContainText("may still be waking up");
  await page.getByRole("button", { name: "Retry demo entry" }).click();
  await expect(
    page.getByRole("heading", { name: "Exception register" }),
  ).toBeVisible({ timeout: 100_000 });
});
