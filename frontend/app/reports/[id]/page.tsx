"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

export default function ReportDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [report, setReport] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.report(id).then(setReport).catch((e) => setErr(e.message));
  }, [id]);

  if (err) return <AppShell><div className="text-red-600">{err}</div></AppShell>;
  if (!report) return <AppShell><div className="text-slate-400">Loading…</div></AppShell>;

  const data = report.data || {};

  return (
    <AppShell>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{report.title}</h1>
          <p className="text-sm text-slate-500">
            {new Date(report.report_date).toLocaleString()} · {report.event_count} events
          </p>
        </div>
        <div className="flex gap-2">
          <a className="btn-ghost" href={api.downloadUrl(id, "pdf")} target="_blank">PDF</a>
          <a className="btn-ghost" href={api.downloadUrl(id, "html")} target="_blank">HTML</a>
          <a className="btn-ghost" href={api.downloadUrl(id, "md")} target="_blank">Markdown</a>
        </div>
      </div>

      <div className="mt-6 card border-brand-200 bg-brand-50 p-6">
        <h2 className="font-bold text-brand-700">Executive Summary</h2>
        <p className="mt-2 text-slate-700">{data.executive_summary}</p>
      </div>

      {data.sections &&
        Object.entries(data.sections).map(([section, items]: any) =>
          items?.length ? (
            <section key={section} className="mt-8">
              <h2 className="mb-3 border-l-4 border-brand-600 pl-3 text-lg font-bold">
                {section}
              </h2>
              <div className="space-y-3">
                {items.map((it: any, i: number) => (
                  <div key={it.id} className="card p-5">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-semibold">
                        {i + 1}. {it.headline}
                      </h3>
                      {it.score && <span className="badge">{it.score}</span>}
                    </div>
                    <div className="mt-1 text-xs font-semibold uppercase text-brand-600">
                      {it.category} · {it.publishers} publisher(s)
                    </div>
                    {it.detailed && <p className="mt-2 text-sm text-slate-700">{it.detailed}</p>}
                    {it.why_it_matters && (
                      <p className="mt-2 text-sm">
                        <span className="font-semibold">Why it matters: </span>
                        {it.why_it_matters}
                      </p>
                    )}
                    {it.key_takeaways?.length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-sm text-slate-600">
                        {it.key_takeaways.map((t: string, k: number) => (
                          <li key={k}>{t}</li>
                        ))}
                      </ul>
                    )}
                    {it.url && (
                      <a href={it.url} target="_blank" className="mt-2 inline-block text-sm font-semibold text-brand-600">
                        Read full coverage →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ) : null
        )}

      {data.trending_topics?.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-bold">Trending Topics</h2>
          <div className="flex flex-wrap gap-2">
            {data.trending_topics.map((t: any) => (
              <span key={t.topic} className="badge">{t.topic} · {t.count}</span>
            ))}
          </div>
        </section>
      )}

      {data.tomorrow_watchlist?.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-bold">Tomorrow&apos;s Watchlist</h2>
          <ul className="space-y-2">
            {data.tomorrow_watchlist.map((it: any, i: number) => (
              <li key={i} className="card p-3 text-sm">
                <span className="font-semibold text-brand-600">{it.category}:</span> {it.headline}
              </li>
            ))}
          </ul>
        </section>
      )}
    </AppShell>
  );
}
