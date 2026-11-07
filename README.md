# Meraki — bilingual Next.js startup website

This version reworks the earlier software-only landing page into a **white-and-green bilingual startup website** primarily for Syrian and Arabic-speaking small and medium businesses, with a delivery scope appropriate to a small 1–10-person team. It describes three service groups: web application development across the full lifecycle, business and IT consulting, and marketing/advertising. The homepage leads visitors through the promise, services, five-step methodology, and WhatsApp contact.

## Quick start

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000 — the root redirects to `/en` or `/ar` based on the browser's preferred language, defaulting to `/ar` for unknown languages or ties. Both languages have explicit routes:

- `/en`, `/ar` — full-scrolling homepage
- `/en/services`, `/ar/services` — services
- `/en/approach`, `/ar/approach` — delivery process
- `/en/work`, `/ar/work` — honest portfolio (currently empty)
- `/en/about`, `/ar/about` — company description
- `/en/contact`, `/ar/contact` — WhatsApp-only contact
- `/en/work/[slug]`, `/ar/work/[slug]` — future portfolio details

## Company WhatsApp and publication configuration

The business WhatsApp number is already configured as a public fallback, so the WhatsApp CTA works in development without adding an environment variable. You can override it in `.env.local` or deployment environment variables:

```bash
WHATSAPP_NUMBER=963991953560
NEXT_PUBLIC_SITE_URL=https://your-real-domain.example
```

For WhatsApp, use **8–15 digits including the country code**, without +, spaces, parentheses or dashes. The initial fallback number is **0991953560** domestically, or **+963 991 953 560** internationally. The WhatsApp link uses `https://wa.me/963991953560` with a pre-filled message in the chosen language. An invalid environment override disables the link rather than creating a broken contact target. **Important:** the number format has been checked against the Syrian numbering plan, but only you can confirm that the number is registered and reachable on WhatsApp before publication.

`NEXT_PUBLIC_SITE_URL` should be the public canonical HTTPS origin. Arabic is the primary locale; the `x-default` alternate targets `/ar`. Localized canonical and hreflang metadata are generated **only when configured** to avoid publishing fake localhost URLs. To apply edits to the env file, restart the dev server; deployment environment variable changes require a rebuild if statically prerendered.

## Market positioning and realistic scope

- **Primary audience:** Syrian and Arabic-speaking small and medium-sized businesses, including local shops, service offices, and growing companies.
- **Capacity:** Start with projects a small 1–10-person delivery team can reasonably complete; avoid implying enterprise-scale implementation, guaranteed results, or an existing large expert team.
- **Services:** Practical websites/web apps and automation, initial business/technical feasibility and risk guidance, focused brand and digital marketing work.
- **Voice:** Professional, plain-language Modern Standard Arabic that is accessible to local business owners; English remains fully translated.
- **Contact:** WhatsApp only, with localized pre-filled intro messages.

## Where to customize

| File | What to edit |
|---|---|
| `src/content/ar.ts` | All Arabic copy |
| `src/content/en.ts` | All English copy |
| `src/content/types.ts` | Data contracts and types |
| `src/app/site.css` | Visual design, tokens, responsiveness, animations |
| `src/components/visuals/idea-visual.tsx` | Interactive hero diagram |
| `src/components/layout/site-header.tsx` | Route-aware navigation and language switch |
| `src/lib/whatsapp.ts` | Validated WhatsApp URL construction |
| `src/lib/projects.ts` | Future portfolio records (both languages required) |
| `src/lib/metadata.ts` | SEO titles, canonical and hreflang URLs |
| `src/proxy.ts` | Locale detection for `/` only, using Accept-Language |

This project uses Next.js 16.4.3+ App Router. Content pages and data stay server-side by default. The **header** and **idea diagram** are client components because they use browser state and navigation.

## How to add a genuine project

Add an object to `projects` in `src/lib/projects.ts`, with `slug`, `kind`, bilingual `title`, `summary`, `challenge`, `solution`, `outcome`, and `technologies`. `/en/work/<slug>` and `/ar/work/<slug>` will render it after a rebuild. Do not fabricate client projects or outcomes.

## Checks

```bash
npm run lint
npm run typecheck
npm run build
```

## Security and accessibility notes

- No contact form, user-supplied HTML, auth, DB, or HTTP API is included, which reduces the initial attack surface.
- The supplied public WhatsApp number is configured as a server-side fallback; a deployment variable can override it. Both paths are validated before creating the outgoing URL. This public company number is not a secret.
- The earlier baseline response headers remain in `next.config.ts`; configure a CSP specifically for your deployed assets and test it before enabling enforcement.
- Navigation uses semantic anchors; language routes set HTML `lang` and `dir` (RTL for Arabic), including localized alternate URLs when domain is configured.
- Interactive visual controls are buttons with `aria-pressed`, and all transitions respect reduced-motion preferences.
- Proxy requires a supported Next.js server deployment; pure `output: "export"` is not compatible with the current language-detection redirect.
- Before launch: confirm claims describing your real capabilities, the company name/trademark, copyright and privacy policy if analytics or tracking are added, and test on mobile devices.

No external images, icon packages, fonts or animation libraries are required. Add a real logo, brand assets and verified contact details when available.
