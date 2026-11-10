import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const json = (body: unknown) => new Response(JSON.stringify(body));
const origin = "https://example.onrender.com";

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("VITE_API_BASE_URL", origin);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("public session read cache", () => {
  it("deduplicates concurrent reads, reuses results, and isolates sessions", async () => {
    let resolve!: (response: Response) => void;
    const fetch = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<Response>((done) => {
            resolve = done;
          }),
      )
      .mockImplementation(() => Promise.resolve(json({ value: 2 })));
    vi.stubGlobal("fetch", fetch);
    const { Client, portfolioBootstrap } = await import("./api");
    const client = new Client("demo-token");
    const first = client.request(portfolioBootstrap);
    const second = client.request(portfolioBootstrap);
    expect(first).toBe(second);
    expect(fetch).toHaveBeenCalledTimes(1);
    resolve(json({ value: 1 }));
    await expect(first).resolves.toEqual({ value: 1 });
    await expect(client.request(portfolioBootstrap)).resolves.toEqual({
      value: 1,
    });
    expect(client.peek(portfolioBootstrap)).toEqual({ value: 1 });
    expect(fetch).toHaveBeenCalledTimes(1);
    await expect(
      new Client("next-token").request(portfolioBootstrap),
    ).resolves.toEqual({ value: 2 });
    client.clear();
    expect(client.peek(portfolioBootstrap)).toBeUndefined();
    await client.request(portfolioBootstrap);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("retains the previous snapshot after a failed invalidation and replaces it on success", async () => {
    const fetch = vi
      .fn()
      .mockImplementationOnce(() => Promise.resolve(json({ value: 1 })))
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockImplementation(() => Promise.resolve(json({ value: 2 })));
    vi.stubGlobal("fetch", fetch);
    const { Client, portfolioBootstrap } = await import("./api");
    const client = new Client("demo-token");
    await client.request(portfolioBootstrap);
    client.invalidate(portfolioBootstrap);
    await expect(client.request(portfolioBootstrap)).rejects.toThrow(
      "PORTFOLIO_API_UNAVAILABLE",
    );
    expect(client.peek(portfolioBootstrap)).toEqual({ value: 1 });
    await expect(client.request(portfolioBootstrap)).resolves.toEqual({
      value: 2,
    });
    expect(client.peek(portfolioBootstrap)).toEqual({ value: 2 });
  });

  it("cancels an in-flight read when its session is cleared", async () => {
    let complete!: (response: Response) => void;
    const fetch = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(
      () =>
        new Promise<Response>((resolve) => {
          complete = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetch);
    const { Client, portfolioBootstrap } = await import("./api");
    const client = new Client("demo-token");
    const pending = client.request(portfolioBootstrap);
    const signal = fetch.mock.calls[0][1].signal;
    expect(signal?.aborted).toBe(false);
    client.clear();
    expect(signal?.aborted).toBe(true);
    complete(json({ ignored: true }));
    await pending;
    expect(client.peek(portfolioBootstrap)).toBeUndefined();
  });

  it("never caches authentication, mutations or uploads with visitor credentials", async () => {
    const fetch = vi.fn(() => Promise.resolve(json({ ok: true })));
    vi.stubGlobal("fetch", fetch);
    const { Client, portfolioBootstrap } = await import("./api");
    const client = new Client("demo-token");
    const file = new File(["sample"], "sample.txt", { type: "text/plain" });
    for (const key of ["first-placeholder", "second-placeholder"]) {
      await client.request("/portfolio/session");
      await client.request("/review/me");
      await client.request(portfolioBootstrap, "POST");
      await client.portfolioUpload(file, "text/plain", key);
    }
    expect(fetch).toHaveBeenCalledTimes(8);
    expect(client.peek("/portfolio/session")).toBeUndefined();
    expect(client.peek("/review/me")).toBeUndefined();
    expect(client.peek("/portfolio/extract")).toBeUndefined();
    expect(client.peek(portfolioBootstrap)).toBeUndefined();
  });

  it("keys source reads by document version and both hashes and rejects a mismatch", async () => {
    const fetch = vi
      .fn()
      .mockImplementationOnce(() =>
        Promise.resolve(
          json({
            document_version: 1,
            raw_sha256: "a",
            canonical_sha256: "b",
            pages: ["one"],
          }),
        ),
      )
      .mockImplementationOnce(() =>
        Promise.resolve(
          json({
            document_version: 1,
            raw_sha256: "a",
            canonical_sha256: "b",
            pages: ["wrong"],
          }),
        ),
      )
      .mockImplementation(() =>
        Promise.resolve(
          json({
            document_version: 2,
            raw_sha256: "c",
            canonical_sha256: "d",
            pages: ["two"],
          }),
        ),
      );
    vi.stubGlobal("fetch", fetch);
    const { Client } = await import("./api");
    const client = new Client("demo-token");
    const doc = {
      id: "a-b",
      version: 1,
      content_sha256: "a",
      canonical_sha256: "b",
    };
    const next = {
      ...doc,
      version: 2,
      content_sha256: "c",
      canonical_sha256: "d",
    };
    expect((await client.sourceText(doc)).pages).toEqual(["one"]);
    await client.sourceText(doc);
    expect(fetch).toHaveBeenCalledTimes(1);
    await expect(client.sourceText(next)).rejects.toThrow(
      "SOURCE_VERSION_CHANGED",
    );
    expect((await client.sourceText(next)).pages).toEqual(["two"]);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("keeps private application reads uncached", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetch = vi.fn(() => Promise.resolve(json([])));
    vi.stubGlobal("fetch", fetch);
    const { Client } = await import("./api");
    const client = new Client("private-token");
    await client.request("/invoices");
    await client.request("/invoices");
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
