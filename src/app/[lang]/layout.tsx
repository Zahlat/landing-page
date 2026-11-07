import "../globals.css";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { isLocale, localeDirection, locales } from "@/lib/i18n";
import { SiteHeader } from "@/components/layout/site-header";
import { SiteFooter } from "@/components/layout/site-footer";

export const dynamicParams = false;
export function generateStaticParams() {
  return locales.map((lang) => ({ lang }));
}

export default async function LocaleLayout({ children, params }: { children: ReactNode; params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const content = getContent(lang);
  return (
    <html lang={lang} dir={localeDirection(lang)}>
      <body><a href="#main-content" className="skip-link">{lang === "ar" ? "تخطي إلى المحتوى" : "Skip to content"}</a>
        <SiteHeader locale={lang} navigation={content.navigation} descriptor={content.brand.descriptor}/>
        <main id="main-content">{children}</main>
        <SiteFooter locale={lang} content={content}/>
      </body>
    </html>
  );
}
