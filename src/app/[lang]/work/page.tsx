import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { hrefFor, isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { projects } from "@/lib/projects";
import { ContactPanel } from "@/components/ui/contact-panel";

type Props = { params: Promise<{ lang: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { lang } = await params; if (!isLocale(lang)) notFound(); return localizedMetadata(lang, "work"); }
export default async function WorkPage({ params }: Props) { const { lang } = await params; if (!isLocale(lang)) notFound(); const t = getContent(lang); return <><section className="inner-page section-pad"><div className="container"><div className="about-lead"><p className="eyebrow"><span className="eyebrow-square"/>{t.work.eyebrow}</p><h1>{t.work.heading}</h1><p>{t.work.intro}</p></div>{projects.length===0?<div className="empty-projects"><span className="empty-art" aria-hidden="true">✳</span><h2>{t.work.emptyTitle}</h2><p>{t.work.emptyText}</p></div>:<div className="projects-grid">{projects.map((project)=><Link key={project.slug} href={hrefFor(lang,`/work/${project.slug}`)} className="project-card"><span>{t.work.kind[project.kind]}</span><h2>{project.title[lang]}</h2><p>{project.summary[lang]}</p><span className="text-link">{t.labels.learnMore} ↗</span></Link>)}</div>}</div></section><ContactPanel locale={lang}/></>; }
