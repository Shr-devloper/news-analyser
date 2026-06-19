"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

export default function ReportsPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (kind) params.set("kind", kind);
    if (dateFrom) params.set("date_from", new Date(dateFrom).toISOString());
    try {
      setReports(await api.reports(`?${params.toString()}`));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppShell>
      <h1 className="text-2xl font-bold">Reports</h1>
      <p className="text-slate-500">Search and filter your historical briefings.</p>

      <div className="mt-5 card flex flex-wrap items-end gap-3 p-4">
        <div className="grow">
          <label className="text-xs font-medium text-slate-500">Search</label>
          <input
            className="input mt-1"
            placeholder="Search title or summary…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500">Type</label>
          <select className="input mt-1" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500">From date</label>
          <input
            type="date"
            className="input mt-1"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <button className="btn-primary" onClick={load}>
          Apply
        </button>
      </div>

      <div className="mt-6 space-y-3">
        {loading && <div className="text-slate-400">Loading…</div>}
        {!loading && reports.length === 0 && (
          <div className="card p-10 text-center text-slate-500">No reports found.</div>
        )}
        {reports.map((r) => (
          <Link key={r.id} href={`/reports/${r.id}`} className="card block p-5 hover:border-brand-300">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{r.title}</h3>
              <span className="badge capitalize">{r.kind}</span>
            </div>
            <p className="mt-2 line-clamp-2 text-sm text-slate-500">
              {r.executive_summary}
            </p>
            <div className="mt-2 text-xs text-slate-400">
              {new Date(r.report_date).toLocaleString()} · {r.event_count} events
            </div>
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
