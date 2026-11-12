import { useEffect, useState } from "react";
import { fetchReport } from "./api/client";
import type { Report } from "./api/types";
import Overview from "./overview/Overview";
import PairDetailPage from "./pairs/PairDetail";
import PairList from "./pairs/PairList";
import Status, { loadError } from "./Status";
import { useRoute } from "./route";

// Every number shown here comes from the report the Python backend builds.
// The dashboard renders results; it never computes a metric.
export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const { page, params } = useRoute();

  useEffect(() => {
    fetchReport().then(setReport, setError);
  }, []);

  return (
    <main>
      <header className="app-header">
        <p className="brand">
          <a href="#/">ASSAY</a> <span>capability-conditioned safety report</span>
        </p>
        <nav aria-label="Pages">
          <a href="#/" aria-current={page === "" ? "page" : undefined}>
            Overview
          </a>
          <a href="#/pairs" aria-current={page === "pairs" ? "page" : undefined}>
            Pairs
          </a>
        </nav>
        {report && (
          <p className="run">
            {report.runs
              .map((run) => `Run ${run.run_id} · judge ${run.judge} · ${run.splits.join(", ")}`)
              .join("; ")}{" "}
            · built{" "}
            {new Date(report.created_at).toLocaleString("en-IE", {
              dateStyle: "medium",
              timeStyle: "short",
            })}{" "}
            · ASSAY {report.assay_version}
          </p>
        )}
      </header>
      {error && (
        <Status kind="error" title="Couldn't load the report">
          {loadError(error)}
        </Status>
      )}
      {!report && !error && <Status kind="loading" title="Loading the report…" />}
      {report && page === "pairs" && <PairList report={report} params={params} />}
      {report && page === "pair" && (
        <PairDetailPage key={params.toString()} report={report} params={params} />
      )}
      {report && page !== "pairs" && page !== "pair" && <Overview report={report} />}
    </main>
  );
}
