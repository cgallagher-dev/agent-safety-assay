import type { Report } from "./types";

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`the server answered ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchReport(): Promise<Report> {
  return get<Report>("/api/report");
}
