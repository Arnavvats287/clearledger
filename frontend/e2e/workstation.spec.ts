import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";

const access = JSON.parse(
  fs.readFileSync(
    new URL("../../local-data/frontend/access.json", import.meta.url),
    "utf8",
  ),
) as {
  username: string;
  password: string;
  fixtures: { mode: string; case_id: string; task_id: string }[];
};
const screenshots = new URL("../../docs/screenshots/", import.meta.url);
fs.mkdirSync(screenshots, { recursive: true });

async function login(page: Page, username = access.username) {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(access.password);
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/review/demo/login") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Open exception register", exact: true })
    .click();
  const { access_token: token } = await (await response).json();
  await expect(
    page.getByRole("heading", { name: "Exception register", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Test", exact: true }).first(),
  ).toBeVisible();
  return { Authorization: `ReviewDemo ${token}` };
}
async function openCase(page: Page, mode: string, tab?: string) {
  const f = access.fixtures.find((f) => f.mode === mode)!;
  await page.locator(`a[href="/cases/${f.case_id}"]`).first().click();
  await expect(
    page.getByRole("heading", { name: "The asserted discrepancy" }),
  ).toBeVisible();
  if (tab)
    await page.getByRole("link", { name: new RegExp(`^${tab}`) }).click();
  return f;
}
async function shot(page: Page, name: string) {
  await page.screenshot({
    path: new URL(`${name}.png`, screenshots).pathname.replace(
      /^\/(\w:)/,
      "$1",
    ),
    fullPage: true,
  });
}

test.beforeEach(async ({ page }) => {
  const failures: string[] = [];
  page.on("pageerror", (e) => failures.push(e.name));
  page.on("response", (r) => {
    if (r.status() >= 400)
      failures.push(`${r.status()} ${new URL(r.url()).pathname}`);
  });
  page.on("close", () => {
    /* Browser records are never logged with headers or bodies. */
  });
  (page as Page & { failures: string[] }).failures = failures;
});
test.afterEach(async ({ page }, info) => {
  if (!info.title.includes("fault injection"))
    expect((page as Page & { failures: string[] }).failures).toEqual([]);
});

test("queue, precise money, canonical span and keyboard focus", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.name));
  await login(page);
  await expect(
    page.getByText("Offline control · Completed").first(),
  ).toBeVisible();
  await shot(page, "exception-queue");
  await page.getByRole("button", { name: "Conflict", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "All exceptions", exact: true })
    .click();
  await openCase(page, "missing");
  await expect(page.locator(".financial-comparison")).toContainText("₹10.01");
  await expect(page.locator(".financial-comparison")).toContainText("₹9.00");
  await expect(page.locator(".financial-comparison")).toContainText("₹1.01");
  await page.getByRole("button", { name: "Invoice I-1", exact: true }).click();
  await expect(page.getByTestId("source-highlight")).toHaveText("I-1");
  await expect(
    page.getByText("Span consistent", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "damage · ₹1.01" }).click();
  await expect(page.getByTestId("source-highlight")).toHaveText("INR 1.01");
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  await expect(
    page.getByRole("region", { name: "Document evidence inspector" }),
  ).toHaveCount(0);
  await page.keyboard.press("Tab");
  const focus = await page.evaluate(() => {
    const e = document.activeElement!;
    return { tag: e.tagName, outline: getComputedStyle(e).outlineStyle };
  });
  expect(["A", "BUTTON", "SUMMARY"]).toContain(focus.tag);
  expect(focus.outline).not.toBe("none");
  expect(errors).toEqual([]);
});

for (const [mode, outcome, action] of [
  ["missing", "Insufficient evidence", "Request evidence"],
  ["supported", "Supported", "Human review"],
  ["conflict", "Conflicting evidence", "Escalate conflict"],
]) {
  test(`${mode}: persisted plan, verification, synthesis and citations`, async ({
    page,
  }) => {
    const headers = await login(page);
    const invoices = await (
      await page.request.get("http://127.0.0.1:8010/invoices", { headers })
    ).text();
    const receipts = await (
      await page.request.get("http://127.0.0.1:8010/receipts", { headers })
    ).text();
    await openCase(page, mode, "Investigation");
    await expect(
      page.getByText("Offline control · fake", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^Investigator plan/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^Evidence verification/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^Investigator synthesis/ }),
    ).toBeVisible();
    await page.getByRole("button", { name: /^Investigator plan/ }).click();
    await expect(page.locator(".stage-detail")).toContainText(
      "Get wms deliveries",
    );
    await page.getByRole("button", { name: /^Evidence verification/ }).click();
    await expect(page.locator(".stage-detail")).toContainText(
      "Source facts only",
    );
    await page.getByRole("button", { name: /^Investigator synthesis/ }).click();
    await expect(page.locator(".next-action strong")).toHaveText(action);
    await expect(page.locator(".case-heading .badge")).toHaveText(outcome);
    await page
      .getByRole("button", { name: /Inspect source/ })
      .first()
      .click();
    await expect(
      page.getByText("Source verified", { exact: true }),
    ).toBeVisible();
    await expect(page.getByTestId("source-highlight")).toBeVisible();
    await shot(page, `${mode}-evidence-investigation`);
    await page
      .getByRole("button", { name: "Close evidence inspector" })
      .click();
    const before = await page.locator(".run-select option").count();
    await page
      .getByRole("button", { name: "Refresh case", exact: true })
      .click();
    await expect(page.locator(".run-select option")).toHaveCount(before);
    expect(
      await (
        await page.request.get("http://127.0.0.1:8010/invoices", { headers })
      ).text(),
    ).toBe(invoices);
    expect(
      await (
        await page.request.get("http://127.0.0.1:8010/receipts", { headers })
      ).text(),
    ).toBe(receipts);
  });
}

test("inspect task proof, deliberately confirm, retain history and merge", async ({
  page,
}) => {
  const headers = await login(page);
  const before = await (
    await page.request.get("http://127.0.0.1:8010/invoices", { headers })
  ).text();
  await openCase(page, "confirm", "Correlation review");
  await expect(
    page.getByRole("heading", { name: "Ready for review", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Inspect authenticated source/ })
    .click();
  await expect(
    page.getByText("Source verified", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("source-highlight")).toBeVisible();
  await page
    .getByRole("button", { name: "Review & confirm association", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page
    .getByRole("button", { name: "Review & confirm association", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Confirm association", exact: true })
    .click();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();
  await expect(page.locator(".decision-history")).toHaveCount(1);
  await shot(page, "correlation-decision");
  await page
    .getByRole("button", { name: "Refresh proof", exact: true })
    .click();
  await expect(page.locator(".decision-history")).toHaveCount(1);
  await expect(page.locator(".financial-comparison")).toContainText("₹10.01");
  await expect(page.locator(".financial-comparison")).toContainText("₹9.00");
  expect(
    await (
      await page.request.get("http://127.0.0.1:8010/invoices", { headers })
    ).text(),
  ).toBe(before);
});

test("reject and auditor boundary, responsive dark mode and offline error", async ({
  page,
}) => {
  await login(page);
  await openCase(page, "reject", "Correlation review");
  await page
    .getByRole("button", { name: "Review & reject", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record rejection" })
    .click();
  await expect(page.getByText("Rejected", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "auditor");
  await openCase(page, "missing", "Investigation");
  await expect(
    page.getByRole("button", { name: "Run current investigation" }),
  ).toBeDisabled();
  await expect(page.locator(".stage-detail")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Use dark mode" }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await shot(page, "mobile-dark-case");
  await page.setViewportSize({ width: 768, height: 1024 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.context().setOffline(true);
  await page.getByRole("button", { name: "Refresh case", exact: true }).click();
  await expect(
    page.getByText("The application server is unreachable.", { exact: false }),
  ).toBeVisible();
  await page.context().setOffline(false);
});

test("real draft evidence request and readable human audit", async ({
  page,
}) => {
  await login(page);
  await openCase(page, "missing", "Investigation");
  await page
    .getByRole("button", { name: "Draft evidence request", exact: true })
    .click();
  await page
    .getByLabel("Review note (optional)")
    .fill(
      "Please provide signed POD for the asserted damage. No settlement authorized.",
    );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save draft only", exact: true })
    .click();
  await expect(
    page.getByText("Evidence request saved as a draft. Nothing was sent."),
  ).toBeVisible();
  await page.getByRole("link", { name: "Audit trail", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Case history" }),
  ).toBeVisible();
  await expect(page.locator(".review-history")).toHaveCount(1);
});

test("fault injection: malformed API data, empty search and recoverable errors", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("textbox", { name: "Search loaded cases" })
    .fill("no-such-synthetic-case");
  await expect(
    page.getByText("No loaded cases match this view.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "Search loaded cases" }).fill("");
  await page.route("**/api/cases?*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"not_a_case_list":true}',
    }),
  );
  await page
    .getByRole("button", { name: "Refresh queue", exact: true })
    .click();
  await expect(
    page.getByText("MALFORMED_LIST_RESPONSE", { exact: false }),
  ).toBeVisible();
  await page.unroute("**/api/cases?*");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Test", exact: true }).first(),
  ).toBeVisible();
});
