import type { Locale } from "./i18n";
export type Localized = Record<Locale, string>;
export type Project = {
  slug: string;
  kind: "Product" | "Demo" | "Client work";
  title: Localized;
  summary: Localized;
  challenge: Localized;
  solution: Localized;
  outcome: Localized;
  technologies: string[];
};
/** Do not add invented clients or case studies. New projects require a rebuild and redeploy. */
export const projects: Project[] = [];
export function getProject(slug: string): Project | undefined {
  return projects.find((project) => project.slug === slug);
}
