"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

const INTERESTS = [
  "AI", "Software Engineering", "DSA", "Programming",
  "Startups", "Finance", "Productivity", "Career Growth",
];
const CATEGORIES = [
  "World", "India", "Business", "Finance", "Markets", "Technology",
  "AI", "Cybersecurity", "Startups", "Science", "Health", "Sports",
];

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<any>(null);
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api.getPreferences().then(setPrefs).catch(() => setPrefs({ interests: [], categories: [], email_enabled: true, send_hour: 7, timezone: "Asia/Kolkata" }));
  }, []);

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
  }

  async function save() {
    setSaved("");
    await api.updatePreferences({
      interests: prefs.interests,
      categories: prefs.categories,
      email_enabled: prefs.email_enabled,
      send_hour: prefs.send_hour,
      timezone: prefs.timezone,
    });
    setSaved("Preferences saved ✓");
  }

  if (!prefs) return <AppShell><div className="text-slate-400">Loading…</div></AppShell>;

  return (
    <AppShell>
      <h1 className="text-2xl font-bold">Settings</h1>
      <p className="text-slate-500">Personalize your briefing and delivery.</p>

      <div className="mt-6 card p-6">
        <h2 className="font-bold">Your interests</h2>
        <p className="text-sm text-slate-500">Used to build your personalized section.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {INTERESTS.map((i) => (
            <button
              key={i}
              onClick={() => setPrefs({ ...prefs, interests: toggle(prefs.interests, i) })}
              className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                prefs.interests.includes(i)
                  ? "bg-brand-600 text-white"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {i}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 card p-6">
        <h2 className="font-bold">Preferred categories</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setPrefs({ ...prefs, categories: toggle(prefs.categories, c) })}
              className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                prefs.categories.includes(c)
                  ? "bg-brand-600 text-white"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 card p-6">
        <h2 className="font-bold">Email delivery</h2>
        <label className="mt-3 flex items-center gap-3">
          <input
            type="checkbox"
            checked={prefs.email_enabled}
            onChange={(e) => setPrefs({ ...prefs, email_enabled: e.target.checked })}
          />
          <span className="text-sm">Email me the daily briefing</span>
        </label>
        <div className="mt-4 flex gap-4">
          <div>
            <label className="text-xs font-medium text-slate-500">Send hour (local)</label>
            <input
              type="number"
              min={0}
              max={23}
              className="input mt-1 w-28"
              value={prefs.send_hour}
              onChange={(e) => setPrefs({ ...prefs, send_hour: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Timezone</label>
            <input
              className="input mt-1 w-56"
              value={prefs.timezone}
              onChange={(e) => setPrefs({ ...prefs, timezone: e.target.value })}
            />
          </div>
        </div>
      </div>

      <div className="mt-6 flex items-center gap-3">
        <button className="btn-primary" onClick={save}>Save preferences</button>
        {saved && <span className="text-sm text-green-600">{saved}</span>}
      </div>
    </AppShell>
  );
}
