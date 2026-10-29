import unittest
from unittest.mock import patch

from app import app


class PasswordResetTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = app.test_client()

    def test_recovery_pages_are_public(self):
        self.assertEqual(self.client.get("/forgot-password").status_code, 200)
        with patch("app.password_reset_token_is_valid", return_value=False):
            response = self.client.get("/reset-password/invalid-token")
        self.assertEqual(response.status_code, 200)
        self.assertIn("inválido", response.get_data(as_text=True))

    @patch("app.send_password_reset")
    @patch("app.create_password_reset_token")
    @patch("app.find_user_by_email")
    def test_forgot_password_creates_and_sends_token(self, find_user, create_token, send_mail):
        find_user.return_value = {"id": 7, "email": "user@example.com"}
        response = self.client.post("/api/auth/forgot-password", json={"email": "user@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Si el correo", response.get_json()["message"])
        create_token.assert_called_once()
        send_mail.assert_called_once()

    @patch("app.consume_password_reset_token", return_value=True)
    def test_reset_password_uses_hash(self, consume_token):
        response = self.client.post("/api/auth/reset-password", json={"token": "valid-token", "password": "NewPassword123!"})
        self.assertEqual(response.status_code, 200)
        password_hash = consume_token.call_args.args[1]
        self.assertNotEqual(password_hash, "NewPassword123!")
        self.assertTrue(password_hash.startswith("scrypt:"))


if __name__ == "__main__":
    unittest.main()
