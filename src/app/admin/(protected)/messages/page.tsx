import { FilterTabs } from "@/components/admin/filter-tabs";
import { MessageTable } from "@/components/admin/message-table";
import { isMessageStatus, isMessageType, type AdminFilters } from "@/lib/admin-types";
import { fetchMessagePage } from "@/lib/server/admin-api";

type Props = { searchParams: Promise<{ status?: string | string[]; type?: string | string[] }> };

function parseFilters(params: Awaited<Props["searchParams"]>): AdminFilters {
  // No status in the URL opens the New tab; "all" means no status filter.
  const status = params.status ?? "new";
  return {
    status: isMessageStatus(status) ? status : null,
    type: isMessageType(params.type) ? params.type : null,
  };
}

export default async function AdminMessagesPage({ searchParams }: Props) {
  const filters = parseFilters(await searchParams);
  const page = await fetchMessagePage(filters);
  return (
    <>
      <h1>Messages</h1>
      <FilterTabs filters={filters} />
      {page
        // Keyed by filter so "Load more" state resets when the filter changes.
        ? <MessageTable key={`${filters.status}:${filters.type}`} filters={filters} initialPage={page} />
        : <p className="admin-alert" role="alert">Messages are unavailable right now. Please try again shortly.</p>}
    </>
  );
}
