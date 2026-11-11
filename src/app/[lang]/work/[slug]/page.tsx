import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getContent } from "@/content";
import { isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { getProject, projects } from "@/lib/projects";
import { ContactPanel } from "@/components/ui/contact-panel";

type Props = { params: Promise<{ lang: string; slug: string }> };
export const dynamicParams = false;
export function generateStaticParams() { return projects.map(({ slug }) => ({ slug })); }
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { lang, slug } = await params; if (!isLocale(lang)) notFound(); const project=getProject(slug); if (!project) notFound(); return localizedMetadata(lang, "work", { path: `/work/${project.slug}`, title: `${project.title[lang]} | Meraki`, description: project.summary[lang], index: true }); }
export default async function ProjectPage({ params }: Props) { const { lang, slug } = await params; if (!isLocale(lang)) notFound(); const p = getProject(slug); if (!p) notFound(); const t=getContent(lang); return <><article className="inner-page section-pad"><div className="container project-detail"><p className="eyebrow"><span className="eyebrow-square"/>{t.work.kind[p.kind]}</p><h1>{p.title[lang]}</h1><p className="project-summary">{p.summary[lang]}</p><div className="project-sections"><section><h2>{t.work.challenge}</h2><p>{p.challenge[lang]}</p></section><section><h2>{t.work.solution}</h2><p>{p.solution[lang]}</p></section><section><h2>{t.work.outcome}</h2><p>{p.outcome[lang]}</p></section><section><h2>{t.work.technologies}</h2><ul className="tech-list">{p.technologies.map(v=><li key={v}>{v}</li>)}</ul></section></div></div></article><ContactPanel locale={lang}/></>; }
