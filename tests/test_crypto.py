"""Unit tests for Ed25519 digital signature generation, verification, and tamper detection."""

import unittest

from src.mesh.crypto import generate_keypair, sign_message, verify_signature
from src.mesh.protocol import AlertCategory, AlertMessage, GPSLocation


class TestCryptoSignatures(unittest.TestCase):
    def test_keypair_generation(self):
        kp = generate_keypair()
        self.assertEqual(len(kp.public_bytes), 32)
        self.assertEqual(len(kp.private_bytes), 32)
        self.assertEqual(len(kp.public_hex), 64)

    def test_signature_validity(self):
        kp = generate_keypair()
        payload = b"EMERGENCY EVACUATION ORDER: SECTOR 7"
        sig = sign_message(kp, payload)
        self.assertTrue(verify_signature(kp.public_hex, payload, sig))

    def test_tampered_payload_rejected(self):
        kp = generate_keypair()
        payload = b"ORIGINAL CLEAN PAYLOAD"
        sig = sign_message(kp, payload)
        tampered_payload = b"CORRUPTED / FORGED PAYLOAD"
        self.assertFalse(verify_signature(kp.public_hex, tampered_payload, sig))

    def test_wrong_public_key_rejected(self):
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        payload = b"AUTHENTIC BROADCAST"
        sig = sign_message(kp1, payload)
        # Attempt to verify with kp2's public key
        self.assertFalse(verify_signature(kp2.public_hex, payload, sig))

    def test_alert_canonical_bytes_tamper_detection(self):
        kp = generate_keypair()
        alert = AlertMessage(
            message_id="SETU-TEST-001",
            category=AlertCategory.SOS,
            origin_node_id="phone-1",
            payload_text="Real SOS alert",
            location=GPSLocation(28.6139, 77.2090),
            public_key=kp.public_hex,
        )
        alert.signature = sign_message(kp, alert.canonical_bytes())
        self.assertTrue(verify_signature(alert.public_key, alert.canonical_bytes(), alert.signature))

        # Tampering with location coordinates invalidates signature
        alert.location.latitude = 29.9999
        self.assertFalse(verify_signature(alert.public_key, alert.canonical_bytes(), alert.signature))


if __name__ == "__main__":
    unittest.main()
