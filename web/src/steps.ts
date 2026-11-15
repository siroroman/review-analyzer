import type { RunStatus } from "./api/client";

/** The steps of a Run in order, as the progress screen lists them. */
export const STEPS: { status: RunStatus; label: string }[] = [
  { status: "queued", label: "Ve frontě" },
  { status: "downloading", label: "Stahování recenzí" },
  { status: "classifying", label: "Třídění recenzí do témat" },
  { status: "analyzing", label: "Analýza a doporučení" },
];

export const FINAL: readonly RunStatus[] = ["done", "partial", "failed"];

export function formatCost(cost: string): string {
  const value = Number(cost);
  return `${value.toFixed(value < 1 ? 3 : 2)} USD`;
}
