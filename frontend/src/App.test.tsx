import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { report } from "./test/report";

test("renders the overview from the API's report", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(report)));
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByText(/20261112T2130Z-7f3a/)).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith("/api/report");
  vi.unstubAllGlobals();
});

test("opening another page starts at the top", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(report))));
  const scrollTo = vi.fn();
  vi.stubGlobal("scrollTo", scrollTo);
  render(<App />);
  await screen.findByText(/20261112T2130Z-7f3a/);

  window.location.hash = "#/pairs";
  window.dispatchEvent(new HashChangeEvent("hashchange"));

  await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(0, 0));
  vi.unstubAllGlobals();
  window.location.hash = "";
});
