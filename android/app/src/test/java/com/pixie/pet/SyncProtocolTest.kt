package com.pixie.pet

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.OffsetDateTime

/** 用電腦端 Python 加密出來的資料（sync_fixture.json）確認兩邊格式一致。 */
class SyncProtocolTest {
    private val fixture = JSONObject(
        javaClass.classLoader!!.getResource("sync_fixture.json")!!.readText()
    )

    @Test
    fun decryptsPayloadFromDesktop() {
        val json = SyncCrypto.decrypt(fixture.getString("payload"), fixture.getString("key"))
        val snap = Snapshot.parse(json)
        val expected = fixture.getJSONObject("expected").getJSONArray("todos")

        assertEquals(expected.length(), snap.todos.size)
        for (i in 0 until expected.length()) {
            val e = expected.getJSONObject(i)
            val t = snap.todos[i]
            assertEquals(e.getInt("id"), t.id)
            assertEquals(e.getString("title"), t.title)
            if (e.isNull("deadline")) assertNull(t.deadline)
            else assertEquals(OffsetDateTime.parse(e.getString("deadline")), t.deadline)
        }
    }

    @Test
    fun wrongKeyIsRejected() {
        val otherKey = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  // 32 個 0 byte
        assertThrows(Exception::class.java) {
            SyncCrypto.decrypt(fixture.getString("payload"), otherKey)
        }
    }

    @Test
    fun opsMessageRoundTrips() {
        val key = fixture.getString("key")
        val deadline = OffsetDateTime.parse("2026-11-06T18:00:00+08:00")
        val ops = listOf(
            PendingOp("u1", "add", "買牛奶", deadline = deadline),
            PendingOp("u2", "add", "無期限的事"),
            PendingOp("u3", "done", "交報告", todoId = 2),
        )
        val msg = JSONObject(SyncCrypto.decrypt(SyncCrypto.encrypt(PendingOp.buildMessage(ops), key), key))
        assertEquals("ops", msg.getString("kind"))
        val arr = msg.getJSONArray("ops")
        assertEquals("2026-11-06T18:00:00+08:00", arr.getJSONObject(0).getString("deadline"))
        assertTrue(arr.getJSONObject(1).isNull("deadline"))
        assertEquals(2, arr.getJSONObject(2).getInt("id"))
        assertEquals("交報告", arr.getJSONObject(2).getString("title"))
    }

    @Test
    fun pendingOpsSurviveStorage() {
        val ops = listOf(
            PendingOp("u1", "add", "買牛奶", deadline = OffsetDateTime.parse("2026-11-06T18:00:00+08:00"),
                createdMillis = 5, lastSentMillis = 7),
            PendingOp("u2", "done", "交報告", todoId = 2, createdMillis = 9),
        )
        assertEquals(ops, PendingOp.listFromJson(PendingOp.listToJson(ops)))
    }

    @Test
    fun snapshotAppliedIsOptional() {
        val old = Snapshot.parse("""{"v":1,"sent_at":"2026-11-05T10:00:00+08:00","todos":[]}""")
        assertTrue(old.applied.isEmpty())
        val new = Snapshot.parse("""{"v":1,"sent_at":"2026-11-05T10:00:00+08:00","todos":[],"applied":["a","b"]}""")
        assertEquals(setOf("a", "b"), new.applied)
    }

    @Test
    fun reusedIdGetsNewKey() {
        assertNotEquals(TodoItem(2, "舊的", null).key, TodoItem(2, "新的", null).key)
    }

    @Test
    fun parsesPairingUri() {
        val key = fixture.getString("key")
        val p = Pairing.parse("pixie://pair?server=https%3A%2F%2Fntfy.sh&topic=pixie-abc123&key=$key")
        assertEquals("https://ntfy.sh", p.server)
        assertEquals("pixie-abc123", p.topic)
        assertEquals(key, p.key)
    }

    @Test
    fun rejectsBadPairingUri() {
        assertThrows(IllegalArgumentException::class.java) { Pairing.parse("https://example.com") }
        assertThrows(IllegalArgumentException::class.java) {
            Pairing.parse("pixie://pair?server=https%3A%2F%2Fntfy.sh&topic=a/b&key=xx")
        }
    }
}
