import { render, screen } from "@testing-library/react";
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
