import type { Report } from "./types";

export async function fetchReport(): Promise<Report> {
  const response = await fetch("/api/report");
  if (!response.ok) {
    throw new Error(`the server answered ${response.status}`);
  }
  return (await response.json()) as Report;
}
