package com.pixie.pet

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

/** 在每個待辦的期限排一個鬧鐘；時間到由 ReminderReceiver 跳通知。電腦關機、手機沒網路也照樣會響。 */
object ReminderScheduler {
    private const val EXTRA_ID = "todo_id"
    private const val EXTRA_KEY = "todo_key"

    private fun pendingIntent(context: Context, todoId: Int, key: String?, flags: Int): PendingIntent? {
        val intent = Intent(context, ReminderReceiver::class.java)
            .putExtra(EXTRA_ID, todoId)
            .putExtra(EXTRA_KEY, key)
        return PendingIntent.getBroadcast(context, todoId, intent, flags or PendingIntent.FLAG_IMMUTABLE)
    }

    fun schedule(context: Context, todo: TodoItem) {
        val at = todo.deadline?.toInstant()?.toEpochMilli() ?: return
        val am = context.getSystemService(AlarmManager::class.java)
        val pi = pendingIntent(context, todo.id, todo.key, PendingIntent.FLAG_UPDATE_CURRENT)!!
        if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
        } else {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)   // 沒有精準鬧鐘權限時，可能晚幾分鐘
        }
    }

    fun cancel(context: Context, todoId: Int) {
        val pi = pendingIntent(context, todoId, null, PendingIntent.FLAG_NO_CREATE) ?: return
        context.getSystemService(AlarmManager::class.java).cancel(pi)
        pi.cancel()
    }

    internal fun readExtras(intent: Intent): Pair<Int, String?> =
        intent.getIntExtra(EXTRA_ID, -1) to intent.getStringExtra(EXTRA_KEY)
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val (id, key) = ReminderScheduler.readExtras(intent)
        val prefs = Prefs(context)
        // 鬧鐘排下去之後，事情可能已經在電腦上完成或改期了：以最新清單為準
        val todos = Outbox.visibleTodos(prefs, prefs.snapshot?.todos.orEmpty())
        val todo = todos.firstOrNull { it.id == id && it.key == key } ?: return
        if (todo.key in prefs.notifiedKeys) return
        Notifications.showOverdue(context, todo)
        prefs.notifiedKeys = prefs.notifiedKeys + todo.key
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        TodoSync.applyStored(context)
        SyncWorker.runOnce(context)
    }
}
