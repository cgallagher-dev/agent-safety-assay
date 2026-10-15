import { useEffect, useState } from "react";
import { fetchReport } from "./api/client";
import type { Report } from "./api/types";
import Overview from "./overview/Overview";

// Every number shown here comes from report.json built by the Python backend.
// The dashboard renders results; it never computes a metric.
export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReport().then(setReport, (reason: Error) => setError(reason.message));
  }, []);

  return (
    <main>
      <header>
        <h1>ASSAY dashboard</h1>
        {report && (
          <p className="run">
            {report.runs.map((run) => `Run ${run.run_id}, judge ${run.judge}`).join("; ")}
          </p>
        )}
      </header>
      {error && <p role="alert">Could not load the report: {error}.</p>}
      {!report && !error && <p>Loading the report...</p>}
      {report && <Overview report={report} />}
    </main>
  );
}
