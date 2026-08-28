import unittest

from security_core import generate_totp_secret, totp_code, totp_uri, verify_totp


class TotpSecurityTests(unittest.TestCase):
    SECRET = "JBSWY3DPEHPK3PXP"

    def test_generated_secret_has_sufficient_entropy_length(self):
        self.assertGreaterEqual(len(generate_totp_secret()), 26)

    def test_totp_is_deterministic_for_same_time_step(self):
        base=(1_700_000_000//30)*30+1
        self.assertEqual(totp_code(self.SECRET, base), totp_code(self.SECRET, base+10))

    def test_verify_accepts_current_code(self):
        when = 1_700_000_000
        code = totp_code(self.SECRET, when)
        self.assertTrue(verify_totp(self.SECRET, code, for_time=when))

    def test_verify_accepts_one_step_clock_skew(self):
        when = 1_700_000_000
        code = totp_code(self.SECRET, when - 30)
        self.assertTrue(verify_totp(self.SECRET, code, window=1, for_time=when))

    def test_invalid_code_rejected(self):
        self.assertFalse(verify_totp(self.SECRET, "000000", for_time=1_700_000_000))
        self.assertFalse(verify_totp(self.SECRET, "abc"))

    def test_uri_is_authenticator_compatible(self):
        uri = totp_uri(self.SECRET, "controller@example.edu")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("secret=" + self.SECRET, uri)


if __name__ == "__main__":
    unittest.main()
