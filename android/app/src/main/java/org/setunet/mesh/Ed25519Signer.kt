package org.setunet.mesh

import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.NamedParameterSpec

/**
 * Android Ed25519 Digital Signature Manager (Slide 7 & 10).
 * Uses Android Keystore / Java Cryptography Architecture (Ed25519) to sign
 * and verify emergency alerts on phone hardware.
 */
object Ed25519Signer {

    fun generateKeyPair(): java.security.KeyPair {
        val kpg = KeyPairGenerator.getInstance("Ed25519")
        return kpg.generateKeyPair()
    }

    fun sign(privateKey: java.security.PrivateKey, data: ByteArray): String {
        val sig = Signature.getInstance("Ed25519")
        sig.initSign(privateKey)
        sig.update(data)
        return sig.sign().joinToString("") { "%02x".format(it) }
    }

    fun verify(publicKey: java.security.PublicKey, data: ByteArray, signatureHex: String): Boolean {
        return try {
            val sigBytes = signatureHex.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
            val sig = Signature.getInstance("Ed25519")
            sig.initVerify(publicKey)
            sig.update(data)
            sig.verify(sigBytes)
        } catch (e: Exception) {
            false
        }
    }
}
