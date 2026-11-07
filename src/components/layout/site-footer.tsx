import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { hrefFor } from "@/lib/i18n";
import type { SiteContent } from "@/content/types";

export function SiteFooter({ locale, content }: { locale: Locale; content: SiteContent }) {
  const nav = content.navigation;
  return (
    <footer className="site-footer"><div className="container footer-grid">
      <div className="footer-main"><Link className="footer-brand" href={hrefFor(locale)}>meraki<span>.</span></Link><p>{content.footer.tagline}</p><span className="footer-note">{content.footer.note}</span></div>
      <nav className="footer-links" aria-label={nav.menu}><Link href={hrefFor(locale)}>{nav.home}</Link><Link href={hrefFor(locale,"/services")}>{nav.services}</Link><Link href={hrefFor(locale,"/approach")}>{nav.approach}</Link><Link href={hrefFor(locale,"/work")}>{nav.work}</Link><Link href={hrefFor(locale,"/contact")}>{nav.contact}</Link></nav>
      <div className="footer-languages"><Link href={hrefFor("en")} hrefLang="en" lang="en">English</Link><span aria-hidden="true">·</span><Link href={hrefFor("ar")} hrefLang="ar" lang="ar">العربية</Link></div>
    </div><div className="container footer-bottom">© {new Date().getFullYear()} Meraki. {content.footer.copyright}</div></footer>
  );
}
