import type { SiteContent } from "@/content/types";
import { ServiceIcon } from "./service-icon";

export function ServiceGrid({ services }: { services: SiteContent["services"]["items"] }) {
  return <div className="services-grid">{services.map((service) => <article className="service-card" key={service.id}>
    <div className="service-card-top"><ServiceIcon icon={service.icon}/><span>{service.number} / 03</span></div>
    <h3>{service.title}</h3><p className="service-short">{service.short}</p><p className="service-description">{service.description}</p>
    <ul className="service-deliverables">{service.deliverables.map((deliverable) => <li key={deliverable}><span aria-hidden="true">✓</span>{deliverable}</li>)}</ul>
  </article>)}</div>;
}
