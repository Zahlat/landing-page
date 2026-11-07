import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { ContactPanel } from "@/components/ui/contact-panel";

type Props = { params: Promise<{ lang: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { lang } = await params; if (!isLocale(lang)) notFound(); return localizedMetadata(lang, "about"); }
export default async function AboutPage({ params }: Props) { const { lang } = await params; if (!isLocale(lang)) notFound(); const t = getContent(lang); return <><section className="inner-page section-pad"><div className="container"><div className="about-lead"><p className="eyebrow"><span className="eyebrow-square"/>{t.about.eyebrow}</p><h1>{t.about.title}</h1><p>{t.about.lead}</p></div><div className="about-values">{t.about.sections.map((item,i)=><article key={item.title}><span>0{i+1}</span><h2>{item.title}</h2><p>{item.description}</p></article>)}</div></div></section><ContactPanel locale={lang}/></>; }
