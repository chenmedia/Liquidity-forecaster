"use client";

import { useEffect, useState } from "react";
import { UserButton } from "@clerk/nextjs";

type Driver = { date: string; creditor: string; amount: string; currency: string };
type Inflow = { date: string; source: string; amount: string };
type Forecast = {
  severity: "GREEN" | "AMBER" | "RED";
  startDate: string;
  endDate: string;
  floor: string;
  amberThreshold: string;
  troughDate: string;
  troughBalance: string;
  shortfall: string;
  firstBreachDate: string | null;
  savingsBalance: string;
  drawOnSavingsClears: boolean;
  flags: { hasRetrying: boolean; lowConfidence: boolean; fxVariable: boolean; baselineApplied: boolean };
  curve: { date: string; balance: string }[];
  drivers: Driver[];
  inflows: Inflow[];
};

const nok = (s: string) =>
  Math.round(parseFloat(s)).toLocaleString("en-US").replace(/,/g, " ") + " NOK";

export default function Dashboard() {
  const [data, setData] = useState<Forecast | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetch("/api/forecast", { cache: "no-store" })
      .then(async (res) => {
        if (res.status === 403) throw new Error("Your account is not permitted to view this dashboard.");
        if (res.status === 404)
          throw new Error("No forecast has been published yet — the scheduled run will publish one (or run `publish`).");
        if (!res.ok) throw new Error(`Forecast unavailable (HTTP ${res.status}).`);
        return res.json();
      })
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <header>
        <h1>Liquidity Forecaster</h1>
        {data && <span className={`badge ${data.severity}`}>{data.severity}</span>}
        <span className="muted" style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center" }}>
          {data && <span>Horizon to {data.endDate}</span>}
          <UserButton afterSignOutUrl="/sign-in" />
        </span>
      </header>
      <main>
        {error && <div className="card error">{error}</div>}
        {!data && !error && <div className="card muted">Loading forecast…</div>}
        {data && <Report d={data} />}
      </main>
    </>
  );
}

function Report({ d }: { d: Forecast }) {
  const leadDays = Math.round(
    (new Date(d.firstBreachDate || d.troughDate).getTime() - new Date(d.startDate).getTime()) / 86400000,
  );
  const stats: [string, string][] = [
    ["Trough", `${nok(d.troughBalance)} · ${d.troughDate}`],
    ["Floor", nok(d.floor)],
    ["Shortfall", d.shortfall === "0" ? "—" : nok(d.shortfall)],
    ["Lead time", d.firstBreachDate ? `${leadDays} days` : "—"],
    ["Draw on Savings clears?", d.drawOnSavingsClears ? "Yes" : "No"],
    ["Savings", nok(d.savingsBalance)],
  ];
  const flags = [
    d.flags.baselineApplied && "run-rate baseline",
    d.flags.fxVariable && "FX-variable",
    d.flags.lowConfidence && "low confidence",
    d.flags.hasRetrying && "payment retrying — short now",
  ].filter(Boolean) as string[];

  return (
    <>
      <div className="card">
        <div className="grid">
          {stats.map(([k, v]) => (
            <div className="stat" key={k}>
              <div className="k">{k}</div>
              <div className="v">{v}</div>
            </div>
          ))}
        </div>
        {flags.length > 0 && (
          <div className="chips">
            {flags.map((f) => (
              <span className="chip" key={f}>{f}</span>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="muted" style={{ marginBottom: 8 }}>Projected operational balance</div>
        <Chart d={d} />
      </div>

      <div className="card">
        <div className="muted" style={{ marginBottom: 8 }}>Drivers of the dip</div>
        <Rows rows={d.drivers.map((r) => [r.date, r.creditor, nok(r.amount)])} cols={["Date", "Creditor", "Amount"]} />
      </div>

      {d.inflows.length > 0 && (
        <div className="card">
          <div className="muted" style={{ marginBottom: 8 }}>Expected inflows</div>
          <Rows rows={d.inflows.map((r) => [r.date, r.source, nok(r.amount)])} cols={["Date", "Source", "Amount"]} />
        </div>
      )}
    </>
  );
}

function Rows({ cols, rows }: { cols: string[]; rows: string[][] }) {
  return (
    <table>
      <thead>
        <tr>{cols.map((c, i) => <th key={c} className={i === 2 ? "num" : ""}>{c}</th>)}</tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr><td className="muted" colSpan={cols.length}>None</td></tr>
        ) : (
          rows.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j} className={j === 2 ? "num" : ""}>{c}</td>)}</tr>
          ))
        )}
      </tbody>
    </table>
  );
}

function Chart({ d }: { d: Forecast }) {
  const W = 900, H = 260, pad = 48;
  const pts = d.curve.map((p) => parseFloat(p.balance));
  const floor = parseFloat(d.floor), amber = parseFloat(d.amberThreshold);
  const lo = Math.min(...pts, floor) * 0.98, hi = Math.max(...pts, amber) * 1.02;
  const x = (i: number) => pad + (i * (W - 2 * pad)) / (pts.length - 1 || 1);
  const y = (v: number) => H - pad - ((v - lo) * (H - 2 * pad)) / (hi - lo || 1);
  const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const color = d.severity === "RED" ? "var(--red)" : d.severity === "AMBER" ? "var(--amber)" : "var(--green)";
  const floorY = y(floor).toFixed(1), amberY = y(amber).toFixed(1);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Projected balance">
      <line x1={pad} y1={floorY} x2={W - pad} y2={floorY} stroke="var(--red)" strokeDasharray="5 4" opacity="0.7" />
      <line x1={pad} y1={amberY} x2={W - pad} y2={amberY} stroke="var(--amber)" strokeDasharray="3 4" opacity="0.5" />
      <path d={line} fill="none" stroke={color} strokeWidth="2" />
      <text x={pad} y={Number(floorY) - 5}>floor {nok(d.floor)}</text>
      <text x={pad} y={H - 16}>{d.curve[0].date}</text>
      <text x={W - pad} y={H - 16} textAnchor="end">{d.curve[d.curve.length - 1].date}</text>
    </svg>
  );
}
