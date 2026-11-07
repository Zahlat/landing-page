export type ServiceIconName = "code" | "compass" | "megaphone";
export type Service = {
  id: string;
  number: string;
  icon: ServiceIconName;
  title: string;
  short: string;
  description: string;
  deliverables: string[];
};
export type MethodStep = {
  number: string;
  title: string;
  short: string;
  outcome: string;
};
export type SiteContent = {
  seo: { title: string; description: string };
  brand: { descriptor: string };
  navigation: { home: string; services: string; approach: string; work: string; about: string; contact: string; menu: string; close: string; switchLang: string };
  labels: { discover: string; build: string; grow: string; scroll: string; learnMore: string; comingSoon: string; home: string; principles: string };
  hero: { eyebrow: string; lineOne: string; lineTwo: string; description: string; primary: string; secondary: string; highlights: string[] };
  visual: { eyebrow: string; title: string; coreLabel: string; descriptions: string[]; phases: string[]; note: string };
  services: { eyebrow: string; heading: string; description: string; items: Service[]; footer: string };
  approach: { eyebrow: string; heading: string; description: string; steps: MethodStep[]; pledgeHeading: string; pledgeText: string; values: string[] };
  about: { eyebrow: string; title: string; lead: string; sections: { title: string; description: string }[] };
  work: { eyebrow: string; heading: string; intro: string; emptyTitle: string; emptyText: string; kind: Record<"Product" | "Demo" | "Client work", string>; challenge: string; solution: string; outcome: string; technologies: string };
  contact: { eyebrow: string; heading: string; description: string; whatsapp: string; pending: string; pendingDetail: string; prompt: string; message: string; details: string[] };
  footer: { tagline: string; copyright: string; note: string };
  notFound: { title: string; description: string; action: string };
};
