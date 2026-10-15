import type { PairDetail, Report } from "./types";

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

export function fetchPair(configuration: string, repeat: number, key: string): Promise<PairDetail> {
  const query = new URLSearchParams({ configuration, repeat: String(repeat), key });
  return get<PairDetail>(`/api/pair?${query}`);
}
