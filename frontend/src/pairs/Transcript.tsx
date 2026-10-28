import type { Turn } from "../api/types";

function toolResult(turn: Turn): string {
  return `tool result: ${turn.function}${turn.tool_error ? " (tool error)" : ""}`;
}

export function Transcript({ turns }: { turns: Turn[] }) {
  return (
    <ol className="transcript">
      {turns.map((turn, index) => (
        <li key={index}>
          <strong>{turn.role === "tool" ? toolResult(turn) : turn.role}</strong>
          {turn.reasoning && (
            <details>
              <summary>Reasoning</summary>
              <p className="text">{turn.reasoning}</p>
            </details>
          )}
          {turn.text && <p className="text">{turn.text}</p>}
          {turn.tool_calls.map((call, number) => (
            <pre key={number}>
              {`${call.function}(${JSON.stringify(call.arguments ?? {}, null, 2)})`}
            </pre>
          ))}
        </li>
      ))}
    </ol>
  );
}

// Reads only roles, tool names and error flags, whatever else the response holds.
export function TraceStructure({ turns }: { turns: Turn[] }) {
  return (
    <ol className="transcript">
      {turns.map((turn, index) => {
        const calls = turn.tool_calls.map((call) => call.function);
        let line: string = turn.role;
        if (turn.role === "tool") {
          line = toolResult(turn);
        } else if (calls.length > 0) {
          line = `${turn.role}: called ${calls.join(", ")}`;
        }
        return <li key={index}>{line}</li>;
      })}
    </ol>
  );
}
