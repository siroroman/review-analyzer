import type { RunStatus } from "./api/client";

/** The steps of a Run in order, as the progress screen lists them. */
export const STEPS: { status: RunStatus; label: string; hint?: string }[] = [
  { status: "queued", label: "Ve frontě" },
  { status: "downloading", label: "Stahování recenzí" },
  { status: "classifying", label: "Třídění recenzí do témat" },
  { status: "analyzing", label: "Analýza a doporučení", hint: "Trendy, poklesy, shrnutí" },
];

/** The key of a step in the API's per-step cost. */
export const COST_KEY = { downloading: "downloading", classifying: "classifying", analyzing: "analysis" } as const;

export const SOURCE_NAMES: Record<string, string> = { google_maps: "Google Maps", firmy_cz: "Firmy.cz" };

/** A count the Czech way: 1 352, with a non-breaking space. */
export const formatCount = (n: number): string => n.toLocaleString("cs-CZ");

export const FINAL: readonly RunStatus[] = ["done", "partial", "failed"];

/** The cost as the Result screen shows it. */
export function formatCost(cost: string): string {
  const value = Number(cost);
  return `${value.toFixed(value < 1 ? 3 : 2)} USD`;
}

/** The cost as the Progress screen shows it, in Czech notation: 0,35 USD; three decimals under a cent so a small spend is not zero. */
export function formatUsd(cost: string): string {
  const value = Number(cost);
  const digits = value > 0 && value < 0.01 ? 3 : 2;
  return `${value.toFixed(digits).replace(".", ",")} USD`;
}
