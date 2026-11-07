"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { Locale } from "@/lib/i18n";
import { hrefFor } from "@/lib/i18n";
import type { SiteContent } from "@/content/types";

export function SiteHeader({ locale, navigation, descriptor }: { locale: Locale; navigation: SiteContent["navigation"]; descriptor: string }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const paths = [
    { path: "", label: navigation.home },
    { path: "/services", label: navigation.services },
    { path: "/approach", label: navigation.approach },
    { path: "/work", label: navigation.work },
    { path: "/about", label: navigation.about },
  ];
  const otherLocale: Locale = locale === "ar" ? "en" : "ar";
  const switchPath = pathname.replace(/^\/(en|ar)(?=\/|$)/, `/${otherLocale}`);
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link href={hrefFor(locale)} className="brand" aria-label={`Meraki — ${navigation.home}`} onClick={() => setMenuOpen(false)}>
          <span className="brand-symbol" aria-hidden="true"><i/><i/><i/></span>
          <span className="brand-text"><strong>meraki<span>.</span></strong><small>{descriptor}</small></span>
        </Link>
        <div className="header-controls">
          <Link className="language-control" href={switchPath || hrefFor(otherLocale)} hrefLang={otherLocale} lang={otherLocale} dir={otherLocale === "ar" ? "rtl" : "ltr"} aria-label={navigation.switchLang} onClick={() => setMenuOpen(false)}>{otherLocale === "ar" ? "العربية" : "English"}<span aria-hidden="true">◎</span></Link>
          <button type="button" className="mobile-toggle" aria-expanded={menuOpen} aria-controls="primary-navigation" aria-label={menuOpen ? navigation.close : navigation.menu} onClick={() => setMenuOpen((old) => !old)}><span/><span/><span/></button>
        </div>
        <nav id="primary-navigation" className={`site-nav ${menuOpen ? "nav-open" : ""}`} aria-label={navigation.menu}>
          {paths.map(({ path, label }) => {
            const href = hrefFor(locale, path);
            const isActive = path === "" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
            return <Link key={path} href={href} aria-current={isActive ? "page" : undefined} onClick={() => setMenuOpen(false)} className={`nav-item ${isActive ? "nav-active" : ""}`}>{label}</Link>;
          })}
          <Link href={hrefFor(locale, "/contact")} className="nav-contact" onClick={() => setMenuOpen(false)}>{navigation.contact} <span aria-hidden="true">↗</span></Link>
        </nav>
      </div>
    </header>
  );
}
