# Syrian small-business launch update — 25 October 2026

This update customizes the bilingual Meraki launch site for **small and medium-sized businesses in Syria and Arabic-speaking markets**. We kept the three service categories and five-step development methodology, but made the wording more concrete and realistic for projects deliverable by a small team (1–10 people). The site does **not** claim that Meraki currently employs 10 staff or has existing completed client projects.

## Updated public contact

- Domestic phone number supplied: **0991953560**
- International display: **+963 991 953 560**
- WhatsApp numeric path: `963991953560`
- Arabic click-to-chat: `https://wa.me/963991953560?text=...` (Arabic message is safely URL-encoded)
- English click-to-chat: same recipient, with an English prefilled message
- Only WhatsApp is promoted as a contact channel; the number appears directly below the button.
- `src/lib/whatsapp.ts` contains the supplied public business number as a fallback; `WHATSAPP_NUMBER` overrides it if necessary.

**You must still test the WhatsApp account in the app itself before launch.** International format alone doesn't establish that the number is registered on WhatsApp.

## Messaging changes

- Arabic-first for visitors with no clear browser language preference; English is still available at `/en`.
- Homepage promise immediately identifies **SMBs in Syria and the Arab region**.
- Web development now gives examples: company websites, bookings, order handling, business dashboards.
- Consulting is scoped around *initial feasibility*, budgets, risks, priorities and technology choices, not a claim of full regulated financial or legal advisory services.
- Marketing emphasizes audience, brand messaging, content, scoped digital campaigns, and measurement, without promising guaranteed sales.
- Contact invites business owners to describe the nature of their activity, the immediate challenge and their approximate budget or timeline.

## Files modified

- `src/content/ar.ts`, `src/content/en.ts` — market-specific copy and WhatsApp prefilled text
- `src/lib/whatsapp.ts` — correctly normalized and validated WhatsApp links and display number
- `src/components/ui/whatsapp-cta.tsx` — display phone beneath contact CTA
- `src/app/site.css` — light and dark background-compatible phone display
- `src/proxy.ts` — default to Arabic for unspecified or tied language preferences
- `src/lib/i18n.ts` — Arabic listed first
- `src/lib/metadata.ts` — Arabic `x-default` and Syrian OpenGraph locale
- `.env.example`, `README.md` — configuration and market documentation

## Remaining launch prerequisites

1. Confirm this is the **public company WhatsApp** number and it is registered and reachable.
2. Obtain the canonical site domain and set `NEXT_PUBLIC_SITE_URL`.
3. Validate final brand name/trademark rights and copy claims before publication.
4. Run `npm install`, `npm run lint`, `npm run typecheck`, and `npm run build` locally. The workspace was source-validated, but dependencies could not be installed here in time for a complete Next.js production build.
5. Review Arabic and English copy for accuracy about services that the current team can truly deliver.
