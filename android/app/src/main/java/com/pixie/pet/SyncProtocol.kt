package com.pixie.pet

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.URI
import java.net.URLDecoder
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.security.SecureRandom
import java.util.Base64
import java.util.UUID
import java.util.zip.Deflater
import java.util.zip.DeflaterOutputStream
import java.util.zip.InflaterInputStream
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * 跟電腦端 pixie/sync/protocol.py 對應的格式。只用純 JDK + org.json，方便在 JVM 上做單元測試。
 *
 * payload = base64( nonce[12] + AES-256-GCM( zlib(JSON), aad="pixie-v1" ) )
 */
object SyncCrypto {
    private val AAD = "pixie-v1".toByteArray()

    fun decodeKey(key: String): ByteArray {
        val raw = Base64.getUrlDecoder().decode(key.trim())
        require(raw.size == 32) { "金鑰長度錯誤" }
        return raw
    }

    fun decrypt(payload: String, key: String): String {
        val raw = Base64.getDecoder().decode(payload.trim())
        require(raw.size > 12 + 16) { "資料太短" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(decodeKey(key), "AES"), GCMParameterSpec(128, raw, 0, 12))
        cipher.updateAAD(AAD)
        val zipped = cipher.doFinal(raw, 12, raw.size - 12)
        return InflaterInputStream(zipped.inputStream()).use { it.readBytes() }.toString(Charsets.UTF_8)
    }

    fun encrypt(json: String, key: String): String {
        val buf = ByteArrayOutputStream()
        DeflaterOutputStream(buf, Deflater(9)).use { it.write(json.toByteArray(Charsets.UTF_8)) }
        val nonce = ByteArray(12).also { SecureRandom().nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(decodeKey(key), "AES"), GCMParameterSpec(128, nonce))
        cipher.updateAAD(AAD)
        return Base64.getEncoder().encodeToString(nonce + cipher.doFinal(buf.toByteArray()))
    }
}

data class TodoItem(val id: Int, val title: String, val deadline: OffsetDateTime?) {
    /** 期限或名稱改了就算新的一筆：改期後要能再提醒一次；編號會被重用，所以也要帶名稱。開頭固定是 "id|" */
    val key: String get() = "$id|${deadline ?: "-"}|$title"
}

/** 手機上做的新增 / 完成，送到電腦前先放在待送清單（Outbox）。 */
data class PendingOp(
    val uid: String,
    val op: String,                 // "add" | "done"
    val title: String,
    val deadline: OffsetDateTime? = null,   // add 用
    val todoId: Int = 0,                    // done 用
    val createdMillis: Long = System.currentTimeMillis(),
    val lastSentMillis: Long = 0,
) {
    fun toWire(): JSONObject = JSONObject().put("uid", uid).put("op", op).put("title", title).apply {
        if (op == "add") put("deadline", deadline?.format(ISO) ?: JSONObject.NULL) else put("id", todoId)
    }

    fun toJson(): JSONObject = toWire().put("created", createdMillis).put("last_sent", lastSentMillis)

    companion object {
        private val ISO: DateTimeFormatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME   // 一定帶秒數，Python 好解析

        fun newUid(): String = UUID.randomUUID().toString().replace("-", "").take(16)

        fun fromJson(o: JSONObject) = PendingOp(
            uid = o.getString("uid"),
            op = o.getString("op"),
            title = o.getString("title"),
            deadline = if (o.isNull("deadline")) null else o.optString("deadline").takeIf { it.isNotEmpty() }
                ?.let { OffsetDateTime.parse(it) },
            todoId = o.optInt("id"),
            createdMillis = o.optLong("created"),
            lastSentMillis = o.optLong("last_sent"),
        )

        fun listToJson(ops: List<PendingOp>): String = JSONArray(ops.map { it.toJson() }).toString()

        fun listFromJson(json: String?): List<PendingOp> {
            if (json.isNullOrBlank()) return emptyList()
            val arr = JSONArray(json)
            return (0 until arr.length()).mapNotNull { runCatching { fromJson(arr.getJSONObject(it)) }.getOrNull() }
        }

        /** 手機 → 電腦的訊息內容（加密前），格式見 pixie/sync/protocol.py */
        fun buildMessage(ops: List<PendingOp>, now: OffsetDateTime = OffsetDateTime.now()): String =
            JSONObject().put("v", 1).put("kind", "ops").put("sent_at", now.format(ISO))
                .put("ops", JSONArray(ops.map { it.toWire() })).toString()
    }
}

data class Snapshot(
    val sentAt: OffsetDateTime,
    val todos: List<TodoItem>,
    val applied: Set<String> = emptySet(),   // 電腦已經處理過的手機操作 uid
) {
    companion object {
        fun parse(json: String): Snapshot {
            val o = JSONObject(json)
            val arr = o.getJSONArray("todos")
            val todos = (0 until arr.length()).map { i ->
                val t = arr.getJSONObject(i)
                val d = if (t.isNull("deadline")) null else OffsetDateTime.parse(t.getString("deadline"))
                TodoItem(t.getInt("id"), t.getString("title"), d)
            }
            val ack = o.optJSONArray("applied")
            val applied = if (ack == null) emptySet() else (0 until ack.length()).map { ack.getString(it) }.toSet()
            return Snapshot(OffsetDateTime.parse(o.getString("sent_at")), todos, applied)
        }
    }
}

data class Pairing(val server: String, val topic: String, val key: String) {
    companion object {
        private val TOPIC_RE = Regex("^[-_A-Za-z0-9]{1,64}$")

        /** 解析 pixie://pair?server=...&topic=...&key=...；格式不對丟 IllegalArgumentException */
        fun parse(text: String): Pairing {
            val uri = try { URI(text.trim()) } catch (e: Exception) { throw IllegalArgumentException("不是配對連結") }
            require(uri.scheme == "pixie" && uri.host == "pair") { "不是 Pixie 的配對連結" }
            val q = (uri.rawQuery ?: "").split("&").filter { "=" in it }.associate {
                val (k, v) = it.split("=", limit = 2)
                k to URLDecoder.decode(v, "UTF-8")
            }
            val server = q["server"] ?: throw IllegalArgumentException("缺少 server")
            val topic = q["topic"] ?: throw IllegalArgumentException("缺少 topic")
            val key = q["key"] ?: throw IllegalArgumentException("缺少 key")
            require(server.startsWith("https://") || server.startsWith("http://")) { "server 格式錯誤" }
            require(TOPIC_RE.matches(topic)) { "topic 格式錯誤" }
            SyncCrypto.decodeKey(key)
            return Pairing(server.trimEnd('/'), topic, key)
        }
    }
}
