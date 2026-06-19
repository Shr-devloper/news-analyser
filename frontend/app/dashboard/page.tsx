"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="card p-5">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-3xl font-bold">{value ?? "—"}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<any>(null);
  const [latest, setLatest] = useState<any>(null);
  const [err, setErr] = useState("");
  const [running, setRunning] = useState(false);

  async function load() {
    try {
      const [o, l] = await Promise.allSettled([
        api.analyticsOverview(),
        api.latestReport(),
      ]);
      if (o.status === "fulfilled") setOverview(o.value);
      if (l.status === "fulfilled") setLatest(l.value);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runNow() {
    setRunning(true);
    setErr("");
    try {
      await api.runPipeline();
      setErr("Pipeline queued — refresh in a minute to see the new report.");
    } catch (e: any) {
      setErr(e.message || "Failed to queue pipeline (admin only).");
    } finally {
      setRunning(false);
    }
  }

  const data = latest?.data;

  return (
    <AppShell>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Good day, {user?.full_name || "there"} 👋</h1>
          <p className="text-slate-500">Here's your latest intelligence snapshot.</p>
        </div>
        {user?.role === "admin" && (
          <button className="btn-primary" onClick={runNow} disabled={running}>
            {running ? "Queuing…" : "Run pipeline now"}
          </button>
        )}
      </div>

      {err && (
        <div className="mt-4 rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-800">
          {err}
        </div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Reports" value={overview?.totals?.reports} />
        <Stat label="Articles" value={overview?.totals?.articles} />
        <Stat label="Unique events" value={overview?.totals?.events} />
        <Stat label="Sources" value={overview?.totals?.sources} />
      </div>

      {latest ? (
        <div className="mt-8 card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">{latest.title}</h2>
            <Link href={`/reports/${latest.id}`} className="btn-ghost">
              Open full report →
            </Link>
          </div>
          <p className="mt-3 text-slate-700">{data?.executive_summary}</p>

          {data?.sections &&
            Object.entries(data.sections).map(([section, items]: any) =>
              items?.length ? (
                <div key={section} className="mt-6">
                  <h3 className="mb-2 font-semibold text-brand-700">{section}</h3>
                  <ul className="space-y-2">
                    {items.slice(0, 3).map((it: any) => (
                      <li key={it.id} className="flex items-start gap-3">
                        {it.score && <span className="badge mt-0.5">{it.score}</span>}
                        <div>
                          <a href={it.url} target="_blank" className="font-medium hover:text-brand-700">
                            {it.headline}
                          </a>
                          {it.two_line && (
                            <p className="text-sm text-slate-500">{it.two_line}</p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null
            )}
        </div>
      ) : (
        <div className="mt-8 card p-10 text-center text-slate-500">
          No reports yet. {user?.role === "admin" && "Click “Run pipeline now” to generate the first one."}
        </div>
      )}
    </AppShell>
  );
}
