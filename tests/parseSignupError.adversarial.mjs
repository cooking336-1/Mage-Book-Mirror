/**
 * Adversarial and Empirical Test Harness for `parseSignupError`
 * Extracted directly from src/app/(auth)/signup/page.tsx
 */

import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";

// 1. Read parseSignupError source directly from page.tsx to guarantee 100% fidelity
const pagePath = path.resolve("src/app/(auth)/signup/page.tsx");
const pageSource = fs.readFileSync(pagePath, "utf-8");

const fnStartMatch = pageSource.indexOf("function parseSignupError");
if (fnStartMatch === -1) {
  throw new Error("Could not find parseSignupError in page.tsx");
}

const fnEndMatch = pageSource.indexOf("export default function SignUpPage");
if (fnEndMatch === -1) {
  throw new Error("Could not find SignUpPage export in page.tsx");
}

let fnSnippet = pageSource.substring(fnStartMatch, fnEndMatch).trim();

// Strip TypeScript annotations cleanly using exact block indices
const axiosStart = fnSnippet.indexOf("const axiosErr =");
const axiosEnd = fnSnippet.indexOf("// Case 1:");
const axiosBlock = fnSnippet.slice(axiosStart, axiosEnd);

fnSnippet = fnSnippet
  .replace("function parseSignupError(err: unknown): ParsedSignupError {", "function parseSignupError(err) {")
  .replace("const result: ParsedSignupError =", "const result =")
  .replace(axiosBlock, "const axiosErr = err;\n\n  ")
  .replace("const errorObj = data as Record<string, unknown>;", "const errorObj = data;")
  .replace('typeof (data as { detail: unknown }).detail === "string"', 'typeof data.detail === "string"')
  .replace('(data as { detail: string }).detail', 'data.detail');

// Create executable function via constructor
const parseSignupError = new Function(`${fnSnippet}; return parseSignupError;`)();

console.log("=== EMPIRICAL ADVERSARIAL TEST SUITE: parseSignupError ===\n");
let passed = 0;
let total = 0;

function runTest(name, fn) {
  total++;
  try {
    fn();
    console.log(`[PASS] ${name}`);
    passed++;
  } catch (err) {
    console.error(`[FAIL] ${name}`);
    console.error(err);
  }
}

// ----------------------------------------------------
// Category 1: DRF Standard Responses
// ----------------------------------------------------
runTest("1. DRF standard field error dict (email + password)", () => {
  const err = {
    response: {
      status: 400,
      data: {
        email: ["User with this email already exists."],
        password: ["Too short."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.email, "User with this email already exists.");
  assert.equal(res.fieldErrors.password, "Too short.");
  assert.equal(res.generalError, null);
});

runTest("2. Multiple errors joined cleanly per field", () => {
  const err = {
    response: {
      status: 400,
      data: {
        email: ["Invalid format.", "Already taken."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.email, "Invalid format. Already taken.");
  assert.equal(res.generalError, null);
});

runTest("3. Non-field errors as array", () => {
  const err = {
    response: {
      status: 400,
      data: {
        non_field_errors: ["Rate limit exceeded."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Rate limit exceeded.");
  assert.deepEqual(res.fieldErrors, {});
});

runTest("4. Non-field errors as string", () => {
  const err = {
    response: {
      status: 400,
      data: {
        non_field_errors: "Rate limit exceeded.",
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Rate limit exceeded.");
});

runTest("5. String error in detail", () => {
  const err = {
    response: {
      status: 401,
      data: {
        detail: "Authentication credentials were not provided.",
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Authentication credentials were not provided.");
});

runTest("6. Array error in detail", () => {
  const err = {
    response: {
      status: 400,
      data: {
        detail: ["Invalid token.", "Session expired."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Invalid token. Session expired.");
});

runTest("7. Top-level message fallback", () => {
  const err1 = { response: { status: 400, data: { message: "Account registration is temporarily disabled." } } };
  const res1 = parseSignupError(err1);
  assert.equal(res1.generalError, "Account registration is temporarily disabled.");
});

runTest("8. Top-level error fallback", () => {
  const err2 = { response: { status: 400, data: { error: "Organization capacity reached." } } };
  const res2 = parseSignupError(err2);
  assert.equal(res2.generalError, "Organization capacity reached.");
});

// ----------------------------------------------------
// Category 2: Unhandled / Unknown DRF Keys
// ----------------------------------------------------
runTest("9. Unhandled DRF key (phone_number) surfaced in both fieldErrors and generalError", () => {
  const err = {
    response: {
      status: 400,
      data: {
        phone_number: ["Invalid phone number."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.phone_number, "Invalid phone number.");
  assert.equal(res.generalError, "phone number: Invalid phone number.");
});

runTest("10. Multiple unhandled keys surfaced informatively in general banner", () => {
  const err = {
    response: {
      status: 400,
      data: {
        first_name: ["Required."],
        last_name: ["Required."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.first_name, "Required.");
  assert.equal(res.fieldErrors.last_name, "Required.");
  assert.equal(res.generalError, "first name: Required.; last name: Required.");
});

runTest("11. Handled field error + unhandled key simultaneously", () => {
  const err = {
    response: {
      status: 400,
      data: {
        email: ["Invalid email."],
        invitation_code: ["Expired code."],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.email, "Invalid email.");
  assert.equal(res.fieldErrors.invitation_code, "Expired code.");
  assert.equal(res.generalError, "invitation code: Expired code.");
});

// ----------------------------------------------------
// Category 3: Malformed & Unexpected Payloads
// ----------------------------------------------------
runTest("12. Null error input", () => {
  const res = parseSignupError(null);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
  assert.deepEqual(res.fieldErrors, {});
});

runTest("13. Undefined error input", () => {
  const res = parseSignupError(undefined);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("14. Primitive string error input", () => {
  const res = parseSignupError("Raw string error");
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("15. Primitive number error input", () => {
  const res = parseSignupError(500);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("16. Primitive boolean error input", () => {
  const res = parseSignupError(false);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("17. Empty object error input", () => {
  const res = parseSignupError({});
  assert.equal(res.generalError, "Network error: Unable to contact server. Please try again.");
});

runTest("18. Response with null data", () => {
  const err = { response: { status: 400, data: null } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("19. Response with undefined data", () => {
  const err = { response: { status: 400, data: undefined } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("20. Response with empty object data", () => {
  const err = { response: { status: 400, data: {} } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("21. Response with raw string data 'Bad Request'", () => {
  const err = { response: { status: 400, data: "Bad Request" } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Bad Request");
});

runTest("22. Response with empty string data", () => {
  const err = { response: { status: 400, data: "" } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("23. Response with array data", () => {
  const err = { response: { status: 400, data: ["Unexpected top level array error"] } };
  const res = parseSignupError(err);
  assert.ok(res.generalError);
});

runTest("24. Response with number data", () => {
  const err = { response: { status: 400, data: 404 } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

// ----------------------------------------------------
// Category 4: Server / 5xx Errors
// ----------------------------------------------------
runTest("25. 500 error with HTML <!DOCTYPE html>", () => {
  const err = {
    response: {
      status: 500,
      data: "<!DOCTYPE html><html><body><h1>Internal Server Error</h1></body></html>",
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Server error (500). The server encountered an issue. Please try again later.");
});

runTest("26. 502 Bad Gateway with <html>", () => {
  const err = {
    response: {
      status: 502,
      data: "<html><head><title>502 Bad Gateway</title></head></html>",
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Server error (502). The server encountered an issue. Please try again later.");
});

runTest("27. 500 error with OperationalError (database locked)", () => {
  const err = {
    response: {
      status: 500,
      data: "django.db.utils.OperationalError: database is locked",
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Database service is temporarily unavailable. Please try again shortly.");
});

runTest("28. 500 error with JSON detail", () => {
  const err = {
    response: {
      status: 500,
      data: {
        detail: "Service maintenance window in progress.",
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Service maintenance window in progress.");
});

runTest("29. 503 Service Unavailable with null data", () => {
  const err = {
    response: {
      status: 503,
      data: null,
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Server error (503). Please try again later.");
});

// ----------------------------------------------------
// Category 5: Network / Connection Failures
// ----------------------------------------------------
runTest("30. Network Error with code ERR_NETWORK", () => {
  const err = {
    code: "ERR_NETWORK",
    message: "Network Error",
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to connect to authentication server. Please check your network connection.");
});

runTest("31. Network Error with new Error('Network Error')", () => {
  const err = new Error("Network Error");
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to connect to authentication server. Please check your network connection.");
});

runTest("32. Specific network failure message without response (ECONNREFUSED)", () => {
  const err = new Error("connect ECONNREFUSED 127.0.0.1:8000");
  const res = parseSignupError(err);
  assert.equal(res.generalError, "connect ECONNREFUSED 127.0.0.1:8000");
});

runTest("33. Network error with empty message", () => {
  const err = { message: "" };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Network error: Unable to contact server. Please try again.");
});

// ----------------------------------------------------
// Category 6: Mixed Data Types & Adversarial Payloads
// ----------------------------------------------------
runTest("34. Mixed data types: email as number, password as nested object", () => {
  const err = {
    response: {
      status: 400,
      data: {
        email: 12345,
        password: { nested: "error" },
      },
    },
  };
  const res = parseSignupError(err);
  // Must not crash and should fall back safely to generic generalError
  assert.equal(res.generalError, "Unable to create account. Please try again.");
  assert.deepEqual(res.fieldErrors, {});
});

runTest("35. Array with mixed non-string types", () => {
  const err = {
    response: {
      status: 400,
      data: {
        email: [12345, null, "Malformed value", true],
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.email, "12345 null Malformed value true");
});

runTest("36. Detail as nested object (unusual 400 response)", () => {
  const err = {
    response: {
      status: 400,
      data: {
        detail: { code: "INVALID", text: "Invalid input" },
      },
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("37. Massive string payload (10,000 characters)", () => {
  const bigStr = "A".repeat(10000);
  const err = {
    response: {
      status: 400,
      data: bigStr,
    },
  };
  const res = parseSignupError(err);
  assert.equal(res.generalError, bigStr);
});

// ----------------------------------------------------
// Category 7: Additional Stress & Boundary Tests
// ----------------------------------------------------
runTest("38. Response data is boolean false", () => {
  const err = { response: { status: 400, data: false } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("39. Response data is number zero", () => {
  const err = { response: { status: 400, data: 0 } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("40. Function passed as err", () => {
  const res = parseSignupError(() => {});
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("41. Circular reference inside response data", () => {
  const circular = { email: ["Duplicate email"] };
  circular.self = circular;
  const err = { response: { status: 400, data: circular } };
  const res = parseSignupError(err);
  assert.equal(res.fieldErrors.email, "Duplicate email");
  assert.equal(res.generalError, null);
});

runTest("42. Non-field errors as number", () => {
  const err = { response: { status: 400, data: { non_field_errors: 12345 } } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("43. Detail as number", () => {
  const err = { response: { status: 400, data: { detail: 9999 } } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

runTest("44. Empty arrays in field errors", () => {
  const err = { response: { status: 400, data: { email: [], password: [] } } };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
  assert.deepEqual(res.fieldErrors, {});
});

runTest("45. Malformed response object: response is string instead of object", () => {
  const err = { response: "Malformed response string" };
  const res = parseSignupError(err);
  assert.equal(res.generalError, "Unable to create account. Please try again.");
});

// ----------------------------------------------------
// Summary
// ----------------------------------------------------
console.log(`\nResults: ${passed} / ${total} tests passed.`);
if (passed !== total) {
  process.exit(1);
}
