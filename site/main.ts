/**
 * Browser entry point for the Schema Sentinel static sales page.
 *
 * Bundled by esbuild as an IIFE (`site/dist/main.js`) and loaded as a
 * classic script at the end of `site/index.html`, after the DOM exists.
 * Exported helpers stay importable from Node tests; the top-level
 * `initSite(document)` call is gated so that import does not crash.
 */

import { siteConfig, type SiteConfig } from "./config.ts";
import {
  buildWaitlistMailto,
  formatPriceUsd,
  isBuyEnabled,
  validateWaitlist,
  type WaitlistSubmission,
} from "./offer.ts";

/** Fallback buy-button label when {@link formatPriceUsd} rejects the price. */
const BUY_LABEL_FALLBACK = "Buy setup";

/** Submit-button label shown while a waitlist POST is in flight. */
const WAITLIST_SUBMITTING_LABEL = "Joining…";

/** Default submit-button label when the markup has no usable text. */
const WAITLIST_IDLE_LABEL = "Join the waitlist";

/**
 * Build the unreachable-waitlist error line using the public contact email.
 *
 * @param email - Fallback mailbox from site config.
 * @returns A single human-readable error string.
 */
export function waitlistUnreachableMessage(email: string): string {
  return `Could not reach the waitlist service. Email us instead: ${email}`;
}

/**
 * Read waitlist field values from `form`.
 *
 * Uses `instanceof` after `querySelector` so missing or unexpected
 * controls never require a non-null assertion or unchecked cast.
 *
 * @param form - The waitlist form element.
 * @returns A {@link WaitlistSubmission}, or `null` when a required control is missing.
 */
export function readSubmission(form: HTMLFormElement): WaitlistSubmission | null {
  const emailInput = form.querySelector("#waitlist-email");
  if (!(emailInput instanceof HTMLInputElement)) {
    console.error("Missing required waitlist email input (#waitlist-email).");
    return null;
  }

  const orgTypeSelect = form.querySelector("#waitlist-org-type");
  if (!(orgTypeSelect instanceof HTMLSelectElement)) {
    console.error("Missing required waitlist org-type select (#waitlist-org-type).");
    return null;
  }

  const storyInput = form.querySelector("#waitlist-story");
  if (!(storyInput instanceof HTMLTextAreaElement)) {
    console.error("Missing required waitlist story textarea (#waitlist-story).");
    return null;
  }

  const burnedInput = form.querySelector("input[name=\"burned\"]:checked");
  const burned = burnedInput instanceof HTMLInputElement ? burnedInput.value : "";

  return {
    email: emailInput.value,
    orgType: orgTypeSelect.value,
    burned,
    story: storyInput.value,
  };
}

/**
 * Replace `container` contents with a list of error messages.
 *
 * Builds the list with `createElement` and `textContent` so user-controlled
 * validation text is never assigned through `innerHTML`.
 *
 * @param container - Element that displays waitlist errors.
 * @param errors - Human-readable validation or network errors.
 */
export function renderErrors(container: HTMLElement, errors: readonly string[]): void {
  const doc = container.ownerDocument;
  while (container.firstChild !== null) {
    container.removeChild(container.firstChild);
  }

  if (errors.length === 0) {
    return;
  }

  const list = doc.createElement("ul");
  for (const message of errors) {
    const item = doc.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  }
  container.appendChild(list);
}

/**
 * Hide a success or status element by setting the `hidden` attribute.
 *
 * @param element - Element to hide.
 */
export function hideStatus(element: HTMLElement): void {
  element.hidden = true;
}

/**
 * Reveal a success or status element by removing the `hidden` attribute.
 *
 * @param element - Element to show.
 */
export function showStatus(element: HTMLElement): void {
  element.removeAttribute("hidden");
}

/**
 * Format the buy-button label, falling back when the price is out of band.
 *
 * @param priceUsd - Integer USD amount from site config.
 * @returns A buy-button label safe to assign to `textContent`.
 */
export function formatBuyButtonLabel(priceUsd: number): string {
  try {
    return `Buy setup — ${formatPriceUsd(priceUsd)}`;
  } catch (error) {
    if (error instanceof RangeError) {
      console.error(error);
      return BUY_LABEL_FALLBACK;
    }
    throw error;
  }
}

/**
 * Wire the setup-package buy control from live site config.
 *
 * When a Payment Link is configured, the control becomes an external
 * checkout link. Otherwise the markup fallback (`#waitlist`,
 * `aria-disabled`) is left alone so in-page navigation still works.
 *
 * @param button - The buy-button anchor.
 * @param config - Public site configuration.
 */
export function initBuyButton(button: HTMLAnchorElement, config: SiteConfig): void {
  if (!isBuyEnabled(config.paymentLink)) {
    return;
  }

  button.href = config.paymentLink.trim();
  button.removeAttribute("aria-disabled");
  button.rel = "noopener noreferrer";
  button.target = "_blank";
  button.textContent = formatBuyButtonLabel(config.priceUsd);
}

/**
 * Paint the setup price into `priceEl` from a USD integer.
 *
 * On {@link RangeError}, the existing text (the server-rendered default)
 * is kept and the error is logged.
 *
 * @param priceEl - Element that displays the formatted price.
 * @param priceUsd - Integer USD amount to format.
 */
export function initPriceDisplay(priceEl: HTMLElement, priceUsd: number): void {
  try {
    priceEl.textContent = formatPriceUsd(priceUsd);
  } catch (error) {
    if (error instanceof RangeError) {
      console.error(error);
      return;
    }
    throw error;
  }
}

/**
 * POST a validated waitlist payload to a Formspree-compatible endpoint.
 *
 * @param action - Trimmed non-empty form endpoint URL.
 * @param submission - Values collected from the waitlist form.
 * @returns The fetch {@link Response}.
 */
export async function postWaitlist(
  action: string,
  submission: WaitlistSubmission
): Promise<Response> {
  const body = new FormData();
  body.append("email", submission.email);
  body.append("orgType", submission.orgType);
  body.append("burned", submission.burned);
  body.append("story", submission.story);

  return fetch(action, {
    method: "POST",
    headers: {
      "Accept": "application/json",
    },
    body,
  });
}

/**
 * Validate one waitlist submit and deliver it via POST or mailto.
 *
 * @param form - The waitlist form being submitted.
 * @param config - Public site configuration.
 * @param errorsContainer - Live region for validation and network errors.
 * @param successEl - Success copy shown after a completed join.
 * @param submitButton - Submit control disabled while a POST is in flight.
 */
export async function submitWaitlist(
  form: HTMLFormElement,
  config: SiteConfig,
  errorsContainer: HTMLElement,
  successEl: HTMLElement,
  submitButton: HTMLButtonElement
): Promise<void> {
  const submission = readSubmission(form);
  if (submission === null) {
    return;
  }

  const errors = validateWaitlist(submission);
  if (errors.length > 0) {
    renderErrors(errorsContainer, errors);
    hideStatus(successEl);
    return;
  }

  const action = config.waitlistAction.trim();
  if (action === "") {
    window.location.href = buildWaitlistMailto(config.email, submission);
    renderErrors(errorsContainer, []);
    showStatus(successEl);
    return;
  }

  const previousLabel =
    submitButton.textContent === null || submitButton.textContent.trim() === ""
      ? WAITLIST_IDLE_LABEL
      : submitButton.textContent;

  submitButton.disabled = true;
  submitButton.textContent = WAITLIST_SUBMITTING_LABEL;

  try {
    const response = await postWaitlist(action, submission);
    if (response.ok) {
      renderErrors(errorsContainer, []);
      showStatus(successEl);
      form.reset();
      return;
    }

    renderErrors(errorsContainer, [waitlistUnreachableMessage(config.email)]);
  } catch (error) {
    console.error(error);
    renderErrors(errorsContainer, [waitlistUnreachableMessage(config.email)]);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = previousLabel;
  }
}

/**
 * Attach the waitlist submit handler to `form`.
 *
 * @param form - The waitlist form.
 * @param config - Public site configuration.
 */
export function initWaitlistForm(form: HTMLFormElement, config: SiteConfig): void {
  const errorsEl = form.querySelector("#waitlist-errors");
  if (!(errorsEl instanceof HTMLElement)) {
    console.error("Missing required waitlist errors container (#waitlist-errors).");
    return;
  }

  const successEl = form.querySelector("#waitlist-success");
  if (!(successEl instanceof HTMLElement)) {
    console.error("Missing required waitlist success message (#waitlist-success).");
    return;
  }

  const submitButton = form.querySelector("#waitlist-submit");
  if (!(submitButton instanceof HTMLButtonElement)) {
    console.error("Missing required waitlist submit button (#waitlist-submit).");
    return;
  }

  form.addEventListener("submit", (event: Event): void => {
    event.preventDefault();
    void submitWaitlist(form, config, errorsEl, successEl, submitButton);
  });
}

/**
 * Bind interactive sales-page behavior on `doc`.
 *
 * Missing controls are skipped. Required waitlist pieces log and return
 * from their own initializers.
 *
 * @param doc - Document whose sales-page controls should be wired.
 */
export function initSite(doc: Document): void {
  const buyButton = doc.getElementById("buy-button");
  if (buyButton instanceof HTMLAnchorElement) {
    initBuyButton(buyButton, siteConfig);
  }

  const priceEl = doc.getElementById("price-usd");
  if (priceEl instanceof HTMLElement) {
    initPriceDisplay(priceEl, siteConfig.priceUsd);
  }

  const form = doc.getElementById("waitlist-form");
  if (form instanceof HTMLFormElement) {
    initWaitlistForm(form, siteConfig);
  }
}

if (typeof document !== "undefined") {
  initSite(document);
}
