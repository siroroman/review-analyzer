const KEY = "demo-token";

/**
 * The Demo token of this tab. It arrives once in the link (`?token=`), is kept for the session only and
 * is removed from the address bar so it is not copied along with the page.
 */
export function readDemoToken(): string | null {
  const url = new URL(window.location.href);
  const given = url.searchParams.get("token");
  if (given) {
    try {
      sessionStorage.setItem(KEY, given);
    } catch {
      /* storage blocked: the token lives until the page reloads */
    }
    url.searchParams.delete("token");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    return given;
  }
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}
