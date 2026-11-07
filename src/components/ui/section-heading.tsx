export function SectionHeading({ eyebrow, title, description, centered = false }: { eyebrow: string; title: string; description: string; centered?: boolean }) {
  return <div className={`section-heading ${centered ? "section-centered" : ""}`}><p className="eyebrow"><span className="eyebrow-square"/>{eyebrow}</p><h2>{title}</h2><p className="section-description">{description}</p></div>;
}
