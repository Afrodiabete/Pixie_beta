package com.pixie.pet

import android.content.Context
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.OffsetDateTime

/**
 * 手機上的新增 / 完成：先放進待送清單，送到 ntfy 的 {topic}-up 給電腦處理。
 * 電腦處理完會在下一份清單的 applied 列出 uid，這時才從待送清單移除；
 * 在那之前畫面上先照「已經生效」顯示（新增的顯示為等待同步、完成的先隱藏）。
 */
object Outbox {
    private const val RESEND_MS = 6 * 60 * 60 * 1000L        // ntfy 只保留 12 小時，電腦太久沒上線就重送
    private const val GIVE_UP_MS = 7 * 24 * 60 * 60 * 1000L  // 電腦端記得處理過的 uid 7 天，超過就放棄
    private const val MAX_OPS = 40                           // 單則訊息不能超過 4KB

    fun add(context: Context, title: String, deadline: OffsetDateTime?) =
        enqueue(context, PendingOp(PendingOp.newUid(), "add", title.trim(), deadline = deadline))

    fun complete(context: Context, todo: TodoItem) {
        enqueue(context, PendingOp(PendingOp.newUid(), "done", todo.title, todoId = todo.id))
        // 不用等電腦確認，手機上先停掉這件事的提醒
        ReminderScheduler.cancel(context, todo.id)
        Notifications.cancel(context, todo.id)
    }

    private fun enqueue(context: Context, op: PendingOp) {
        synchronized(this) {
            val prefs = Prefs(context)
            prefs.outbox = (prefs.outbox + op).takeLast(MAX_OPS)
        }
        SyncWorker.runOnce(context)                 // 立刻送出（沒網路的話 WorkManager 會等有網路再送）
        SyncWorker.runDelayed(context, 45)          // 電腦每 30 秒收一次，之後再拉一次結果
    }

    /** 把還沒送、或送了很久還沒被確認的操作送出去。會做網路請求，不能在主執行緒呼叫。 */
    fun flush(context: Context, pairing: Pairing) {
        val now = System.currentTimeMillis()
        val ops = synchronized(this) { Prefs(context).outbox }
        if (ops.none { it.lastSentMillis == 0L || now - it.lastSentMillis > RESEND_MS }) return

        // 每次都送全部未確認的，電腦用 uid 去重
        val payload = SyncCrypto.encrypt(PendingOp.buildMessage(ops), pairing.key)
        post("${pairing.server}/${pairing.topic}-up", payload)

        val sent = ops.map { it.uid }.toSet()
        synchronized(this) {
            val prefs = Prefs(context)
            prefs.outbox = prefs.outbox.map { if (it.uid in sent) it.copy(lastSentMillis = now) else it }
        }
    }

    /** 收到新清單時：電腦確認過的、或放棄的，從待送清單移除 */
    fun reconcile(context: Context, applied: Set<String>) = synchronized(this) {
        val prefs = Prefs(context)
        val now = System.currentTimeMillis()
        val kept = prefs.outbox.filter { it.uid !in applied && now - it.createdMillis < GIVE_UP_MS }
        if (kept.size != prefs.outbox.size) prefs.outbox = kept
    }

    fun pendingAdds(prefs: Prefs): List<PendingOp> = prefs.outbox.filter { it.op == "add" }

    /** 電腦傳來的清單，扣掉手機上已經按完成、但電腦還沒確認的 */
    fun visibleTodos(prefs: Prefs, todos: List<TodoItem>): List<TodoItem> {
        val done = prefs.outbox.filter { it.op == "done" }.map { it.todoId to it.title }.toSet()
        return todos.filter { (it.id to it.title) !in done }
    }

    private fun post(url: String, body: String) {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 20_000
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setRequestProperty("Firebase", "no")
        conn.setRequestProperty("Title", "pixie-ops")
        try {
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            if (conn.responseCode !in 200..299) throw IOException("HTTP ${conn.responseCode}")
        } finally {
            conn.disconnect()
        }
    }
}
