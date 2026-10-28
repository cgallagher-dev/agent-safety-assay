import { CartesianGrid, LabelList, Scatter, ScatterChart, XAxis, YAxis } from "recharts";
import type { ConfigurationResult } from "../api/types";
import type { Gate } from "../labels";

interface Props {
  configurations: ConfigurationResult[];
  gate: Gate;
}

export default function PassVsCcAsrPlot({ configurations, gate }: Props) {
  const points = [];
  const notPlotted = [];
  for (const configuration of configurations) {
    const { benign_pass_rate, cc_asr } = configuration.gates[gate].metrics;
    if (benign_pass_rate.value === null || cc_asr.value === null) {
      notPlotted.push(`${configuration.name} (${cc_asr.undefined_reason})`);
    } else {
      points.push({
        name: configuration.name,
        benignPass: benign_pass_rate.value * 100,
        ccAsr: cc_asr.value * 100,
      });
    }
  }
  return (
    <figure>
      <ScatterChart width={560} height={380} margin={{ top: 24, right: 32, bottom: 32, left: 16 }}>
        <CartesianGrid />
        <XAxis
          type="number"
          dataKey="benignPass"
          domain={[0, 100]}
          unit="%"
          label={{ value: "Benign pass rate", position: "insideBottom", offset: -16 }}
        />
        <YAxis
          type="number"
          dataKey="ccAsr"
          domain={[0, 100]}
          unit="%"
          label={{ value: "ccASR", angle: -90, position: "insideLeft" }}
        />
        <Scatter data={points} fill="#1f5f8b" isAnimationActive={false}>
          <LabelList dataKey="name" position="top" />
        </Scatter>
      </ScatterChart>
      <figcaption>
        One point per configuration. Higher benign pass means more pairs where safety was
        tested; higher ccASR means more harm done on those pairs.
        {notPlotted.length > 0 && ` Not plotted, ccASR undefined: ${notPlotted.join(", ")}.`}
      </figcaption>
    </figure>
  );
}
