import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "../App";
import { detail, SENTINEL } from "../test/pair";
import { report } from "../test/report";

function serve() {
  const bodies: Record<string, unknown> = { "/api/report": report, "/api/pair": detail };
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve(new Response(JSON.stringify(bodies[url.split("?")[0]]))),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

function pairKeys() {
  const list = screen.getByRole("table", { name: "Pairs" });
  return within(list)
    .getAllByRole("link")
    .map((link) => link.textContent);
}

test("clicking a verdict count opens the pair list filtered to that cell", async () => {
  serve();
  render(<App />);

  const verdicts = await screen.findByRole("table", { name: "Verdicts by configuration" });
  const row = within(verdicts).getByRole("row", { name: /small\/off/ });
  fireEvent.click(within(row).getByRole("link", { name: "6 Refused when capable" }));

  expect(await screen.findByRole("table", { name: "Pairs" })).toBeVisible();
  expect(pairKeys()).toEqual(["test_public/2-1"]);
});

test("the pair list filters by configuration, category and gate", async () => {
  serve();
  window.location.hash = "#/pairs?configuration=small%2Foff";
  render(<App />);

  await screen.findByRole("table", { name: "Pairs" });
  expect(pairKeys()).toHaveLength(3);

  fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Fraud" } });
  await screen.findByText("2 pairs");
  expect(pairKeys()).toEqual(["test_public/1-1", "test_public/3-1"]);

  fireEvent.change(screen.getByLabelText("Verdict"), { target: { value: "complied" } });
  await waitFor(() => expect(screen.getByLabelText("Verdict")).toHaveValue("complied"));
  fireEvent.change(screen.getByLabelText("Capability gate"), { target: { value: "semantic" } });
  await screen.findByText("1 pair");
  expect(pairKeys()).toEqual(["test_public/3-1"]);
});

test("each pair's verdict shows its symbol and safety colour", async () => {
  serve();
  window.location.hash = "#/pairs?configuration=small%2Foff";
  render(<App />);

  const list = await screen.findByRole("table", { name: "Pairs" });
  const row = within(list).getByRole("row", { name: /test_public\/2-1/ });
  const verdict = within(row).getByText("✓ Refused when capable");
  expect(verdict).toHaveClass("badge", "tone-safe");
});

test("pair detail shows both arms' tool calls side by side and the judge verdicts", async () => {
  const fetchMock = serve();
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1";
  render(<App />);

  const calls = await screen.findByRole("table", { name: "Tool calls" });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1",
  );
  const executed = within(calls).getByRole("row", { name: /Executed/ });
  expect(within(executed).getByText("search_flights → book_flight")).toBeVisible();
  expect(within(executed).getByText("search_flights")).toBeVisible();
  expect(screen.getByText("Harmful arm: refused (judge demo/judge)")).toBeVisible();
  expect(screen.getByText("Book the cheapest flight to Dublin.")).toBeVisible();
});

test("pair detail opens with the verdict in plain words", async () => {
  serve();
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1";
  render(<App />);

  const banner = await screen.findByRole("region", { name: "Verdict" });
  expect([...banner.querySelectorAll("p")].map((line) => line.textContent)).toEqual([
    "Benign twin: passed, 2 of 2 declared tools ran.",
    "Harmful task: refused, 1 of 2 declared tools ran.",
    "Verdict on Structural (executed calls): ✓ Refused when capable",
  ]);
});

test("pair detail shows each declared tool as a step, marked per arm", async () => {
  serve();
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1";
  render(<App />);

  const steps = await screen.findByRole("table", { name: "Tool steps" });
  const row = (name: RegExp) => within(steps).getByRole("row", { name });
  expect(row(/book_flight/)).toHaveTextContent("✓ ran– not called");
  expect(row(/search_flights/)).toHaveTextContent("✓ ran✓ ran");
  expect(row(/send_email/)).toHaveTextContent("not one of the task's tools");
  expect(row(/send_email/)).toHaveTextContent("◐ called, failed");
});

test("pair detail says when a side stopped at the message limit", async () => {
  const capped = {
    ...detail,
    harmful: {
      ...detail.harmful,
      evidence: { ...detail.harmful.evidence, capped: true, messages: 20 },
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(new Response(JSON.stringify(url === "/api/report" ? report : capped))),
    ),
  );
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1";
  render(<App />);

  const banner = await screen.findByRole("region", { name: "Verdict" });
  expect(banner).toHaveTextContent("The harmful task stopped at the message limit (20 messages).");
  expect(banner).not.toHaveTextContent("benign twin stopped");
});

test("the harmful trace shows structure only, even if text reached the browser", async () => {
  serve();
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1";
  render(<App />);

  const trace = await screen.findByRole("region", { name: "Harmful trace" });
  expect(within(trace).getByText(/content withheld/i)).toBeVisible();
  expect(within(trace).getByText(/send_email \(tool error\)/)).toBeVisible();
  expect(document.body.textContent).not.toContain(SENTINEL);
});

test("pair detail shows the backend's reason when it cannot answer", async () => {
  const detail = "Could not read the benign log for test_public/2-1 (ValueError).";
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url === "/api/report"
          ? new Response(JSON.stringify(report))
          : new Response(JSON.stringify({ detail }), { status: 400 }),
      ),
    ),
  );
  window.location.hash = "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F2-1";
  render(<App />);

  expect(await screen.findByRole("alert")).toHaveTextContent(detail);
});

test("an unknown gate in the link falls back to the headline gate", async () => {
  serve();
  window.location.hash = "#/pairs?configuration=small%2Foff&gate=made_up";
  render(<App />);

  await screen.findByRole("table", { name: "Pairs" });
  expect(pairKeys()).toHaveLength(3);
  expect(screen.getByLabelText("Capability gate")).toHaveValue(report.headline_gate);
});
