import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { SectionHeading } from "@/components/ui/section-heading";
import { ServiceGrid } from "@/components/ui/service-grid";
import { ContactPanel } from "@/components/ui/contact-panel";

type Props = { params: Promise<{ lang: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { lang } = await params; if (!isLocale(lang)) notFound(); return localizedMetadata(lang, "services"); }
export default async function ServicesPage({ params }: Props) {
  const { lang } = await params; if (!isLocale(lang)) notFound(); const t = getContent(lang);
  return <><section className="inner-page section-pad"><div className="container"><SectionHeading eyebrow={t.services.eyebrow} title={t.services.heading} description={t.services.description}/><ServiceGrid services={t.services.items}/><p className="services-footnote">{t.services.footer}</p></div></section><ContactPanel locale={lang}/></>;
}
