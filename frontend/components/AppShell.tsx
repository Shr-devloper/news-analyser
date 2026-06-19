"use client";

import { useRequireAuth } from "@/lib/auth";
import Nav from "./Nav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useRequireAuth();

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center text-slate-400">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
