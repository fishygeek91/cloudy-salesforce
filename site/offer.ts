/**
 * Inclusive lower bound of the advertised setup-package price band, in USD.
 */
export const PRICE_BAND_MIN_USD = 500;

/**
 * Inclusive upper bound of the advertised setup-package price band, in USD.
 */
export const PRICE_BAND_MAX_USD = 2000;

/**
 * Marketing copy for the Schema Sentinel landing page.
 */
export interface OfferCopy {
  /** Primary page headline. */
  headline: string;
  /** Supporting line under the headline. */
  subhead: string;
  /** Who this offer is for, and who it is not for. */
  audience: string;
  /** Heading for the free CLI section. */
  cliTitle: string;
  /** Explanation of the free CLI install and commands. */
  cliBody: string;
  /** Exact pip install command shown to visitors. */
  cliInstallCommand: string;
  /** Offline fixture demo command shown to visitors. */
  cliDemoCommand: string;
  /** Heading for the paid setup package. */
  setupTitle: string;
  /** Short sell of the fixed-scope setup engagement. */
  setupBody: string;
  /** In-scope deliverables for the setup package. */
  setupIncludes: readonly string[];
  /** Explicitly out-of-scope items for the setup package. */
  setupExcludes: readonly string[];
  /** Heading for the hosted-product waitlist. */
  waitlistTitle: string;
  /** Short explanation of why the waitlist exists. */
  waitlistBody: string;
  /** Footer disclaimer and positioning. */
  footerLegal: string;
}

/**
 * Canonical landing-page copy for the CLI, setup package, and waitlist.
 */
export const offerCopy: OfferCopy = {
  headline: "Your Salesforce admin just broke your integration.",
  subhead: "Schema Sentinel diffs the schema. This page sells the setup, not the host.",
  audience:
    "This is for the Python integration engineer whose job broke at 2 a.m., not the release manager, and not a deploy tool.",
  cliTitle: "Free CLI",
  cliBody:
    "pip install cloudy-salesforce gives snapshot and diff commands that capture an org's schema as stable JSON and diff two snapshots offline. The CLI exits with code 1 on drift so CI can fail the pipeline.",
  cliInstallCommand: "pip install cloudy-salesforce",
  cliDemoCommand:
    "cloudy-salesforce diff examples/snapshots/base.json examples/snapshots/drifted.json",
  setupTitle: "Setup package",
  setupBody:
    "A fixed-scope engagement that stands up Schema Sentinel in your integration stack: we generate the typed client, wire the first snapshot into CI, and walk you through your first change set. One package, one price, then you run it.",
  setupIncludes: [
    "A typed cloudy-salesforce client generated for your sObjects",
    "Your first schema snapshot wired into CI so the pipeline fails on drift",
    "One human walkthrough of your first change set",
  ],
  setupExcludes: [
    "Hosted hourly snapshots",
    "Slack OAuth or alerting integrations",
    "An ongoing retainer",
  ],
  waitlistTitle: "Hosted Sentinel waitlist",
  waitlistBody:
    "Hosted scheduled snapshots may come later; join the waitlist to hear about it.",
  footerLegal:
    "This is not Gearset, not Copado, and not a deployment tool. It is a schema-drift detector and typed Python client for integration engineers. Not affiliated with Salesforce, Inc.",
};

/**
 * Lowercase phrases that must never appear in landing-page copy.
 */
export const FORBIDDEN_PHRASES: readonly string[] = ["nobody detects", "pr bot"];

/**
 * Flatten every string field on the given copy, including array entries.
 *
 * @param copy - Copy to flatten. Defaults to {@link offerCopy}.
 * @returns All string values in stable field order.
 */
export function allCopyStrings(copy?: OfferCopy): readonly string[] {
  const source = copy ?? offerCopy;
  return [
    source.headline,
    source.subhead,
    source.audience,
    source.cliTitle,
    source.cliBody,
    source.cliInstallCommand,
    source.cliDemoCommand,
    source.setupTitle,
    source.setupBody,
    ...source.setupIncludes,
    ...source.setupExcludes,
    source.waitlistTitle,
    source.waitlistBody,
    source.footerLegal,
  ];
}

/**
 * Find forbidden marketing phrases inside a single text blob.
 *
 * Matching is case-insensitive. Returned values are the canonical
 * entries from {@link FORBIDDEN_PHRASES}.
 *
 * @param text - Raw text to scan.
 * @returns Each forbidden phrase that appears in `text`.
 */
export function findForbiddenPhrases(text: string): readonly string[] {
  const lowered = text.toLowerCase();
  return FORBIDDEN_PHRASES.filter((phrase) => lowered.includes(phrase.toLowerCase()));
}

/**
 * Report whether the given copy is free of forbidden phrases.
 *
 * @param copy - Copy to check. Defaults to {@link offerCopy}.
 * @returns `true` when no flattened string contains a forbidden phrase.
 */
export function copyIsCompliant(copy?: OfferCopy): boolean {
  return allCopyStrings(copy).every((text) => findForbiddenPhrases(text).length === 0);
}

/**
 * Check whether a setup price sits inside the advertised USD band.
 *
 * @param price - Candidate price in US dollars.
 * @returns `true` when `price` is an integer in the inclusive band.
 */
export function isValidPriceUsd(price: number): boolean {
  return (
    Number.isInteger(price) &&
    price >= PRICE_BAND_MIN_USD &&
    price <= PRICE_BAND_MAX_USD
  );
}

/**
 * Format a valid setup price as a US-dollar string.
 *
 * @param price - Integer USD amount inside the advertised band.
 * @returns Locale-formatted price such as "$750" or "$2,000".
 * @throws {RangeError} When {@link isValidPriceUsd} is false.
 */
export function formatPriceUsd(price: number): string {
  if (!isValidPriceUsd(price)) {
    throw new RangeError(
      `Price must be an integer between ${PRICE_BAND_MIN_USD} and ${PRICE_BAND_MAX_USD} inclusive. Received: ${String(price)}`
    );
  }
  return `$${price.toLocaleString("en-US")}`;
}

/**
 * Org classifications accepted on the waitlist form.
 */
export const ORG_TYPES = ["indie", "si", "isv", "in-house"] as const;

/**
 * One of the accepted waitlist org classifications.
 */
export type OrgType = (typeof ORG_TYPES)[number];

/**
 * Answers for whether a silent schema change has burned the visitor.
 */
export const BURNED_ANSWERS = ["yes", "no", "story"] as const;

/**
 * One of the accepted burned-by-schema-change answers.
 */
export type BurnedAnswer = (typeof BURNED_ANSWERS)[number];

/**
 * Fields collected from a waitlist form submission.
 */
export interface WaitlistSubmission {
  /** Visitor email address. */
  email: string;
  /** Claimed org classification; must be an {@link OrgType}. */
  orgType: string;
  /** Whether a silent schema change has burned them; must be a {@link BurnedAnswer}. */
  burned: string;
  /** Optional story; required when `burned` is "story". */
  story: string;
}

/**
 * Validate a waitlist payload after trimming every field.
 *
 * @param submission - Raw form values.
 * @returns Human-readable errors. An empty array means the payload is valid.
 */
export function validateWaitlist(submission: WaitlistSubmission): readonly string[] {
  const email = submission.email.trim();
  const orgType = submission.orgType.trim();
  const burned = submission.burned.trim();
  const story = submission.story.trim();
  const errors: string[] = [];
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (email === "" || !emailPattern.test(email)) {
    errors.push("A valid email address is required.");
  }

  if (!ORG_TYPES.some((allowed) => allowed === orgType)) {
    errors.push("Select an org type: indie, si, isv, or in-house.");
  }

  if (burned === "") {
    errors.push("Tell us whether you have been burned by a silent schema change.");
  } else if (!BURNED_ANSWERS.some((allowed) => allowed === burned)) {
    errors.push("Choose yes, no, or story for the burned-by-schema-change question.");
  }

  if (burned === "story" && story === "") {
    errors.push("Share a short story when you choose the story option.");
  }

  return errors;
}

/**
 * Decide whether the buy button can use a Stripe Payment Link.
 *
 * @param paymentLink - Configured payment URL.
 * @returns `true` when the trimmed link is a non-empty `https://` URL.
 */
export function isBuyEnabled(paymentLink: string): boolean {
  const trimmed = paymentLink.trim();
  return trimmed !== "" && trimmed.startsWith("https://");
}

/**
 * Build a mailto URL that carries a waitlist submission in the body.
 *
 * @param recipient - Destination mailbox for the waitlist message.
 * @param submission - Field values encoded into the message body.
 * @returns A `mailto:` URL with encoded subject and body.
 */
export function buildWaitlistMailto(
  recipient: string,
  submission: WaitlistSubmission
): string {
  const subject = encodeURIComponent("Sentinel waitlist");
  const body = encodeURIComponent(
    [
      `Email: ${submission.email}`,
      `Org type: ${submission.orgType}`,
      `Burned by silent schema change: ${submission.burned}`,
      `Story: ${submission.story}`,
    ].join("\n")
  );
  return `mailto:${recipient}?subject=${subject}&body=${body}`;
}
