"""Ghanaian Statutory Identifiers & Luhn Checksum Boundary Value Analysis (Task C.11 / T3.2).

Verifies compliance with:
1. GRA Taxpayer Identification Number (TIN):
   - Valid statutory prefixes: C (Company), P (Personal), Q (Partnership),
     V (Charity/Trust), G (Government).
   - Strict length constraints: exactly 11 characters.
   - Rejection of invalid prefixes (A, B, X, Z) and non-numeric suffixes.
   - Prohibiting degenerate all-zero numbers (e.g. C0000000000).
   - Normalization: whitespace and hyphen stripping, uppercase coercion.

2. Ghana Card National ID (NIA PIN):
   - Format: GHA-XXXXXXXXX-X (exactly 15 characters).
   - Prefix and hyphen delimiters validation.
   - Rejection of degenerate numbers (GHA-000000000-0).
   - Normalization: whitespace stripping, uppercase coercion.

3. Luhn Mod-10 Check Digit & Transposition Security:
   - Check digit calculation and self-validating payment reference generation.
   - 100% single-digit transcription error detection.
   - Adjacent transposition error trapping.
   - Rejection of tampered, malformed, and degenerate codes.
"""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.invoicing.utils import (
    LuhnValidator,
    is_valid_ghana_card,
    is_valid_gra_tin,
    normalize_ghana_card,
    normalize_gra_tin,
    validate_ghana_card,
    validate_gra_tin,
)


class GhanaTINBoundaryTests(SimpleTestCase):
    """BVA test cases for GRA Taxpayer Identification Numbers."""

    def test_valid_tin_statutory_prefixes(self) -> None:
        """Verifies each legal GRA prefix (C, P, Q, V, G) is accepted and normalized."""
        valid_tins = [
            ("C0001234567", "Corporate"),
            ("P1234567890", "Personal"),
            ("Q9876543210", "Partnership"),
            ("V5551234567", "Charity/Trust"),
            ("G0011223344", "Government"),
        ]
        for tin, entity_type in valid_tins:
            with self.subTest(prefix=tin[0], entity=entity_type):
                self.assertTrue(is_valid_gra_tin(tin))
                self.assertEqual(validate_gra_tin(tin), tin)

    def test_lowercase_prefix_normalization(self) -> None:
        """Verifies lowercase prefixes (e.g. c0001234567) are normalized to uppercase."""
        self.assertEqual(normalize_gra_tin("c0001234567"), "C0001234567")
        self.assertTrue(is_valid_gra_tin("c0001234567"))
        self.assertEqual(validate_gra_tin("c0001234567"), "C0001234567")

    def test_whitespace_and_hyphen_cleaning(self) -> None:
        """Verifies hyphens and spaces are stripped during TIN normalization."""
        messy_tin = " C-000 1234-567 "
        self.assertEqual(normalize_gra_tin(messy_tin), "C0001234567")
        self.assertTrue(is_valid_gra_tin(messy_tin))
        self.assertEqual(validate_gra_tin(messy_tin), "C0001234567")

    def test_invalid_prefixes_rejected(self) -> None:
        """Verifies invalid prefixes (A, B, D, X, Z, 9) raise ValidationError."""
        invalid_prefixes = ["A", "B", "D", "E", "F", "H", "X", "Z", "1", "9"]
        for p in invalid_prefixes:
            invalid_tin = f"{p}0001234567"
            with self.subTest(prefix=p):
                self.assertFalse(is_valid_gra_tin(invalid_tin))
                with self.assertRaises(ValidationError) as ctx:
                    validate_gra_tin(invalid_tin)
                self.assertIn("Invalid GRA TIN prefix", str(ctx.exception))

    def test_length_boundary_constraints(self) -> None:
        """BVA on character length: 10 (short), 11 (exact), 12 (long)."""
        ten_chars = "C000123456"
        eleven_chars = "C0001234567"
        twelve_chars = "C00012345678"

        self.assertFalse(is_valid_gra_tin(ten_chars))
        with self.assertRaises(ValidationError) as ctx_short:
            validate_gra_tin(ten_chars)
        self.assertIn("Invalid GRA TIN length", str(ctx_short.exception))

        self.assertTrue(is_valid_gra_tin(eleven_chars))
        self.assertEqual(validate_gra_tin(eleven_chars), eleven_chars)

        self.assertFalse(is_valid_gra_tin(twelve_chars))
        with self.assertRaises(ValidationError) as ctx_long:
            validate_gra_tin(twelve_chars)
        self.assertIn("Invalid GRA TIN length", str(ctx_long.exception))

    def test_non_numeric_suffix_rejected(self) -> None:
        """Verifies alphabetical characters within the 10-digit suffix raise ValidationError."""
        alphabetic_suffixes = ["C000123456A", "P123456789X", "C00012345#7"]
        for tin in alphabetic_suffixes:
            with self.subTest(tin=tin):
                self.assertFalse(is_valid_gra_tin(tin))
                with self.assertRaises(ValidationError):
                    validate_gra_tin(tin)

    def test_degenerate_all_zero_tins_prohibited(self) -> None:
        """Verifies degenerate sequences (e.g. C0000000000) are blocked across all prefixes."""
        for prefix in ["C", "P", "Q", "V", "G"]:
            degenerate = f"{prefix}0000000000"
            with self.subTest(prefix=prefix):
                self.assertFalse(is_valid_gra_tin(degenerate))
                with self.assertRaises(ValidationError) as ctx:
                    validate_gra_tin(degenerate)
                self.assertIn("degenerate all-zero sequences are prohibited", str(ctx.exception))

    def test_empty_or_none_tin_handling(self) -> None:
        """Verifies blank or None TINs are handled appropriately."""
        self.assertEqual(normalize_gra_tin(None), "")
        self.assertFalse(is_valid_gra_tin(None))
        self.assertFalse(is_valid_gra_tin(""))

        with self.assertRaises(ValidationError) as ctx:
            validate_gra_tin("")
        self.assertIn("cannot be blank", str(ctx.exception))


class GhanaCardBoundaryTests(SimpleTestCase):
    """BVA test cases for Ghana Card National ID (NIA PIN)."""

    def test_valid_ghana_card_formats(self) -> None:
        """Verifies standard 15-character Ghana Card PINs pass validation."""
        valid_pins = [
            "GHA-123456789-0",
            "GHA-001122334-1",
            "GHA-987654321-7",
            "GHA-555444333-9",
        ]
        for pin in valid_pins:
            with self.subTest(pin=pin):
                self.assertTrue(is_valid_ghana_card(pin))
                self.assertEqual(validate_ghana_card(pin), pin)

    def test_lowercase_prefix_and_whitespace_cleaning(self) -> None:
        """Verifies lowercase prefix is coerced to uppercase and whitespace is stripped."""
        raw_pin = " gha-123456789-0 "
        expected = "GHA-123456789-0"
        self.assertEqual(normalize_ghana_card(raw_pin), expected)
        self.assertTrue(is_valid_ghana_card(raw_pin))
        self.assertEqual(validate_ghana_card(raw_pin), expected)

    def test_prefix_constraint(self) -> None:
        """Verifies non-GHA prefixes (e.g. NGA-, KEN-, USA-) are rejected."""
        invalid_prefixes = ["NGA-123456789-0", "KEN-123456789-0", "GAB-123456789-0"]
        for pin in invalid_prefixes:
            with self.subTest(pin=pin):
                self.assertFalse(is_valid_ghana_card(pin))
                with self.assertRaises(ValidationError) as ctx:
                    validate_ghana_card(pin)
                self.assertIn("must start with the statutory prefix 'GHA-'", str(ctx.exception))

    def test_length_boundary_constraints(self) -> None:
        """BVA on character length: 14 (short), 15 (exact), 16 (long)."""
        short_pin = "GHA-12345678-0"  # 14 chars
        exact_pin = "GHA-123456789-0"  # 15 chars
        long_pin = "GHA-1234567890-0"  # 16 chars

        self.assertFalse(is_valid_ghana_card(short_pin))
        with self.assertRaises(ValidationError) as ctx_short:
            validate_ghana_card(short_pin)
        self.assertIn("Invalid Ghana Card PIN length", str(ctx_short.exception))

        self.assertTrue(is_valid_ghana_card(exact_pin))
        self.assertEqual(validate_ghana_card(exact_pin), exact_pin)

        self.assertFalse(is_valid_ghana_card(long_pin))
        with self.assertRaises(ValidationError) as ctx_long:
            validate_ghana_card(long_pin)
        self.assertIn("Invalid Ghana Card PIN length", str(ctx_long.exception))

    def test_missing_or_misplaced_hyphens(self) -> None:
        """Verifies delimiter positioning is strictly validated."""
        bad_hyphens = [
            "GHA123456789-0",  # Missing first hyphen
            "GHA-1234567890",  # Missing second hyphen
            "GHA--1234567890",  # Double hyphen
            "GHA-1234-567890",  # Misplaced hyphen
        ]
        for pin in bad_hyphens:
            with self.subTest(pin=pin):
                self.assertFalse(is_valid_ghana_card(pin))
                with self.assertRaises(ValidationError):
                    validate_ghana_card(pin)

    def test_degenerate_all_zero_ghana_card_prohibited(self) -> None:
        """Verifies degenerate GHA-000000000-0 is prohibited."""
        degenerate = "GHA-000000000-0"
        self.assertFalse(is_valid_ghana_card(degenerate))
        with self.assertRaises(ValidationError) as ctx:
            validate_ghana_card(degenerate)
        self.assertIn("degenerate all-zero sequences are prohibited", str(ctx.exception))

    def test_empty_or_none_ghana_card_handling(self) -> None:
        """Verifies blank or None PIN handling."""
        self.assertEqual(normalize_ghana_card(None), "")
        self.assertFalse(is_valid_ghana_card(None))
        self.assertFalse(is_valid_ghana_card(""))

        with self.assertRaises(ValidationError) as ctx:
            validate_ghana_card("")
        self.assertIn("cannot be blank", str(ctx.exception))


class LuhnChecksumAndTranspositionTests(SimpleTestCase):
    """Test suite validating Mod-10 Luhn check digit calculation and error trapping."""

    def test_check_digit_calculation(self) -> None:
        """Verifies accurate calculation of Luhn check digits."""
        # 84291 -> digits reversed: 1, 9, 2, 4, 8
        # idx 0: 1 * 2 = 2
        # idx 1: 9
        # idx 2: 2 * 2 = 4
        # idx 3: 4
        # idx 4: 8 * 2 = 16 -> 16 - 9 = 7
        # sum = 2 + 9 + 4 + 4 + 7 = 26.
        # (10 - (26 % 10)) % 10 = (10 - 6) = 4. Check digit is 4.
        self.assertEqual(LuhnValidator.calculate_check_digit("84291"), 4)
        self.assertEqual(LuhnValidator.calculate_check_digit(84291), 4)

    def test_reference_generation(self) -> None:
        """Verifies generation of delimited payment references."""
        ref = LuhnValidator.generate_reference("84291", delimiter="-")
        self.assertEqual(ref, "84291-4")
        self.assertTrue(LuhnValidator.validate(ref))

    def test_single_digit_transcription_error_trapping(self) -> None:
        """100% of single-digit transcription errors must be detected by LuhnValidator."""
        valid_ref = "84291-4"
        self.assertTrue(LuhnValidator.validate(valid_ref))

        # Mutate each digit in sequence to an alternate value
        for i, char in enumerate("842914"):
            mutated_digit = str((int(char) + 1) % 10)
            mutated_str = "842914"[:i] + mutated_digit + "842914"[i + 1 :]
            # Reconstruct with hyphen before last digit
            tampered_ref = f"{mutated_str[:-1]}-{mutated_str[-1]}"
            with self.subTest(original=valid_ref, tampered=tampered_ref):
                self.assertFalse(
                    LuhnValidator.validate(tampered_ref),
                    f"Tampered reference {tampered_ref} unexpectedly passed Luhn validation",
                )

    def test_adjacent_transposition_error_trapping(self) -> None:
        """Adjacent character transpositions (e.g. 84291 -> 48291) must be trapped."""
        # 84291-4: transpose 8 and 4 -> 48291-4
        transposed_ref_1 = "48291-4"
        self.assertFalse(LuhnValidator.validate(transposed_ref_1))

        # transpose 2 and 9 -> 84921-4
        transposed_ref_2 = "84921-4"
        self.assertFalse(LuhnValidator.validate(transposed_ref_2))

        # transpose 9 and 1 -> 84219-4
        transposed_ref_3 = "84219-4"
        self.assertFalse(LuhnValidator.validate(transposed_ref_3))

    def test_clean_and_validate_utility(self) -> None:
        """Verifies clean_and_validate correctly parses payload and check digit."""
        is_valid, payload, cd = LuhnValidator.clean_and_validate(" 84291-4 ")
        self.assertTrue(is_valid)
        self.assertEqual(payload, "84291")
        self.assertEqual(cd, 4)

        # Invalid reference
        is_valid_bad, payload_bad, cd_bad = LuhnValidator.clean_and_validate("84291-5")
        self.assertFalse(is_valid_bad)
        self.assertEqual(payload_bad, "84291")
        self.assertEqual(cd_bad, 5)

        # Non-numeric garbage
        is_valid_garbage, payload_garbage, cd_garbage = LuhnValidator.clean_and_validate("ABC")
        self.assertFalse(is_valid_garbage)
        self.assertIsNone(cd_garbage)

    def test_degenerate_and_empty_reference_rejection(self) -> None:
        """Verifies empty strings and degenerate sequences (000-0) are rejected."""
        self.assertFalse(LuhnValidator.validate(""))
        self.assertFalse(LuhnValidator.validate("0"))
        self.assertFalse(LuhnValidator.validate("000-0"))
        self.assertFalse(LuhnValidator.validate("---"))
