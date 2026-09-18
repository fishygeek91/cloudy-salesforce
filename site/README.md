# Schema Sentinel till

Static marketing page for Schema Sentinel: free CLI pitch, $750 setup package buy button, and a hosted waitlist. One page, no backend.

## Configuration

Both URLs live in `site/config.ts` (`siteConfig`).

- `paymentLink`: paste a Stripe Payment Link URL (`https://buy.stripe.com/...`). While it is `""`, the Buy button stays disabled with "Payment link not set — use the waitlist".
- `waitlistAction`: paste a Formspree / Buttondown / getform POST endpoint. While it is `""`, the form falls back to a `mailto:` draft to the configured email with subject "Sentinel waitlist".

Everything in `config.ts` ships publicly in the bundle. Never put secrets there.

`priceUsd` must stay an integer between 500 and 2000 (unit-tested).

## Local development

```bash
npm install
npm test
npm run build
```

Then open `site/index.html` directly in a browser. The bundle is a plain IIFE, so `file://` works.

## Publishing

Push to `main`. `.github/workflows/pages.yml` builds and deploys `site/` via GitHub Pages.

One-time setup: repo Settings → Pages → Source = "GitHub Actions".

Resulting URL: https://fishygeek91.github.io/cloudy-salesforce/

## Scope

This page sells CLI setup work. It is not the hosted product. The Python package is unaffected (`site/` is excluded from the wheel).
