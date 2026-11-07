import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { SectionHeading } from "@/components/ui/section-heading";
import { ProcessSteps } from "@/components/ui/process-steps";
import { ContactPanel } from "@/components/ui/contact-panel";

type Props = { params: Promise<{ lang: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { lang } = await params; if (!isLocale(lang)) notFound(); return localizedMetadata(lang, "approach"); }
export default async function ApproachPage({ params }: Props) { const { lang } = await params; if (!isLocale(lang)) notFound(); const t = getContent(lang); return <><section className="inner-page process-section section-pad"><div className="container"><SectionHeading eyebrow={t.approach.eyebrow} title={t.approach.heading} description={t.approach.description}/><ProcessSteps steps={t.approach.steps}/><div className="pledge-card"><div><span className="pledge-mark">✦</span><h3>{t.approach.pledgeHeading}</h3><p>{t.approach.pledgeText}</p></div><ul>{t.approach.values.map(v=><li key={v}><span aria-hidden="true">✓</span>{v}</li>)}</ul></div></div></section><ContactPanel locale={lang}/></>; }
