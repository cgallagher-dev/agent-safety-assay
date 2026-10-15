import type { ConfigurationResult } from "../api/types";
import { type Gate, VERDICTS } from "../labels";

interface Props {
  configurations: ConfigurationResult[];
  gate: Gate;
}

export default function VerdictTable({ configurations, gate }: Props) {
  return (
    <table aria-label="Verdicts by configuration">
      <thead>
        <tr>
          <th scope="col" rowSpan={2}>
            Configuration
          </th>
          <th scope="colgroup" colSpan={3}>
            Benign task passed
          </th>
          <th scope="colgroup" colSpan={3}>
            Benign task failed
          </th>
          <th scope="col" rowSpan={2}>
            Executed and refused
          </th>
          <th scope="col" rowSpan={2}>
            Benign refusals
          </th>
        </tr>
        <tr>
          {VERDICTS.map((verdict) => (
            <th scope="col" key={verdict.name}>
              {verdict.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {configurations.map((configuration) => {
          const result = configuration.gates[gate];
          return (
            <tr key={configuration.name}>
              <th scope="row">{configuration.name}</th>
              {VERDICTS.map((verdict) => (
                <td key={verdict.name}>{result.verdicts[verdict.name]}</td>
              ))}
              <td>{result.overlap}</td>
              <td>{result.benign_refusals}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
