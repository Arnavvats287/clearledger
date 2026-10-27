import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, Client, decode, money, references, sliceSpan } from "./api";

afterEach(() => vi.unstubAllGlobals());
describe("integer-paise presentation", () => {
  it("preserves int64 money before JavaScript can round it", () => {
    const x = decode(
      '{"open_amount_paise":9223372036854775807,"version":1}',
    ) as { open_amount_paise: bigint; version: number };
    expect(x.open_amount_paise).toBe(9223372036854775807n);
    expect(x.version).toBe(1);
    expect(money(x.open_amount_paise)).toBe("₹92,23,37,20,36,85,47,758.07");
  });
  it("distinguishes missing, zero, negative and fractional rupees exactly", () => {
    expect(money(null)).toBe("—");
    expect(money(0n)).toBe("₹0.00");
    expect(money(101n)).toBe("₹1.01");
    expect(money(-101n)).toBe("−₹1.01");
  });
  it("refuses float and string money instead of coercing them", () => {
    expect(() => decode('{"amount_paise":1.01}')).toThrow();
    expect(() => decode('{"amount_paise":"101"}')).toThrow();
  });
});
describe("canonical source spans", () => {
  it("uses Unicode code points rather than UTF-16 offsets", () => {
    expect(
      sliceSpan("\u{1f600} Invoice I-1", {
        page: 1,
        start: 10,
        end: 13,
        quote: "I-1",
      }),
    ).toEqual(["\u{1f600} Invoice ", "I-1", ""]);
  });
  it("rejects wrong quotes and out-of-bounds positions", () => {
    expect(() =>
      sliceSpan("Invoice I-1", { page: 1, start: 8, end: 11, quote: "I-2" }),
    ).toThrow(ApiError);
    expect(() =>
      sliceSpan("x", { page: 1, start: 0, end: 10, quote: "x" }),
    ).toThrow(ApiError);
  });
});
describe("API failures remain failures", () => {
  it("loads financial references beyond the first page instead of inventing missing balances", async () => {
    const fetch = vi
      .fn()
      .mockImplementation(
        async (path: string) =>
          new Response(
            JSON.stringify(
              path.includes("offset=100")
                ? [{ id: "wanted" }]
                : Array.from({ length: 100 }, (_, i) => ({ id: String(i) })),
            ),
          ),
      );
    vi.stubGlobal("fetch", fetch);
    expect(
      await references(new Client("unit"), "/invoices", ["wanted"]),
    ).toEqual([{ id: "wanted" }]);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("preserves safe status/code without leaking provider text", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"detail":"STALE_CORRELATION_CASE"}', { status: 409 }),
        ),
    );
    await expect(
      new Client("unit").request("/cases/unit"),
    ).rejects.toMatchObject({ status: 409, code: "STALE_CORRELATION_CASE" });
  });
  it("reports offline and malformed responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("secret unsafe URL")),
    );
    await expect(new Client("unit").request("/cases")).rejects.toMatchObject({
      code: "SERVER_UNAVAILABLE",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>private</html>")),
    );
    await expect(new Client("unit").request("/cases")).rejects.toMatchObject({
      code: "MALFORMED_API_RESPONSE",
    });
  });
  it("carries the original retry key, not a newly fabricated version", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    await new Client("unit").request(
      "/decision",
      "POST",
      { expected_case_version: 4 },
      "original-key",
    );
    expect(fetch.mock.calls[0][1].headers["Idempotency-Key"]).toBe(
      "original-key",
    );
    expect(fetch.mock.calls[0][1].body).toContain('"expected_case_version":4');
  });
});
