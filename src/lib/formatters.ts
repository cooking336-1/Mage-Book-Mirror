/**
 * Ghanaian Statutory Identifier Formatters and Validators.
 *
 * Implements:
 * - GRA Taxpayer Identification Number (TIN): 11 chars, 1 prefix letter (C, P, V, G, T) + 10 digits (e.g. C0001234567).
 * - Ghana Card (NIA National ID): GHA-XXXXXXXXX-X (e.g. GHA-123456789-0).
 */

/**
 * Formats a raw Ghana Card input into canonical `GHA-XXXXXXXXX-X`.
 * Handles inputs like "1234567890", "gha1234567890", or "GHA-123456789-0".
 */
export function formatGhanaCard(val: string): string {
  if (!val) return "";
  const cleaned = val.trim().toUpperCase();
  // Extract all digits from input
  const digits = cleaned.replace(/[^0-9]/g, "");
  if (!digits) return cleaned.startsWith("GHA") ? cleaned : "";
  const mainPart = digits.slice(0, 9);
  const checkDigit = digits.slice(9, 10);
  if (digits.length <= 9) {
    return `GHA-${mainPart}`;
  }
  return `GHA-${mainPart}-${checkDigit}`;
}

/**
 * Formats a GRA Taxpayer Identification Number (TIN).
 * Strips extraneous spaces and normalizes to uppercase (e.g. " c0001234567 " -> "C0001234567").
 */
export function formatGraTin(val: string): string {
  if (!val) return "";
  return val.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
}

/**
 * Validates whether a Ghana Card PIN strictly conforms to NIA statutory format: GHA-XXXXXXXXX-X.
 */
export function validateGhanaCard(val: string): boolean {
  if (!val) return false;
  return /^GHA-\d{9}-\d$/.test(val.trim().toUpperCase());
}

/**
 * Validates whether a TIN strictly conforms to GRA format: [CPVGT] followed by 10 digits.
 */
export function validateGraTin(val: string): boolean {
  if (!val) return false;
  return /^[CPVGT]\d{10}$/.test(val.trim().toUpperCase());
}

/**
 * Returns human-readable validation error or null for Ghana Card.
 */
export function getGhanaCardError(val: string): string | null {
  if (!val) return null;
  if (!validateGhanaCard(val)) {
    return "Ghana Card must match format GHA-XXXXXXXXX-X (e.g. GHA-123456789-0)";
  }
  return null;
}

/**
 * Returns human-readable validation error or null for GRA TIN.
 */
export function getGraTinError(val: string): string | null {
  if (!val) return null;
  if (!validateGraTin(val)) {
    return "GRA TIN must start with C, P, V, G, or T followed by 10 digits (e.g. C0001234567)";
  }
  return null;
}
