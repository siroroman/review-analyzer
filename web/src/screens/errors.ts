import { ApiError } from "../api/client";

/** What to tell the user about a failed call; `what` finishes the sentence, e.g. "najít pobočky". */
export function describeError(error: unknown, what: string): string {
  const status = error instanceof ApiError ? error.status : 0;
  if (status === 401) return "Chybí platný odkaz s přístupem. Otevřete prosím odkaz, který jste dostali.";
  if (status === 429) return "Dosáhli jste limitu požadavků nebo denního limitu analýz. Zkuste to později.";
  if (status === 0) return `Nepodařilo se spojit se serverem, nelze ${what}. Zkuste to znovu.`;
  return `Nepodařilo se ${what}. Zkuste to znovu za chvíli.`;
}
