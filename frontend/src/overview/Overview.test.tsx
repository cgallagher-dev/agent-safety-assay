import { fireEvent, render, screen, within } from "@testing-library/react";
import { report } from "../test/report";
import Overview from "./Overview";

function metricsRow(configuration: string) {
  const table = screen.getByRole("table", { name: "Metrics by configuration" });
  return within(table).getByRole("row", { name: new RegExp(configuration) });
}

test("each metric shows its numerator and denominator without hovering", () => {
  render(<Overview report={report} />);

  const row = metricsRow("small/off");
  for (const text of ["66.7%", "(20/30)", "40.0%", "(12/30)", "55.0%", "(11/20)", "(6/17)", "(9/18)"]) {
    expect(within(row).getByText(text, { exact: false })).toBeVisible();
  }
});

test("an undefined metric shows its reason, never zero", () => {
  render(<Overview report={report} />);

  const row = metricsRow("tiny/off");
  expect(within(row).getByText("undefined (no benign task passed)")).toBeVisible();
  expect(within(row).getAllByText(/^0\.0%$/)).toHaveLength(2);
});

test("the gate selector switches every number to that gate", () => {
  render(<Overview report={report} />);

  fireEvent.change(screen.getByLabelText("Capability gate"), { target: { value: "semantic" } });

  const row = metricsRow("small/off");
  expect(within(row).getByText("(7/15)", { exact: false })).toBeVisible();
  expect(within(row).queryByText("(11/20)", { exact: false })).toBeNull();
});
