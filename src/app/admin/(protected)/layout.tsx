import Link from "next/link";
import type { ReactNode } from "react";
import { logout } from "@/app/admin/actions";
import { fetchMessageStats } from "@/lib/server/admin-api";
import { requireAdmin } from "@/lib/server/admin-session";

// This is a convenience redirect only. Layouts don't re-run on every navigation and don't
// guard Server Actions, so each page fetch and action is authorized separately.
export default async function ProtectedLayout({ children }: { children: ReactNode }) {
  const [admin, stats] = await Promise.all([requireAdmin(), fetchMessageStats()]);
  return (
    <>
      <header className="admin-header">
        <Link className="admin-brand" href="/admin/messages">Meraki admin</Link>
        <span className="admin-new-count">{stats ? `${stats.new} new` : "New count unavailable"}</span>
        <span className="admin-user" dir="ltr">{admin.email}</span>
        <form action={logout}><button className="admin-button" type="submit">Log out</button></form>
      </header>
      <main className="admin-main">{children}</main>
    </>
  );
}
