/** The header every screen shares: logo and name (Claude Design canvas "Review Analyzer – návrh dashboardu"). */
export function AppHeader() {
  return (
    <header className="border-b border-line bg-card">
      <div className="mx-auto flex max-w-7xl items-center gap-2.5 px-6 py-3.5">
        <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
          <rect width="28" height="28" rx="7" fill="#1b1f23" />
          <path d="M6 19l5-6 4 3 7-8" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-base font-bold">Review Analyzer</span>
      </div>
    </header>
  );
}
