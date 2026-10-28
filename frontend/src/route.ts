import { useEffect, useState } from "react";

export interface Route {
  page: string;
  params: URLSearchParams;
}

// Pages live in the URL hash, so links, reloads and the back button work without a router.
export function useRoute(): Route {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => setHash(window.location.hash);
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  const [page, query = ""] = hash.replace(/^#\/?/, "").split("?");
  return { page, params: new URLSearchParams(query) };
}

export function href(page: string, params: Record<string, string | number> = {}): string {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== "") {
      query.set(name, String(value));
    }
  }
  const text = query.toString();
  return text ? `#/${page}?${text}` : `#/${page}`;
}
