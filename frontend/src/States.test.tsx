import { fireEvent, render, screen, within } from "@testing-library/react";
import App from "./App";
import { report } from "./test/report";

function serveReport() {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(report))));
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

test("the report shows a loading state until it arrives", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => {})),
  );
  render(<App />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading the report");
});

test("a dashboard server that has stopped says to check it is still running", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  render(<App />);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Couldn't load the report");
  expect(alert).toHaveTextContent("assay dashboard is still running");
});

test("a report error from the server shows the server's own advice", async () => {
  const detail = "No evidence.jsonl in results/4b. Run assay judge first.";
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 400 })),
  );
  render(<App />);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(detail);
  expect(alert).not.toHaveTextContent("still running");
});

test("a pair that is not in the report says so and links back to the overview", async () => {
  serveReport();
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F99-1";
  render(<App />);

  await screen.findByText(/No pair test_public\/99-1 in this run/);
  const status = screen.getByRole("status");
  expect(within(status).getByRole("link", { name: "Back to the overview" })).toHaveAttribute(
    "href",
    "#/",
  );
});

test("filters that match no pairs offer to clear them", async () => {
  serveReport();
  window.location.hash = "#/pairs?category=Cybercrime&verdict=complied";
  render(<App />);

  await screen.findByText(/No pairs match these filters/);
  const status = screen.getByRole("status");
  fireEvent.click(within(status).getByRole("link", { name: "Clear filters" }));

  expect(await screen.findByRole("table", { name: "Pairs" })).toBeVisible();
});
