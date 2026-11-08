import { STATUS_LABELS, type MessageStatus } from "@/lib/admin-types";

export function StatusBadge({ status }: { status: MessageStatus }) {
  return <span className={`admin-badge admin-badge-${status}`}>{STATUS_LABELS[status]}</span>;
}
