"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LandingPage() {
  const router = useRouter();
  const { user, loading, refresh } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("admin@news.ai");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "register") {
        await api.register(email, password, name);
      }
      await api.login(email, password);
      await refresh();
      router.replace("/dashboard");
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen md:grid-cols-2">
      <section className="hidden flex-col justify-between bg-brand-600 p-12 text-white md:flex">
        <div className="text-2xl font-bold">◆ News Intelligence</div>
        <div>
          <h1 className="text-4xl font-bold leading-tight">
            Your autonomous morning news brief.
          </h1>
          <p className="mt-4 max-w-md text-brand-100">
            12+ trusted sources collected, de-duplicated, ranked and summarized
            by AI agents — delivered to your inbox at 7 AM, every day.
          </p>
          <ul className="mt-8 space-y-2 text-brand-100">
            <li>• Executive summaries powered by GroqCloud</li>
            <li>• Importance scoring & trend detection</li>
            <li>• Personalized briefings for your interests</li>
            <li>• PDF / HTML / Markdown reports</li>
          </ul>
        </div>
        <div className="text-sm text-brand-200">
          Powered by FastAPI · LangGraph · APScheduler · Next.js
        </div>
      </section>

      <section className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="card w-full max-w-md p-8">
          <h2 className="text-2xl font-bold">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {mode === "login"
              ? "Sign in to view your intelligence dashboard."
              : "Start receiving daily AI news briefings."}
          </p>

          {error && (
            <div className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {mode === "register" && (
            <div className="mt-4">
              <label className="text-sm font-medium">Full name</label>
              <input
                className="input mt-1"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
              />
            </div>
          )}

          <div className="mt-4">
            <label className="text-sm font-medium">Email</label>
            <input
              className="input mt-1"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="mt-4">
            <label className="text-sm font-medium">Password</label>
            <input
              className="input mt-1"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button className="btn-primary mt-6 w-full" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>

          <p className="mt-4 text-center text-sm text-slate-500">
            {mode === "login" ? "No account?" : "Already have an account?"}{" "}
            <button
              type="button"
              className="font-semibold text-brand-600"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Register" : "Sign in"}
            </button>
          </p>
        </form>
      </section>
    </main>
  );
}
