package org.setunet.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.setunet.mesh.AlertCategory
import org.setunet.mesh.AlertMessage
import org.setunet.mesh.GPSLocation

/**
 * SETU-NET Android Application UI built with Jetpack Compose (Slide 7).
 * Features 4 alert action buttons, live mesh connection status, and received emergency feed.
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SetuNetAppScreen()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetuNetAppScreen() {
    var alertsList by remember { mutableStateOf(listOf<AlertMessage>()) }
    var activePeersCount by remember { mutableIntStateOf(7) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("SETU-NET", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text("Infrastructure-Independent Disaster Mesh", fontSize = 12.sp, color = Color.Gray)
                    }
                },
                actions = {
                    Badge(containerColor = Color(0xFF10B981)) {
                        Text("$activePeersCount Peers", color = Color.White, modifier = Modifier.padding(4.dp))
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Emergency Trigger Buttons (Slide 4 Categories)
            Text("BROADCAST EMERGENCY ALERT", fontWeight = FontWeight.Bold, fontSize = 14.sp)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // SOS Button (P0)
                Button(
                    onClick = {
                        // Dispatch SOS Alert
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFEF4444)),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("SOS\n[P0]", fontWeight = FontWeight.Bold)
                }

                // Evacuation Button (P1)
                Button(
                    onClick = {
                        // Dispatch Evac Alert
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF59E0B)),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("EVAC\n[P1]", fontWeight = FontWeight.Bold)
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Troop Movement Button (P2)
                Button(
                    onClick = {
                        // Dispatch Troop Movement
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0284C7)),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("TROOP\n[P2]", fontWeight = FontWeight.Bold)
                }

                // General Button (P3)
                Button(
                    onClick = {
                        // Dispatch General Status
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981)),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("GENERAL\n[P3]", fontWeight = FontWeight.Bold)
                }
            }

            Divider()

            // Received Alerts List
            Text("RECEIVED DISASTER ALERTS", fontWeight = FontWeight.Bold, fontSize = 14.sp)
            if (alertsList.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    Text("Listening on Wi-Fi Direct / Wi-Fi Aware...", color = Color.Gray)
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(alertsList) { alert ->
                        AlertCard(alert)
                    }
                }
            }
        }
    }
}

@Composable
fun AlertCard(alert: AlertMessage) {
    Card(
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B))
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${alert.category.name} [P${alert.category.priority}]",
                    fontWeight = FontWeight.Bold,
                    color = when (alert.category) {
                        AlertCategory.SOS -> Color(0xFFEF4444)
                        AlertCategory.EVACUATION -> Color(0xFFF59E0B)
                        AlertCategory.TROOP_MOVEMENT -> Color(0xFF38BDF8)
                        AlertCategory.GENERAL -> Color(0xFF34D399)
                    }
                )
                Text("TTL: ${alert.ttl} | Hops: ${alert.hopCount}", fontSize = 12.sp, color = Color.LightGray)
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(alert.payloadText, color = Color.White, fontSize = 14.sp)
            Spacer(modifier = Modifier.height(4.dp))
            Text("Origin: ${alert.originNodeId} | GPS: ${alert.location.latitude}, ${alert.location.longitude}",
                fontSize = 11.sp, color = Color.Gray)
        }
    }
}
