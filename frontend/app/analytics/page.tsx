"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

const COLORS = ["#4f46e5", "#6366f1", "#818cf8", "#a5b4fc", "#c7d2fe", "#3730a3", "#4338ca"];

export default function AnalyticsPage() {
  const [categories, setCategories] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [email, setEmail] = useState<any>({});

  useEffect(() => {
    api.analyticsCategories().then(setCategories).catch(() => {});
    api.analyticsSources().then(setSources).catch(() => {});
    api.analyticsEmail().then(setEmail).catch(() => {});
  }, []);

  return (
    <AppShell>
      <h1 className="text-2xl font-bold">Analytics</h1>
      <p className="text-slate-500">Coverage, source reliability and delivery health.</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="mb-4 font-bold">Category distribution</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={categories}
                dataKey="count"
                nameKey="category"
                outerRadius={100}
                label={(e) => e.category}
              >
                {categories.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <h2 className="mb-4 font-bold">Source reliability</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={sources} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 1]} />
              <YAxis type="category" dataKey="name" width={110} fontSize={11} />
              <Tooltip />
              <Bar dataKey="reliability" fill="#4f46e5" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-6 card p-6">
        <h2 className="mb-4 font-bold">Email delivery</h2>
        <div className="flex gap-6">
          {["sent", "failed", "pending"].map((s) => (
            <div key={s} className="text-center">
              <div className="text-3xl font-bold">{email[s] || 0}</div>
              <div className="text-sm capitalize text-slate-500">{s}</div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
