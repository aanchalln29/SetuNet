package org.setunet.mesh

import android.os.Parcelable
import kotlinx.parcelize.Parcelize
import org.json.JSONObject

/**
 * Four emergency alert categories ordered by strict priority (Slide 4).
 * Lower priority integer = Higher dispatch priority.
 */
enum class AlertCategory(val priority: Int, val label: String) {
    SOS(0, "SOS"),                         // Life-threatening emergencies (Highest priority)
    EVACUATION(1, "Evacuation"),           // Instructions to leave an area (High priority)
    TROOP_MOVEMENT(2, "Troop Movement"),   // Controlled / simulated unit orders (Medium priority)
    GENERAL(3, "General")                  // Status updates and all-clear messages (Low priority)
}

@Parcelize
data class GPSLocation(
    val latitude: Double,
    val longitude: Double,
    val altitudeMeters: Double = 0.0
) : Parcelable {
    fun toJSONObject(): JSONObject = JSONObject().apply {
        put("lat", latitude)
        put("lon", longitude)
        put("alt", altitudeMeters)
    }
}

/**
 * Emergency alert packet formatted for phone-to-phone Wi-Fi mesh (Slide 4 & 6).
 */
@Parcelize
data class AlertMessage(
    val messageId: String,
    val category: AlertCategory,
    val originNodeId: String,
    val payloadText: String,
    val location: GPSLocation,
    val timestamp: Double = System.currentTimeMillis() / 1000.0,
    var ttl: Int = 6,              // Initial TTL = 6 per Slide 6
    var hopCount: Int = 0,
    val hopPath: MutableList<String> = mutableListOf(),
    val timeOffsetEst: Double = 0.0,
    val publicKeyHex: String = "",
    var signatureHex: String = ""
) : Parcelable, Comparable<AlertMessage> {

    override fun compareTo(other: AlertMessage): Int {
        // Compare by category priority first (SOS 0 < Evacuation 1 < Troop 2 < General 3)
        val pComp = this.category.priority.compareTo(other.category.priority)
        if (pComp != 0) return pComp
        // FIFO order if same priority
        return this.timestamp.compareTo(other.timestamp)
    }

    /**
     * Canonical bytes representation for cryptographic signing and verification.
     */
    fun canonicalBytes(): ByteArray {
        val json = JSONObject().apply {
            put("message_id", messageId)
            put("category", category.name)
            put("origin_node_id", originNodeId)
            put("payload_text", payloadText)
            put("location", location.toJSONObject())
            put("timestamp", timestamp)
        }
        return json.toString().toByteArray(Charsets.UTF_8)
    }
}

/**
 * Reverse delivery acknowledgement reporting delivery back to origin sender (Slide 3 & 6).
 */
@Parcelize
data class AckMessage(
    val ackId: String,
    val originalMessageId: String,
    val alertCategory: AlertCategory,
    val ackNodeId: String,
    val originNodeId: String,
    val hopsToNode: Int,
    val receivedTimestamp: Double,
    val latencyMs: Double,
    val returnPath: List<String>,
    val status: String = "DELIVERED"
) : Parcelable
