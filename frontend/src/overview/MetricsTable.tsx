import type { ConfigurationResult } from "../api/types";
import { type Gate, METRICS } from "../labels";
import Rate from "./Rate";

interface Props {
  configurations: ConfigurationResult[];
  gate: Gate;
}

export default function MetricsTable({ configurations, gate }: Props) {
  return (
    <table aria-label="Metrics by configuration">
      <thead>
        <tr>
          <th scope="col">Configuration</th>
          <th scope="col">Pairs</th>
          {METRICS.map((metric) => (
            <th scope="col" key={metric.name}>
              {metric.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {configurations.map((configuration) => (
          <tr key={configuration.name}>
            <th scope="row">{configuration.name}</th>
            <td>{configuration.pairs}</td>
            {METRICS.map((metric) => (
              <td key={metric.name}>
                <Rate rate={configuration.gates[gate].metrics[metric.name]} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
