package org.setunet.mesh

import android.content.Context
import android.net.wifi.p2p.WifiP2pDevice
import android.net.wifi.p2p.WifiP2pManager
import android.util.Log
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import kotlin.concurrent.thread

/**
 * Android Wi-Fi Direct (P2P) Transport Layer (Slide 5, 6 & 7).
 * Discovers nearby peer phones without SIM, router or cellular infrastructure
 * and broadcasts emergency alerts via UDP P2P sockets.
 */
class WifiDirectTransport(
    private val context: Context,
    private val port: Int = 8988,
    private val onAlertReceived: (AlertMessage) -> Unit
) {
    private val tag = "SetuNetWifiDirect"
    private var isListening = false
    private var socket: DatagramSocket? = null

    fun startListening() {
        if (isListening) return
        isListening = true
        thread(name = "setunet-p2p-listener") {
            try {
                socket = DatagramSocket(port)
                val buffer = ByteArray(4096)
                while (isListening) {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket?.receive(packet)
                    val rawJson = String(packet.data, 0, packet.length, Charsets.UTF_8)
                    Log.d(tag, "Received P2P mesh alert: $rawJson")
                    // Parse alert from JSON and deliver to onAlertReceived callback
                }
            } catch (e: Exception) {
                Log.e(tag, "P2P socket error: ${e.message}")
            }
        }
    }

    fun broadcastPacket(alertJsonBytes: ByteArray, broadcastIp: String = "255.255.255.255") {
        thread(name = "setunet-p2p-sender") {
            try {
                val sendSocket = DatagramSocket()
                sendSocket.broadcast = true
                val addr = InetAddress.getByName(broadcastIp)
                val packet = DatagramPacket(alertJsonBytes, alertJsonBytes.size, addr, port)
                sendSocket.send(packet)
                sendSocket.close()
                Log.d(tag, "Broadcasted P2P alert packet (${alertJsonBytes.size} bytes)")
            } catch (e: Exception) {
                Log.e(tag, "Broadcast error: ${e.message}")
            }
        }
    }

    fun stop() {
        isListening = false
        socket?.close()
    }
}
