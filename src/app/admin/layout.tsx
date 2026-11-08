import "./admin.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Meraki admin",
  robots: { index: false, follow: false },
};

// A separate root layout from app/[lang]: English, left-to-right, none of the public site chrome.
export default function AdminRootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body>{children}</body>
    </html>
  );
}
