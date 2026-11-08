import Link from "next/link";
import { notFound } from "next/navigation";
import { updateStatus } from "@/app/admin/actions";
import { DeleteMessageForm } from "@/components/admin/delete-message-form";
import { StatusBadge } from "@/components/admin/status-badge";
import { formatDate, TYPE_LABELS, type MessageStatus } from "@/lib/admin-types";
import { fetchMessage, isMessageId } from "@/lib/server/admin-api";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string | string[] }>;
};

const STATUS_ACTIONS: { status: MessageStatus; label: string }[] = [
  { status: "read", label: "Mark read" },
  { status: "new", label: "Mark unread" },
  { status: "archived", label: "Archive" },
];

export default async function AdminMessagePage({ params, searchParams }: Props) {
  const [{ id }, { error }] = await Promise.all([params, searchParams]);
  if (!isMessageId(id)) notFound();
  const result = await fetchMessage(id);
  if (result.kind === "missing") notFound();
  if (result.kind === "unavailable") return <p className="admin-alert" role="alert">This message is unavailable right now. Please try again shortly.</p>;
  const { message } = result;

  return (
    <>
      <Link className="admin-back" href="/admin/messages?status=all">← All messages</Link>
      <div className="admin-detail-heading">
        <h1 dir="auto">{message.name}</h1>
        <StatusBadge status={message.status} />
      </div>
      {error && <p className="admin-alert" role="alert">That change couldn&apos;t be saved. Please try again.</p>}

      {/* Attacker-controlled text: rendered only as an escaped React text node, never as HTML. */}
      <p className="admin-content" dir="auto">{message.content}</p>

      <dl className="admin-meta">
        <dt>Email</dt><dd dir="ltr">{message.email}</dd>
        <dt>Type</dt><dd>{TYPE_LABELS[message.type]}</dd>
        <dt>Language</dt><dd>{message.locale === "ar" ? "Arabic" : "English"}</dd>
        <dt>Received</dt><dd>{formatDate(message.created_at)}</dd>
        <dt>First read</dt><dd>{message.read_at ? formatDate(message.read_at) : "Not yet"}</dd>
        <dt>User agent</dt><dd dir="ltr">{message.user_agent ?? "Unknown"}</dd>
      </dl>

      <div className="admin-actions">
        {STATUS_ACTIONS.filter((action) => action.status !== message.status).map((action) => (
          <form key={action.status} action={updateStatus}>
            <input type="hidden" name="id" value={message.id} />
            <input type="hidden" name="status" value={action.status} />
            <button className="admin-button" type="submit">{action.label}</button>
          </form>
        ))}
        <DeleteMessageForm id={message.id} />
      </div>
    </>
  );
}
