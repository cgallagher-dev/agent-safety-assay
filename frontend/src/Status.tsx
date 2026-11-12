import type { ReactNode } from "react";

type Kind = "loading" | "empty" | "error";

const SYMBOLS: Record<Kind, string> = { loading: "●", empty: "–", error: "✗" };

// One look for every loading, empty and error state, so none reads as a result.
export default function Status({
  kind,
  title,
  children,
}: {
  kind: Kind;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className={`status status-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <p className="status-title">
        <span aria-hidden="true">{SYMBOLS[kind]}</span> {title}
      </p>
      {children}
    </div>
  );
}

// fetch rejects with a TypeError only when no answer came back at all.
export function loadError(error: Error): ReactNode {
  if (error instanceof TypeError) {
    return (
      <p>
        The dashboard server isn't answering. Check that <code>assay dashboard</code> is still
        running in your terminal, then reload this page.
      </p>
    );
  }
  return <p>{`${error.message}.`}</p>;
}
