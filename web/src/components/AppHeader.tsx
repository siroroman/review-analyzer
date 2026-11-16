import type { ReactNode } from "react";

/** The header every screen shares: logo and name, and what a screen puts on the right (Claude Design canvas "Review Analyzer – návrh dashboardu"). */
export function AppHeader({ children }: { children?: ReactNode }) {
  return (
    <header className="border-b border-line bg-card">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-3.5">
        <span className="flex items-center gap-2.5">
        <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
          <rect width="28" height="28" rx="7" fill="#1b1f23" />
          <path d="M6 19l5-6 4 3 7-8" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-base font-bold">Review Analyzer</span>
        </span>
        {children && <div className="ml-auto flex flex-wrap items-center gap-2 text-sm text-muted">{children}</div>}
      </div>
    </header>
  );
}
