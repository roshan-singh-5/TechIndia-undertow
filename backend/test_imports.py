"""Focused regression tests for the CSV import boundary."""
import unittest

import main


GOOD = b"transaction_id,timestamp,sender_account,receiver_account,amount,device_id\nT-1,2026-01-01 10:00:00,A-1,B-1,12.50,D-1\nT-2,2026-01-01T10:02:00Z,B-1,C-1,9,D-2\n"


class BankImportTests(unittest.TestCase):
    def test_valid_aliases_normalize_and_analyse(self):
        payload = b"Transaction ID,Transaction Time,From Account,To Account,Transaction Amount\nX-1,01/02/2026 10:30,A,B,100\n"
        frame, report = main.validate_bank_csv(payload, "authorised.csv")
        self.assertTrue(report["valid"])
        self.assertTrue(set(["transaction_id", "timestamp", "sender_account", "receiver_account", "amount"]).issubset(frame.columns))
        result = main.process_analysis(frame, "authorised.csv")
        self.assertEqual(result["summary"]["transactions"], 1)

    def test_missing_columns_invalid_amount_timestamp_and_duplicates(self):
        _, missing = main.validate_bank_csv(b"id,amount\n1,2\n", "x.csv")
        self.assertFalse(missing["valid"])
        bad = b"transaction_id,timestamp,sender_account,receiver_account,amount\nD,not-a-time,A,B,nope\nD,2026-01-01,A,C,1\n"
        _, report = main.validate_bank_csv(bad, "x.csv")
        self.assertFalse(report["valid"])
        messages = " ".join(" ".join(item["errors"]) for item in report["errors"])
        self.assertIn("amount", messages)
        self.assertIn("timestamp", messages)
        self.assertIn("duplicated", messages)

    def test_empty_malformed_and_oversized_rejected(self):
        for payload in (b"", b"transaction_id,timestamp\n\"unterminated"):
            _, report = main.validate_bank_csv(payload, "x.csv")
            self.assertFalse(report["valid"])
        _, report = main.validate_bank_csv(b"x" * (main.MAX_CSV_BYTES + 1), "x.csv")
        self.assertFalse(report["valid"])

    def test_failed_validation_preserves_previous_analysis(self):
        frame, report = main.validate_bank_csv(GOOD, "valid.csv")
        self.assertTrue(report["valid"])
        active = main.process_analysis(frame, "valid.csv")
        _, failed = main.validate_bank_csv(b"transaction_id,timestamp,sender_account,receiver_account,amount\nT-1,bad,A,B,1\n", "bad.csv")
        self.assertFalse(failed["valid"])
        self.assertIs(main.latest_analysis, active)


if __name__ == "__main__":
    unittest.main()
