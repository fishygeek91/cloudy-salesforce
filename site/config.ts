/**
 * Public marketing-site settings compiled into the browser bundle.
 *
 * Payment links and form endpoints are public by design. These values
 * ship to every visitor. Secrets, API keys, and private credentials
 * must never go in this file.
 */
export interface SiteConfig {
  /** Stripe Payment Link URL. Empty string means the buy path is not set. */
  readonly paymentLink: string;
  /** Formspree, Buttondown, or getform POST endpoint. Empty string means not set. */
  readonly waitlistAction: string;
  /** Setup package price in whole US dollars. */
  readonly priceUsd: number;
  /** Fallback contact used for a mailto waitlist when no form endpoint is set. */
  readonly email: string;
}

/**
 * Live site configuration shipped in the compiled public bundle.
 *
 * Payment links and form endpoints are public by design. Secrets must
 * never go in this file.
 */
export const siteConfig: SiteConfig = {
  paymentLink: "",
  waitlistAction: "https://formspree.io/f/mnpnnllo",
  priceUsd: 750,
  email: "fishygeek91@gmail.com",
};
