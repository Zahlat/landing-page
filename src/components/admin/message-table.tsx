"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { loadMoreMessages } from "@/app/admin/actions";
import { StatusBadge } from "@/components/admin/status-badge";
import { formatDate, TYPE_LABELS, type AdminFilters, type MessagePage } from "@/lib/admin-types";

type Props = { filters: AdminFilters; initialPage: MessagePage };

export function MessageTable({ filters, initialPage }: Props) {
  const [items, setItems] = useState(initialPage.items);
  const [cursor, setCursor] = useState(initialPage.next_cursor);
  const [failed, setFailed] = useState(false);
  const [pending, startTransition] = useTransition();

  const loadMore = () => {
    if (!cursor) return;
    startTransition(async () => {
      const result = await loadMoreMessages({ ...filters, cursor });
      if (!result.ok) {
        setFailed(true);
        return;
      }
      setFailed(false);
      setItems((current) => [...current, ...result.items]);
      setCursor(result.next_cursor);
    });
  };

  if (items.length === 0) return <p className="admin-empty">No messages here.</p>;

  return (
    <>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr><th>Date</th><th>Name</th><th>Email</th><th>Type</th><th>Preview</th><th>Status</th><th><span className="admin-sr-only">Open</span></th></tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td className="admin-nowrap">{formatDate(item.created_at)}</td>
                <td className="admin-cell-wrap" dir="auto">{item.name}</td>
                <td className="admin-cell-email" dir="ltr">{item.email}</td>
                <td className="admin-nowrap">{TYPE_LABELS[item.type]}</td>
                <td className="admin-preview" dir="auto">{item.preview}</td>
                <td><StatusBadge status={item.status} /></td>
                <td className="admin-nowrap"><Link href={`/admin/messages/${item.id}`}>Open</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {failed && <p className="admin-alert" role="alert">Could not load more messages. Please try again.</p>}
      {cursor && <button className="admin-button admin-load-more" type="button" onClick={loadMore} disabled={pending}>{pending ? "Loading…" : "Load more"}</button>}
    </>
  );
}
