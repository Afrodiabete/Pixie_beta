package com.pixie.pet

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

object Notifications {
    private const val CHANNEL_OVERDUE = "overdue"

    private val OVERDUE_LINES = listOf(
        "期限到囉！小精靈要生氣了，快去處理～",
        "這件事已經過期了，現在就動手吧，我在旁邊幫你加油！",
        "再拖下去，我就要一直拍翅膀吵你了喔！",
        "先做最小的一步就好，做完再休息 🌿",
    )

    fun createChannels(context: Context) {
        val channel = NotificationChannel(
            CHANNEL_OVERDUE, "待辦逾期提醒", NotificationManager.IMPORTANCE_HIGH
        ).apply { description = "待辦事項超過期限時通知" }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    fun canNotify(context: Context): Boolean =
        Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(
            context, Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED

    fun showOverdue(context: Context, todo: TodoItem) {
        if (!canNotify(context)) return
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val line = OVERDUE_LINES[Math.floorMod(todo.id, OVERDUE_LINES.size)]
        val n = NotificationCompat.Builder(context, CHANNEL_OVERDUE)
            .setSmallIcon(R.drawable.ic_notification)
            .setLargeIcon(BitmapFactory.decodeResource(context.resources, R.drawable.pixie_angry))
            .setContentTitle("「${todo.title}」逾期了")
            .setContentText(line)
            .setStyle(NotificationCompat.BigTextStyle().bigText(line))
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(todo.id, n)
        } catch (_: SecurityException) {
            // 使用者在系統設定關掉了通知權限
        }
    }

    fun cancel(context: Context, todoId: Int) {
        NotificationManagerCompat.from(context).cancel(todoId)
    }
}
