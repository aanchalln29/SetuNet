package org.setunet.mesh

import java.util.Collections
import java.util.LinkedHashMap
import java.util.concurrent.atomic.AtomicInteger

/**
 * Thread-safe LRU Duplicate Suppression Cache for Android (Slides 5, 6 & 7).
 * Prevents network broadcast storms and routing loops across Wi-Fi Direct hops.
 */
class DuplicateFilter(private val maxEntries: Int = 1000) {

    private val seenCache: MutableMap<String, Long> = Collections.synchronizedMap(
        object : LinkedHashMap<String, Long>(maxEntries, 0.75f, true) {
            override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Long>?): Boolean {
                return size > maxEntries
            }
        }
    )

    val duplicatesSuppressed = AtomicInteger(0)

    /**
     * Returns true if message is a duplicate (discard); false if fresh (relay).
     */
    fun checkAndMark(messageId: String): Boolean {
        synchronized(seenCache) {
            if (seenCache.containsKey(messageId)) {
                duplicatesSuppressed.incrementAndGet()
                return true // Duplicate!
            }
            seenCache[messageId] = System.currentTimeMillis()
            return false // Fresh!
        }
    }

    fun contains(messageId: String): Boolean = seenCache.containsKey(messageId)

    fun clear() {
        seenCache.clear()
        duplicatesSuppressed.set(0)
    }
}
