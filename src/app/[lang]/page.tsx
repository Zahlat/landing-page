import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { hrefFor, isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { IdeaVisual } from "@/components/visuals/idea-visual";
import { SectionHeading } from "@/components/ui/section-heading";
import { ServiceGrid } from "@/components/ui/service-grid";
import { ProcessSteps } from "@/components/ui/process-steps";
import { ContactPanel } from "@/components/ui/contact-panel";

type Props = { params: Promise<{ lang: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  return localizedMetadata(lang);
}

export default async function HomePage({ params }: Props) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getContent(lang);
  return <>
    <section className="hero-section" id="home"><div className="hero-bloom" aria-hidden="true"/><div className="container hero-grid">
      <div className="hero-copy"><p className="eyebrow"><span className="eyebrow-square"/>{t.hero.eyebrow}</p>
        <h1>{t.hero.lineOne}<span>{t.hero.lineTwo}</span></h1>
        <p className="hero-description">{t.hero.description}</p>
        <div className="hero-buttons"><a className="button button-primary" href="#services">{t.hero.primary} <span aria-hidden="true">↗</span></a><a className="button button-outline" href="#process">{t.hero.secondary} <span aria-hidden="true">↓</span></a></div>
        <ul className="hero-highlights">{t.hero.highlights.map((item) => <li key={item}><span aria-hidden="true">✦</span>{item}</li>)}</ul>
      </div><IdeaVisual visual={t.visual}/>
    </div><div className="container hero-scroll"><a href="#services"><span className="scroll-mark" aria-hidden="true">↓</span>{t.labels.scroll}</a></div></section>

    <section className="services-section section-pad" id="services"><div className="container">
      <SectionHeading eyebrow={t.services.eyebrow} title={t.services.heading} description={t.services.description}/>
      <ServiceGrid services={t.services.items}/>
      <div className="section-end"><span>{t.services.footer}</span><Link href={hrefFor(lang, "/services")} className="text-link">{t.labels.learnMore}<span aria-hidden="true">↗</span></Link></div>
    </div></section>

    <section className="process-section section-pad" id="process"><div className="container">
      <div className="process-heading"><SectionHeading eyebrow={t.approach.eyebrow} title={t.approach.heading} description={t.approach.description}/><span className="process-decor" aria-hidden="true">✳</span></div>
      <ProcessSteps steps={t.approach.steps}/>
      <div className="pledge-card"><div><span className="pledge-mark">✦</span><h3>{t.approach.pledgeHeading}</h3><p>{t.approach.pledgeText}</p></div><ul>{t.approach.values.map((v) => <li key={v}><span aria-hidden="true">✓</span>{v}</li>)}</ul></div>
    </div></section>
    <ContactPanel locale={lang}/>
  </>;
}
