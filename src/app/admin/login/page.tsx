import { redirect } from "next/navigation";
import { LoginForm } from "@/components/admin/login-form";
import { getAdmin } from "@/lib/server/admin-session";

export default async function AdminLoginPage() {
  if (await getAdmin()) redirect("/admin/messages");
  return (
    <main className="admin-center">
      <h1>Meraki admin</h1>
      <LoginForm />
    </main>
  );
}
