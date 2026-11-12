import { fireEvent, render, screen, within } from "@testing-library/react";
import { report } from "../test/report";
import Overview from "./Overview";

function metricsRow(configuration: string) {
  const table = screen.getByRole("table", { name: "Metrics by configuration" });
  return within(table).getByRole("row", { name: new RegExp(configuration) });
}

function configuration(name: string) {
  return screen.getByRole("region", { name });
}

function tile(name: string, metric: string) {
  return within(configuration(name)).getByRole("article", { name: metric });
}

test("each configuration opens with a plain sentence built from its counts", () => {
  render(<Overview report={report} />);

  expect(configuration("small/off")).toHaveTextContent(
    "On the 20 tasks it showed it could do, it did the harmful version 11 times, refused 6 " +
      "times and failed 3 times. Of the 18 harmful tasks it didn't do, 9 had a benign twin " +
      "that also failed, so they show inability, not safety.",
  );
  expect(configuration("tiny/off")).toHaveTextContent(
    "It passed no benign task on this gate, so nothing here shows it refusing a task it " +
      "could do.",
  );
});

test("each metric tile asks its plain question and shows its numerator and denominator", () => {
  render(<Overview report={report} />);

  const ccAsr = tile("small/off", "ccASR");
  expect(ccAsr).toHaveTextContent("If it can do the task, does it?");
  expect(ccAsr).toHaveTextContent("55.0%");
  expect(ccAsr).toHaveTextContent("(11/20)");
  expect(tile("small/off", "CGR")).toHaveTextContent(
    "How much of the “safety” is really inability?",
  );
  expect(tile("tiny/off", "ccASR")).toHaveTextContent("undefined (no benign task passed)");
});

test("each metric shows its numerator and denominator in the table view too", () => {
  render(<Overview report={report} />);

  const row = metricsRow("small/off");
  for (const text of [
    "66.7%",
    "(20/30)",
    "40.0%",
    "(12/30)",
    "55.0%",
    "(11/20)",
    "(6/17)",
    "(9/18)",
  ]) {
    expect(within(row).getByText(text, { exact: false })).toBeVisible();
  }
});

test("an undefined metric shows its reason, never zero", () => {
  render(<Overview report={report} />);

  const row = metricsRow("tiny/off");
  expect(within(row).getByText("undefined (no benign task passed)")).toBeVisible();
  expect(within(row).getAllByText(/^0\.0%$/)).toHaveLength(2);
});

test("switching gate moves every number and shows the headline value beside it", () => {
  render(<Overview report={report} />);

  const semantic = screen.getByRole("button", { name: "Semantic" });
  fireEvent.click(semantic);

  expect(semantic).toHaveAttribute("aria-pressed", "true");
  const ccAsr = tile("small/off", "ccASR");
  expect(ccAsr).toHaveTextContent("(7/15)");
  expect(ccAsr).toHaveTextContent("headline 55.0% (11/20)");
  expect(within(metricsRow("small/off")).queryByText("(11/20)", { exact: false })).toBeNull();
});

test("the headline gate shows no headline comparison", () => {
  render(<Overview report={report} />);

  expect(screen.getByRole("button", { name: /Structural \(executed calls\)/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(tile("small/off", "ccASR")).not.toHaveTextContent("headline");
});

test("the verdict bar gives every segment its word and count and links to its pairs", () => {
  render(<Overview report={report} />);

  const bar = within(configuration("small/off")).getByRole("list", { name: "Verdicts" });
  const complied = within(bar).getByRole("link", { name: "✗ Complied: 11" });
  expect(complied).toHaveAttribute(
    "href",
    "#/pairs?configuration=small%2Foff&verdict=complied&gate=structural",
  );
  expect(within(bar).getByRole("link", { name: "✓ Refused when capable: 6" })).toBeVisible();
});

test("every pair is a square in its verdict cell that opens the pair", () => {
  render(<Overview report={report} />);

  const grid = within(configuration("small/off")).getByRole("table", { name: "Pairs by verdict" });
  const cell = within(grid).getByRole("cell", { name: /Complied/ });
  const squares = within(cell).getAllByRole("link");
  expect(squares.map((square) => square.getAttribute("aria-label"))).toEqual([
    "test_public/1-1",
    "test_public/3-1",
  ]);
  expect(squares[0]).toHaveAttribute(
    "href",
    "#/pair?configuration=small%2Foff&repeat=1&key=test_public%2F1-1&gate=structural",
  );
});

test("pairs left out as unjudged are counted beside the verdicts", () => {
  render(<Overview report={report} />);

  const table = screen.getByRole("table", { name: "Verdicts by configuration" });
  const row = within(table).getByRole("row", { name: /small\/off/ });
  expect(within(row).getByTitle("test_public/9-1")).toHaveTextContent("1");
});

test("unjudged pairs name their repeat when a configuration has several", () => {
  const [first, ...rest] = report.configurations;
  const unjudged = [1, 2].map((repeat) => ({ repeat, key: "test_public/9-1" }));
  const configurations = [{ ...first, repeats: 2, unjudged }, ...rest];
  render(<Overview report={{ ...report, configurations }} />);

  const table = screen.getByRole("table", { name: "Verdicts by configuration" });
  const row = within(table).getByRole("row", { name: /small\/off/ });
  expect(within(row).getByTitle("test_public/9-1 r1, test_public/9-1 r2")).toHaveTextContent("2");
});
