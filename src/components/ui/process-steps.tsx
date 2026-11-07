import type { SiteContent } from "@/content/types";
export function ProcessSteps({ steps }: { steps: SiteContent["approach"]["steps"] }) {
  return <ol className="process-list">{steps.map((step) => <li className="process-item" key={step.number}><span className="process-index">{step.number}</span><div className="process-content"><h3>{step.title}</h3><p>{step.short}</p></div><span className="process-outcome">{step.outcome}</span></li>)}</ol>;
}
