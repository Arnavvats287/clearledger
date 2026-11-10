import { createContext, useContext, useState, type ReactNode } from "react";
import { publicPortfolio } from "./api";

const Context = createContext<{
  results: Record<string, string>;
  record: (key: string, message: string) => void;
} | null>(null);

export function DemoSimulationProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<Record<string, string>>({});
  return (
    <Context.Provider
      value={
        publicPortfolio
          ? {
              results,
              record: (key, message) =>
                setResults((previous) => ({ ...previous, [key]: message })),
            }
          : null
      }
    >
      {children}
    </Context.Provider>
  );
}

export function useDemoSimulation(caseId: string) {
  const context = useContext(Context);
  if (!context) return null;
  return {
    get: (action: string) => context.results[`${caseId}:${action}`],
    record: (action: string, message: string) =>
      context.record(`${caseId}:${action}`, message),
  };
}
