package org.setunet.mesh

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase

/**
 * Android Room (SQLite) Database for Local Alert History & ACKs (Slide 7).
 */
@Entity(tableName = "alerts")
data class AlertEntity(
    @PrimaryKey val messageId: String,
    val category: String,
    val priority: Int,
    val originNodeId: String,
    val payloadText: String,
    val latitude: Double,
    val longitude: Double,
    val timestamp: Double,
    val ttl: Int,
    val hopCount: Int,
    val signature: String,
    val receivedAt: Long = System.currentTimeMillis()
)

@Entity(tableName = "acknowledgements")
data class AckEntity(
    @PrimaryKey val ackId: String,
    val originalMessageId: String,
    val alertCategory: String,
    val ackNodeId: String,
    val hopsToNode: Int,
    val latencyMs: Double,
    val timestamp: Long = System.currentTimeMillis()
)

@Dao
interface SetuNetDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAlert(alert: AlertEntity)

    @Query("SELECT * FROM alerts ORDER BY timestamp DESC")
    suspend fun getAllAlerts(): List<AlertEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAck(ack: AckEntity)

    @Query("SELECT * FROM acknowledgements WHERE originalMessageId = :msgId")
    suspend fun getAcksForAlert(msgId: String): List<AckEntity>
}

@Database(entities = [AlertEntity::class, AckEntity::class], version = 1)
abstract class SetuNetDatabase : RoomDatabase() {
    abstract fun dao(): SetuNetDao
}
