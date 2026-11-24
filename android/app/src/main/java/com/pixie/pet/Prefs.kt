package com.pixie.pet

import android.content.Context
import android.content.SharedPreferences

/** 本機儲存：配對資訊、最近一次收到的待辦清單、已提醒過的事項、待送到電腦的操作。 */
class Prefs(context: Context) {
    private val sp = context.applicationContext.getSharedPreferences("pixie", Context.MODE_PRIVATE)

    /** 背景同步改了資料時通知畫面更新（在主執行緒呼叫）；listener 要自己保留參照，否則會被回收 */
    fun listen(l: SharedPreferences.OnSharedPreferenceChangeListener) = sp.registerOnSharedPreferenceChangeListener(l)
    fun unlisten(l: SharedPreferences.OnSharedPreferenceChangeListener) = sp.unregisterOnSharedPreferenceChangeListener(l)

    var pairing: Pairing?
        get() {
            val s = sp.getString("server", null) ?: return null
            val t = sp.getString("topic", null) ?: return null
            val k = sp.getString("key", null) ?: return null
            return Pairing(s, t, k)
        }
        set(p) {
            sp.edit().putString("server", p?.server).putString("topic", p?.topic).putString("key", p?.key).apply()
        }

    var snapshotJson: String?
        get() = sp.getString("snapshot", null)
        set(v) = sp.edit().putString("snapshot", v).apply()

    val snapshot: Snapshot?
        get() = snapshotJson?.let { runCatching { Snapshot.parse(it) }.getOrNull() }

    var lastSyncMillis: Long
        get() = sp.getLong("last_sync", 0)
        set(v) = sp.edit().putLong("last_sync", v).apply()

    var lastError: String?
        get() = sp.getString("last_error", null)
        set(v) = sp.edit().putString("last_error", v).apply()

    /** 已經跳過逾期通知的 TodoItem.key，避免每 15 分鐘同步一次就重複響 */
    var notifiedKeys: Set<String>
        get() = sp.getStringSet("notified", emptySet())!!.toSet()
        set(v) = sp.edit().putStringSet("notified", v).apply()

    /** 手機上新增 / 完成、還沒被電腦確認的操作 */
    var outbox: List<PendingOp>
        get() = runCatching { PendingOp.listFromJson(sp.getString("outbox", null)) }.getOrDefault(emptyList())
        set(v) = sp.edit().putString("outbox", PendingOp.listToJson(v)).apply()

    /** 目前排了鬧鐘的待辦 id，清單變動時用來取消舊鬧鐘 */
    var scheduledIds: Set<Int>
        get() = sp.getStringSet("scheduled", emptySet())!!.mapNotNull { it.toIntOrNull() }.toSet()
        set(v) = sp.edit().putStringSet("scheduled", v.map { it.toString() }.toSet()).apply()
}
