package com.pixie.pet

import android.content.Context
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.OffsetDateTime

/** 先送出手機上的新增/完成 → 從 ntfy 拉最新清單 → 解密 → 存起來 → 排鬧鐘、補發逾期通知、收掉已完成的通知。 */
object TodoSync {

    sealed class Result {
        data class Ok(val count: Int) : Result()
        object NotPaired : Result()
        object NoData : Result()                       // ntfy 上沒有訊息（電腦超過 12 小時沒上線）
        data class Error(val message: String, val retryable: Boolean) : Result()
    }

    /** 會做網路請求，不能在主執行緒呼叫 */
    @Synchronized
    fun run(context: Context): Result {
        val prefs = Prefs(context)
        val pairing = prefs.pairing ?: return Result.NotPaired
        val result = try {
            Outbox.flush(context, pairing)
            val payload = fetchLatest(pairing) ?: return Result.NoData.also { prefs.lastError = null }
            val json = SyncCrypto.decrypt(payload, pairing.key)
            val snapshot = Snapshot.parse(json)
            apply(context, json, snapshot)
            Result.Ok(snapshot.todos.size)
        } catch (e: IOException) {
            Result.Error("網路錯誤：${e.message}", retryable = true)
        } catch (e: Exception) {
            Result.Error("無法解讀同步資料（金鑰不符？請重新配對）", retryable = false)
        }
        when (result) {
            is Result.Ok -> { prefs.lastSyncMillis = System.currentTimeMillis(); prefs.lastError = null }
            is Result.Error -> prefs.lastError = result.message
            else -> {}
        }
        return result
    }

    /** 不連網，用手機上存的清單重排鬧鐘（開機後用） */
    fun applyStored(context: Context) {
        val prefs = Prefs(context)
        val json = prefs.snapshotJson ?: return
        val snapshot = prefs.snapshot ?: return
        apply(context, json, snapshot)
    }

    @Synchronized
    private fun apply(context: Context, json: String, snapshot: Snapshot) {
        val prefs = Prefs(context)
        // 只接受比手上更新的清單（避免網路延遲送來舊資料把新資料蓋掉）
        val current = prefs.snapshot
        if (current != null && snapshot.sentAt.isBefore(current.sentAt)) return
        prefs.snapshotJson = json
        Outbox.reconcile(context, snapshot.applied)

        val now = OffsetDateTime.now()
        val todos = Outbox.visibleTodos(prefs, snapshot.todos)   // 手機上已按完成的不再提醒
        val keys = todos.map { it.key }.toSet()

        // 已完成 / 刪除的：取消鬧鐘、收掉通知
        for (old in prefs.scheduledIds) ReminderScheduler.cancel(context, old)
        // 通知對應的 key 不在新清單 = 已完成、刪除或改期 → 收掉舊通知（改期後若又逾期會重新通知）
        prefs.notifiedKeys.filter { it !in keys }.forEach { k ->
            k.substringBefore('|').toIntOrNull()?.let { Notifications.cancel(context, it) }
        }
        var notified = prefs.notifiedKeys.filter { it in keys }.toSet()

        val scheduled = mutableSetOf<Int>()
        for (t in todos) {
            val d = t.deadline ?: continue
            if (d.isAfter(now)) {
                ReminderScheduler.schedule(context, t)
                scheduled += t.id
            } else if (t.key !in notified) {
                Notifications.showOverdue(context, t)   // 同步時才發現已逾期（例如手機剛開機）
                notified = notified + t.key
            }
        }
        prefs.scheduledIds = scheduled
        prefs.notifiedKeys = notified
    }

    private fun fetchLatest(p: Pairing): String? {
        val conn = URL("${p.server}/${p.topic}/json?poll=1").openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 20_000
        try {
            if (conn.responseCode !in 200..299) throw IOException("HTTP ${conn.responseCode}")
            return conn.inputStream.bufferedReader().readLines()
                .mapNotNull { line -> runCatching { JSONObject(line) }.getOrNull() }
                .filter { it.optString("event") == "message" }
                .maxByOrNull { it.optLong("time") }
                ?.optString("message")
        } finally {
            conn.disconnect()
        }
    }
}
