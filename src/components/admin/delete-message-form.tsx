"use client";

import type { FormEvent } from "react";
import { deleteMessage } from "@/app/admin/actions";

export function DeleteMessageForm({ id }: { id: number }) {
  const confirmDelete = (event: FormEvent<HTMLFormElement>) => {
    if (!window.confirm("Delete this message permanently? This can't be undone.")) event.preventDefault();
  };
  return (
    <form action={deleteMessage} onSubmit={confirmDelete}>
      <input type="hidden" name="id" value={id} />
      <button className="admin-button admin-button-danger" type="submit">Delete</button>
    </form>
  );
}
