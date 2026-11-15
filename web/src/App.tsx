import { useMemo } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { createApi } from "./api/client";
import { ApiProvider } from "./api/context";
import { ProgressScreen } from "./screens/ProgressScreen";
import { SearchScreen } from "./screens/SearchScreen";
import { readDemoToken } from "./token";

/** The Demo token comes with the link; without it no screen can call the API. */
export function App() {
  const token = useMemo(readDemoToken, []);
  const api = useMemo(() => (token ? createApi(token) : null), [token]);
  if (!api) {
    return (
      <main className="mx-auto max-w-xl p-6">
        <p role="alert">Chybí odkaz s přístupem. Otevřete prosím odkaz, který jste dostali.</p>
      </main>
    );
  }
  return (
    <ApiProvider api={api}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<SearchScreen />} />
          <Route path="/runs/:id" element={<ProgressScreen />} />
          <Route path="*" element={<SearchScreen />} />
        </Routes>
      </BrowserRouter>
    </ApiProvider>
  );
}
