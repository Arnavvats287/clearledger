type Entry = { value?: unknown; pending?: Promise<unknown>; stale?: boolean };

// Only the public Client calls this store. Request loaders and failures never
// outlive their in-flight entry, and a failed refresh retains the prior value.
export class PortfolioCache {
  private entries = new Map<string, Entry>();

  peek<T>(key: string): T | undefined {
    return this.entries.get(key)?.value as T | undefined;
  }

  read<T>(key: string, load: () => Promise<T>): Promise<T> {
    const entry = this.entries.get(key) ?? {};
    if (!entry.stale && entry.value !== undefined)
      return Promise.resolve(entry.value as T);
    if (entry.pending) return entry.pending as Promise<T>;
    this.entries.set(key, entry);
    const pending = load().then(
      (value) => {
        if (this.entries.get(key) === entry) this.entries.set(key, { value });
        return value;
      },
      (error: unknown) => {
        if (this.entries.get(key) === entry) {
          if (entry.value === undefined) this.entries.delete(key);
          else this.entries.set(key, { value: entry.value, stale: true });
        }
        throw error;
      },
    );
    entry.pending = pending;
    return pending;
  }

  invalidate(matches: (key: string) => boolean) {
    for (const [key, entry] of this.entries)
      if (matches(key))
        this.entries.set(key, { value: entry.value, stale: true });
  }

  clear() {
    this.entries.clear();
  }
}

export function publicReadKey(path: string) {
  const pathname = path.split("?", 1)[0];
  return /^\/portfolio\/(?:bootstrap|cases\/[\da-f-]+)$/.test(pathname) ||
    /^\/(?:customers|invoices|receipts|bank-transactions)(?:\/[\da-f-]+)?$/.test(
      pathname,
    ) ||
    /^\/cases(?:\/[\da-f-]+(?:\/(?:claims|investigations|events|reevaluations|review-actions)|\/evidence\/records\/[\da-f-]+)?)?$/.test(
      pathname,
    ) ||
    /^\/documents\/[\da-f-]+(?:\/extractions)?$/.test(pathname) ||
    /^\/investigations\/[\da-f-]+\/(?:trace|findings)$/.test(pathname) ||
    /^\/review\/(?:cases\/[\da-f-]+\/correlation-tasks|correlation-tasks\/[\da-f-]+\/(?:decisions|proof))$/.test(
      pathname,
    )
    ? path
    : undefined;
}
