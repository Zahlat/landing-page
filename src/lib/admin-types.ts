// Shared by server and client admin code, so this file must stay free of server imports.
import { MESSAGE_TYPES } from "@/lib/validation/contact-shared";

export { MESSAGE_TYPES };
export type MessageType = (typeof MESSAGE_TYPES)[number];

export const MESSAGE_STATUSES = ["new", "read", "archived"] as const;
export type MessageStatus = (typeof MESSAGE_STATUSES)[number];

export const TYPE_LABELS: Record<MessageType, string> = {
  suggestion: "Suggestion",
  request: "Request",
  question: "Question",
  other: "Other",
};

export const STATUS_LABELS: Record<MessageStatus, string> = { new: "New", read: "Read", archived: "Archived" };

export type AdminFilters = { status: MessageStatus | null; type: MessageType | null };

export type MessageListItem = {
  id: number;
  created_at: string;
  name: string;
  email: string;
  type: MessageType;
  status: MessageStatus;
  preview: string;
};

export type MessagePage = { items: MessageListItem[]; next_cursor: string | null };

export type MessageDetail = {
  id: number;
  name: string;
  email: string;
  type: MessageType;
  content: string;
  locale: "ar" | "en";
  status: MessageStatus;
  user_agent: string | null;
  created_at: string;
  read_at: string | null;
};

export type MessageStats = Record<MessageStatus, number>;

export type LoadMoreResult = ({ ok: true } & MessagePage) | { ok: false };

export function isMessageStatus(value: unknown): value is MessageStatus {
  return MESSAGE_STATUSES.some((status) => status === value);
}

export function isMessageType(value: unknown): value is MessageType {
  return MESSAGE_TYPES.some((type) => type === value);
}

const DATE_PARTS = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Damascus",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** Built from parts so server and browser output match exactly during hydration. */
export function formatDate(iso: string): string {
  const parts = Object.fromEntries(DATE_PARTS.formatToParts(new Date(iso)).map((part) => [part.type, part.value]));
  return `${parts.day} ${parts.month} ${parts.year}, ${parts.hour}:${parts.minute}`;
}
