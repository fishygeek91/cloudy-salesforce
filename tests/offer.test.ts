/**
 * Node test-runner coverage for the Schema Sentinel marketing-site helpers.
 *
 * Exercises the price band, waitlist validation, buy-link gate, copy
 * compliance, and mailto fallback without a browser or a bundler.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { siteConfig } from "../site/config.ts";
import {
  ORG_TYPES,
  PRICE_BAND_MAX_USD,
  PRICE_BAND_MIN_USD,
  allCopyStrings,
  buildWaitlistMailto,
  copyIsCompliant,
  findForbiddenPhrases,
  formatPriceUsd,
  isBuyEnabled,
  isValidPriceUsd,
  offerCopy,
  validateWaitlist,
} from "../site/offer.ts";
import type { WaitlistSubmission } from "../site/offer.ts";

/**
 * Build a waitlist payload that passes {@link validateWaitlist}.
 *
 * @param overrides - Fields that replace the valid defaults.
 * @returns A complete {@link WaitlistSubmission}.
 */
function validWaitlist(overrides: Partial<WaitlistSubmission> = {}): WaitlistSubmission {
  return {
    email: "dev@example.com",
    orgType: "indie",
    burned: "no",
    story: "",
    ...overrides,
  };
}

/**
 * Assert that waitlist validation produced at least one error.
 *
 * @param submission - Payload to validate.
 * @param message - Failure message when the payload unexpectedly passes.
 */
function assertHasWaitlistError(submission: WaitlistSubmission, message: string): void {
  const errors = validateWaitlist(submission);
  assert.ok(Array.isArray(errors), "validateWaitlist must return an array");
  assert.ok(errors.length > 0, message);
}

describe("Price band", () => {
  it("siteConfig.priceUsd is an integer inside the advertised band", () => {
    assert.ok(Number.isInteger(siteConfig.priceUsd));
    assert.ok(siteConfig.priceUsd >= PRICE_BAND_MIN_USD);
    assert.ok(siteConfig.priceUsd <= PRICE_BAND_MAX_USD);
    assert.equal(isValidPriceUsd(siteConfig.priceUsd), true);
  });

  it("accepts the inclusive boundaries 500 and 2000", () => {
    assert.equal(isValidPriceUsd(500), true);
    assert.equal(isValidPriceUsd(2000), true);
  });

  it("rejects 499, 2001, 750.5, -750, and NaN", () => {
    assert.equal(isValidPriceUsd(499), false);
    assert.equal(isValidPriceUsd(2001), false);
    assert.equal(isValidPriceUsd(750.5), false);
    assert.equal(isValidPriceUsd(-750), false);
    assert.equal(isValidPriceUsd(Number.NaN), false);
  });

  it("formats 750 and 2000 as US-dollar strings", () => {
    assert.equal(formatPriceUsd(750), "$750");
    assert.equal(formatPriceUsd(2000), "$2,000");
  });

  it("throws RangeError for 499 and 750.5", () => {
    assert.throws(() => {
      formatPriceUsd(499);
    }, RangeError);
    assert.throws(() => {
      formatPriceUsd(750.5);
    }, RangeError);
  });
});

describe("Waitlist validation", () => {
  it("returns no errors for a complete valid submission", () => {
    const errors = validateWaitlist({
      email: "dev@example.com",
      orgType: "indie",
      burned: "no",
      story: "",
    });
    assert.deepEqual(errors, []);
  });

  it("returns at least one error when email is missing", () => {
    assertHasWaitlistError(validWaitlist({ email: "" }), "empty email must be rejected");
  });

  it("returns errors for a malformed email", () => {
    assertHasWaitlistError(
      validWaitlist({ email: "not-an-email" }),
      "malformed email must be rejected"
    );
  });

  it("returns errors for a whitespace-only email", () => {
    assertHasWaitlistError(
      validWaitlist({ email: "   " }),
      "whitespace-only email must be rejected"
    );
  });

  it("requires burned even when email is valid", () => {
    assertHasWaitlistError(
      validWaitlist({ email: "dev@example.com", burned: "" }),
      "missing burned answer must be rejected"
    );
  });

  it("requires a story when burned is story and story is empty", () => {
    assertHasWaitlistError(
      validWaitlist({ burned: "story", story: "" }),
      "burned=story with an empty story must be rejected"
    );
  });

  it("accepts burned story when the story is non-empty", () => {
    const errors = validateWaitlist(
      validWaitlist({ burned: "story", story: "Industry vanished overnight." })
    );
    assert.deepEqual(errors, []);
  });

  it("returns errors for an invalid orgType", () => {
    assertHasWaitlistError(
      validWaitlist({ orgType: "enterprise" }),
      "enterprise is not an accepted org type"
    );
  });

  it("accepts every ORG_TYPES value when other fields are valid", () => {
    for (const orgType of ORG_TYPES) {
      const errors = validateWaitlist(validWaitlist({ orgType }));
      assert.deepEqual(errors, [], `expected orgType ${orgType} to pass`);
    }
  });
});

describe("Buy state", () => {
  it("isBuyEnabled is false for an empty string", () => {
    assert.equal(isBuyEnabled(""), false);
  });

  it("isBuyEnabled is false for whitespace", () => {
    assert.equal(isBuyEnabled("   "), false);
  });

  it("isBuyEnabled is false for a non-https Stripe URL", () => {
    assert.equal(isBuyEnabled("http://buy.stripe.com/x"), false);
  });

  it("isBuyEnabled is true for an https Stripe Payment Link", () => {
    assert.equal(isBuyEnabled("https://buy.stripe.com/test_abc"), true);
  });
});

describe("Copy compliance", () => {
  it("copyIsCompliant is true for the shipped offerCopy", () => {
    assert.equal(copyIsCompliant(offerCopy), true);
    assert.equal(copyIsCompliant(), true);
  });

  it("every allCopyStrings entry is free of forbidden phrases", () => {
    const strings = allCopyStrings();
    assert.ok(strings.length > 0, "allCopyStrings must return at least one value");
    for (const text of strings) {
      assert.equal(typeof text, "string");
      assert.equal(findForbiddenPhrases(text).length, 0, `forbidden phrase in: ${text}`);
    }
  });

  it("findForbiddenPhrases matches nobody detects case-insensitively", () => {
    const hits = findForbiddenPhrases("Nobody Detects drift here");
    assert.ok(hits.includes("nobody detects"));
  });

  it("findForbiddenPhrases matches pr bot in mixed case", () => {
    const hits = findForbiddenPhrases("our PR Bot opens fixes");
    assert.ok(hits.includes("pr bot"));
  });

  it("site/index.html has no forbidden phrases and includes the headline", () => {
    const pageUrl = new URL("../site/index.html", import.meta.url);
    const html = readFileSync(pageUrl, "utf8");
    assert.equal(typeof html, "string");
    assert.ok(html.length > 0, "site/index.html must not be empty");
    assert.deepEqual(findForbiddenPhrases(html), []);
    assert.ok(html.includes("Your Salesforce admin just broke your integration."));
  });
});

describe("Mailto fallback", () => {
  it("buildWaitlistMailto encodes the recipient, subject, and email body", () => {
    const submission = validWaitlist({ email: "dev@example.com" });
    const href = buildWaitlistMailto("owner@example.com", submission);

    assert.ok(href.startsWith("mailto:owner@example.com?"));
    assert.ok(href.includes("subject=Sentinel%20waitlist"));
    assert.ok(href.includes(encodeURIComponent(submission.email)));
  });
});
