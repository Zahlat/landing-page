import type { ServiceIconName } from "@/content/types";

export function ServiceIcon({ icon }: { icon: ServiceIconName }) {
  return (
    <span className="service-icon" aria-hidden="true">
      {icon === "code" && <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="6" width="26" height="20" rx="4"/><path d="m12 13-4 3 4 3m8-6 4 3-4 3m-2-8-4 10M3 11h26"/></svg>}
      {icon === "compass" && <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="16" cy="16" r="12"/><path d="m20.5 11.5-3 6-6 3 3-6 6-3Z"/><path d="M16 4v3m0 18v3M4 16h3m18 0h3"/></svg>}
      {icon === "megaphone" && <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M6 14h6l13-7v18l-13-7H6a3 3 0 0 1-3-3v-2a3 3 0 0 1 3-3Z"/><path d="m10 18 3 10h5l-4-8M25 11a5 5 0 0 1 0 10"/></svg>}
    </span>
  );
}
