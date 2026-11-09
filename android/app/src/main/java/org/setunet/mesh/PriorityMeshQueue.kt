package org.setunet.mesh

import java.util.concurrent.PriorityBlockingQueue
import java.util.concurrent.atomic.AtomicInteger

/**
 * Thread-safe Priority Mesh Queue with preemption for Android (Slides 4, 6, 7 & 8).
 * Ensures that urgent SOS alerts jump directly ahead of lower-priority messages.
 */
class PriorityMeshQueue(capacity: Int = 500) {

    private val queue = PriorityBlockingQueue<AlertMessage>(capacity)
    val preemptionsCount = AtomicInteger(0)

    fun enqueue(alert: AlertMessage) {
        // Preemption check: if SOS arrives and queue contains lower priority items
        if (alert.category == AlertCategory.SOS && !queue.isEmpty()) {
            val hasLowerPriority = queue.any { it.category.priority > AlertCategory.SOS.priority }
            if (hasLowerPriority) {
                preemptionsCount.incrementAndGet()
            }
        }
        queue.put(alert)
    }

    fun poll(): AlertMessage? = queue.poll()

    fun take(): AlertMessage = queue.take()

    fun peek(): AlertMessage? = queue.peek()

    fun size(): Int = queue.size

    fun isEmpty(): Boolean = queue.isEmpty()

    fun snapshot(): List<AlertMessage> = queue.toList().sorted()
}
