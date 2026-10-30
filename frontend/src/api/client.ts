import type { PairDetail, Report } from "./types";

// The backend's own message says what failed and what to do; pages add the final full stop.
async function reason(response: Response): Promise<string> {
  try {
    const { detail } = (await response.json()) as { detail?: unknown };
    if (typeof detail === "string") {
      return detail.replace(/\.$/, "");
    }
  } catch {
    // Not JSON, so there is no message to show.
  }
  return `the server answered ${response.status}`;
}

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await reason(response));
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
