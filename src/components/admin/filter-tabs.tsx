import Form from "next/form";
import Link from "next/link";
import { MESSAGE_TYPES, TYPE_LABELS, type AdminFilters } from "@/lib/admin-types";

const TABS = [
  { label: "New", value: "new" },
  { label: "Read", value: "read" },
  { label: "Archived", value: "archived" },
  { label: "All", value: "all" },
] as const;

export function FilterTabs({ filters }: { filters: AdminFilters }) {
  const active = filters.status ?? "all";
  const hrefFor = (status: string) => {
    const query = new URLSearchParams({ status });
    if (filters.type) query.set("type", filters.type);
    return `/admin/messages?${query}`;
  };
  return (
    <div className="admin-filters">
      <nav className="admin-tabs" aria-label="Filter by status">
        {TABS.map((tab) => (
          <Link key={tab.value} href={hrefFor(tab.value)} className={tab.value === active ? "admin-tab admin-tab-active" : "admin-tab"} aria-current={tab.value === active ? "page" : undefined}>
            {tab.label}
          </Link>
        ))}
      </nav>
      <Form action="/admin/messages" className="admin-type-filter">
        <input type="hidden" name="status" value={active} />
        <label htmlFor="admin-type">Type</label>
        {/* Keyed so the dropdown follows the URL after a client-side navigation. */}
        <select key={filters.type ?? "any"} id="admin-type" name="type" defaultValue={filters.type ?? ""}>
          <option value="">All types</option>
          {MESSAGE_TYPES.map((type) => <option key={type} value={type}>{TYPE_LABELS[type]}</option>)}
        </select>
        <button className="admin-button" type="submit">Apply</button>
      </Form>
    </div>
  );
}
