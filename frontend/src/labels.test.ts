import shown from "./labels.json";
import { paintPalette, VERDICTS } from "./labels";

test("the dashboard paints each tone in the palette's colour", () => {
  paintPalette(document.documentElement);

  for (const [tone, { colour }] of Object.entries(shown.tones)) {
    expect(document.documentElement.style.getPropertyValue(`--${tone}`)).toBe(
      colour,
    );
  }
});

test("verdicts read as sentence-case words", () => {
  expect(VERDICTS.map(({ label }) => label)).toContain(
    "Refused with capability untested",
  );
});
