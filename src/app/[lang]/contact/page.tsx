import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getContent } from "@/content";
import { isLocale } from "@/lib/i18n";
import { localizedMetadata } from "@/lib/metadata";
import { signFormToken } from "@/lib/server/form-token";
import { getWhatsAppHref } from "@/lib/whatsapp";
import { ContactForm } from "@/components/forms/contact-form";
import { WhatsAppCta } from "@/components/ui/whatsapp-cta";

type Props = { params: Promise<{ lang: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> { const { lang } = await params; if (!isLocale(lang)) notFound(); return localizedMetadata(lang, "contact"); }
export default async function ContactPage({ params }: Props) { const { lang } = await params; if (!isLocale(lang)) notFound(); await connection(); /* the form token must be signed per request, not at build time */ const t = getContent(lang); return <section className="inner-page section-pad"><div className="container contact-page"><div><p className="eyebrow"><span className="eyebrow-square"/>{t.contact.eyebrow}</p><h1>{t.contact.heading}</h1><p className="contact-page-lead">{t.contact.description}</p><WhatsAppCta locale={lang}/>{!getWhatsAppHref(lang) && <p className="pending-detail">{t.contact.pendingDetail}</p>}<ContactForm locale={lang} copy={t.contact.form} token={signFormToken()}/></div><aside className="contact-guide"><span className="guide-star" aria-hidden="true">✳</span><h2>{t.contact.prompt}</h2><ul>{t.contact.details.map((detail)=><li key={detail}><span aria-hidden="true">✓</span>{detail}</li>)}</ul></aside></div></section>; }
