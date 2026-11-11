import Image from "next/image";
import type { SiteContent } from "@/content/types";
import { SectionHeading } from "./section-heading";

export function TechStack({ content }: { content: SiteContent["techStack"] }) {
  return <section className="tech-section" id="tech-stack"><div className="container">
    <SectionHeading eyebrow={content.eyebrow} title={content.heading} description={content.description}/>
    <ul className="tech-logos">{content.items.map((item) => <li key={item.name}>
      {/* Empty alt: the visible name right below already says what this is. */}
      <Image src={`/tech-logos/${item.logo}`} alt="" width={46} height={46}/>
      <span dir="ltr">{item.name}</span>
    </li>)}</ul>
  </div></section>;
}
