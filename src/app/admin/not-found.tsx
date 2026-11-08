import Link from "next/link";

export default function AdminNotFound() {
  return (
    <main className="admin-center">
      <h1>Not found</h1>
      <p>That page or message doesn&apos;t exist.</p>
      <Link href="/admin/messages">Back to messages</Link>
    </main>
  );
}
