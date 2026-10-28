import type { Report } from "../api/types";
import { type Gate, GATES, VERDICT_LABELS, VERDICTS } from "../labels";
import { href } from "../route";

interface FilterProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}

function Filter({ label, value, options, onChange }: FilterProps) {
  const id = `filter-${label.toLowerCase().replace(/ /g, "-")}`;
  return (
    <span className="filter">
      <label htmlFor={id}>{label}</label>{" "}
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </span>
  );
}

function yesNo(value: boolean): string {
  return value ? "yes" : "no";
}

export default function PairList({ report, params }: { report: Report; params: URLSearchParams }) {
  const filters = {
    configuration: params.get("configuration") ?? "",
    category: params.get("category") ?? "",
    verdict: params.get("verdict") ?? "",
    gate: (params.get("gate") ?? report.headline_gate) as Gate,
  };
  const pairs = report.pairs.filter(
    (pair) =>
      (!filters.configuration || pair.configuration === filters.configuration) &&
      (!filters.category || pair.category === filters.category) &&
      (!filters.verdict || pair.gates[filters.gate].verdict === filters.verdict),
  );
  const all = { value: "", label: "All" };
  const categories = [...new Set(report.pairs.map((pair) => pair.category))].sort();
  const choose = (name: keyof typeof filters) => (value: string) => {
    window.location.hash = href("pairs", { ...filters, [name]: value });
  };

  return (
    <section>
      <h2>Pairs</h2>
      <p className="filters">
        <Filter
          label="Configuration"
          value={filters.configuration}
          options={[all, ...report.configurations.map(({ name }) => ({ value: name, label: name }))]}
          onChange={choose("configuration")}
        />
        <Filter
          label="Category"
          value={filters.category}
          options={[all, ...categories.map((name) => ({ value: name, label: name }))]}
          onChange={choose("category")}
        />
        <Filter
          label="Verdict"
          value={filters.verdict}
          options={[all, ...VERDICTS.map(({ name, label }) => ({ value: name, label }))]}
          onChange={choose("verdict")}
        />
        <Filter
          label="Capability gate"
          value={filters.gate}
          options={GATES.map(({ name, label }) => ({ value: name, label }))}
          onChange={choose("gate")}
        />
      </p>
      <p>
        {pairs.length} {pairs.length === 1 ? "pair" : "pairs"}
      </p>
      <table aria-label="Pairs">
        <thead>
          <tr>
            <th scope="col">Configuration</th>
            <th scope="col">Repeat</th>
            <th scope="col">Key</th>
            <th scope="col">Category</th>
            <th scope="col">Benign task passed</th>
            <th scope="col">Harmful task executed</th>
            <th scope="col">Refused</th>
            <th scope="col">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {pairs.map((pair) => {
            const result = pair.gates[filters.gate];
            return (
              <tr key={`${pair.configuration} ${pair.repeat} ${pair.key}`}>
                <td>{pair.configuration}</td>
                <td>{pair.repeat}</td>
                <td>
                  <a
                    href={href("pair", {
                      configuration: pair.configuration,
                      repeat: pair.repeat,
                      key: pair.key,
                      gate: filters.gate,
                    })}
                  >
                    {pair.key}
                  </a>
                </td>
                <td>{pair.category}</td>
                <td>{yesNo(result.benign_passed)}</td>
                <td>{yesNo(result.executed)}</td>
                <td>{yesNo(pair.refused)}</td>
                <td>{VERDICT_LABELS[result.verdict]}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
