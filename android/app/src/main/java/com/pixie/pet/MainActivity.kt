package com.pixie.pet

import android.Manifest
import android.app.DatePickerDialog
import android.app.TimePickerDialog
import android.content.ClipboardManager
import android.content.Intent
import android.content.SharedPreferences
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.text.format.DateFormat
import android.text.format.DateUtils
import android.util.TypedValue
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    private lateinit var prefs: Prefs
    private lateinit var status: TextView
    private lateinit var list: LinearLayout
    private lateinit var hint: TextView
    private lateinit var btnAdd: Button

    // 背景同步 / 待送清單有變動 → 重畫
    private val prefsListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key in setOf("snapshot", "outbox", "last_sync", "last_error")) render()
    }

    private val scanQr = registerForActivityResult(ScanContract()) { r ->
        r.contents?.let { pair(it) }
    }
    private val askNotify = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) toast("沒有通知權限，期限到了也無法提醒你。可以到系統設定開啟。")
        render()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        prefs = Prefs(this)
        status = findViewById(R.id.status)
        list = findViewById(R.id.todo_list)
        hint = findViewById(R.id.todo_hint)
        btnAdd = findViewById(R.id.btn_add)
        btnAdd.setOnClickListener { showAddDialog() }

        findViewById<Button>(R.id.btn_scan).setOnClickListener {
            scanQr.launch(
                ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                    .setPrompt("掃描電腦上「手機同步」視窗的 QR code")
                    .setBeepEnabled(false).setOrientationLocked(false)
            )
        }
        findViewById<Button>(R.id.btn_paste).setOnClickListener {
            val text = getSystemService(ClipboardManager::class.java).primaryClip
                ?.getItemAt(0)?.coerceToText(this)?.toString()
            if (text.isNullOrBlank()) toast("剪貼簿是空的") else pair(text)
        }
        findViewById<Button>(R.id.btn_sync).setOnClickListener { syncNow() }
        findViewById<Button>(R.id.btn_test).setOnClickListener {
            Notifications.showOverdue(this, TodoItem(999_999, "測試通知", OffsetDateTime.now()))
            if (!Notifications.canNotify(this)) toast("沒有通知權限")
        }

        if (Build.VERSION.SDK_INT >= 33 && !Notifications.canNotify(this)) {
            askNotify.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        handleDeepLink(intent)
        render()
        if (prefs.pairing != null) syncNow(quiet = true)
    }

    override fun onStart() {
        super.onStart()
        prefs.listen(prefsListener)
        render()
    }

    override fun onStop() {
        prefs.unlisten(prefsListener)
        super.onStop()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent?) {
        intent?.data?.takeIf { it.scheme == "pixie" }?.let { pair(it.toString()) }
    }

    private fun pair(text: String) {
        try {
            prefs.pairing = Pairing.parse(text)
            prefs.snapshotJson = null
            prefs.notifiedKeys = emptySet()
            prefs.outbox = emptyList()   // 換了配對，舊的待送操作不適用
            toast("配對成功")
            syncNow()
        } catch (e: IllegalArgumentException) {
            toast("配對失敗：${e.message}")
        }
    }

    private fun syncNow(quiet: Boolean = false) {
        status.text = "同步中…"
        thread {
            val r = TodoSync.run(applicationContext)
            runOnUiThread {
                render()
                if (!quiet) toast(
                    when (r) {
                        is TodoSync.Result.Ok -> "已同步 ${r.count} 件待辦"
                        TodoSync.Result.NoData -> "電腦還沒送出清單（請確認電腦端已開啟手機同步）"
                        TodoSync.Result.NotPaired -> "還沒配對"
                        is TodoSync.Result.Error -> r.message
                    }
                )
            }
        }
    }

    private fun render() {
        val p = prefs.pairing
        status.text = when {
            p == null -> "尚未配對。在電腦上右鍵小精靈 →「手機同步…」，開啟後掃描 QR code。"
            prefs.lastError != null -> "⚠️ ${prefs.lastError}"
            prefs.lastSyncMillis == 0L -> "已配對，等待第一次同步"
            else -> "已配對 · 上次同步 " + DateUtils.getRelativeTimeSpanString(
                prefs.lastSyncMillis, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS
            )
        } + if (!Notifications.canNotify(this)) "\n⚠️ 通知權限未開啟" else ""

        btnAdd.isEnabled = p != null
        list.removeAllViews()
        if (p == null) {
            hint.text = ""
            return
        }
        val todos = Outbox.visibleTodos(prefs, prefs.snapshot?.todos.orEmpty())
        val adds = Outbox.pendingAdds(prefs)
        hint.text = if (todos.isEmpty() && adds.isEmpty()) "沒有未完成的待辦，好棒！" else "點一下事項 = 完成"

        val now = OffsetDateTime.now()
        for (t in todos) {
            val d = t.deadline
            val overdue = d != null && d.isBefore(now)
            val due = when {
                d == null -> "無期限"
                overdue -> "⚠️ 已逾期（${fmtDeadline(d)}）"
                else -> "⏰ ${fmtDeadline(d)}（剩 ${remaining(now, d)}）"
            }
            addRow("☐  #${t.id}  ${t.title}", due, if (overdue) Color.parseColor("#C0392B") else null) {
                confirmComplete(t)
            }
        }
        for (a in adds) {
            val due = a.deadline?.let { "⏰ ${fmtDeadline(it)}" } ?: "無期限"
            addRow("＋  ${a.title}", "$due · 等待電腦同步（電腦開著時約 1 分鐘內）", null, null).alpha = 0.6f
        }
    }

    private fun addRow(title: String, sub: String, subColor: Int?, onClick: (() -> Unit)?): View {
        val dp = resources.displayMetrics.density
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, (10 * dp).toInt(), 0, (10 * dp).toInt())
            addView(TextView(context).apply {
                text = title
                textSize = 15f
                setTextColor(ContextCompat.getColor(context, R.color.ink))
            })
            addView(TextView(context).apply {
                text = sub
                textSize = 13f
                setPadding((26 * dp).toInt(), (2 * dp).toInt(), 0, 0)
                setTextColor(subColor ?: ContextCompat.getColor(context, R.color.muted))
            })
            if (onClick != null) {
                isClickable = true
                isFocusable = true
                val ripple = TypedValue()
                context.theme.resolveAttribute(android.R.attr.selectableItemBackground, ripple, true)
                setBackgroundResource(ripple.resourceId)
                setOnClickListener { onClick() }
            }
        }
        list.addView(row)
        return row
    }

    private fun confirmComplete(t: TodoItem) {
        AlertDialog.Builder(this)
            .setTitle("完成「${t.title}」？")
            .setMessage("會同步到電腦，電腦上的這件事也會標成完成。")
            .setPositiveButton("完成") { _, _ ->
                Outbox.complete(applicationContext, t)
                toast("「${t.title}」完成！做得好 ✨")
                render()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showAddDialog() {
        val dp = resources.displayMetrics.density
        var deadline: ZonedDateTime? = null
        val title = EditText(this).apply {
            hint = "事項名稱"
            inputType = InputType.TYPE_CLASS_TEXT
            imeOptions = EditorInfo.IME_ACTION_DONE
            setSingleLine()
        }
        val pick = Button(this).apply { text = "設定期限（可省略）" }
        val clear = Button(this, null, android.R.attr.borderlessButtonStyle).apply {
            text = "不設期限"
            visibility = View.GONE
        }
        fun refresh() {
            pick.text = deadline?.let { "期限：${fmtDeadline(it.toOffsetDateTime())}" } ?: "設定期限（可省略）"
            clear.visibility = if (deadline == null) View.GONE else View.VISIBLE
        }
        pick.setOnClickListener { pickDeadline(deadline) { deadline = it; refresh() } }
        clear.setOnClickListener { deadline = null; refresh() }

        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val pad = (20 * dp).toInt()
            setPadding(pad, (8 * dp).toInt(), pad, 0)
            addView(title)
            addView(pick)
            addView(clear)
        }
        val dialog = AlertDialog.Builder(this)
            .setTitle("新增待辦")
            .setView(box)
            .setPositiveButton("新增", null)   // 自己處理點擊：名稱空白時不關掉視窗
            .setNegativeButton("取消", null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val name = title.text.toString().trim()
                if (name.isEmpty()) {
                    title.error = "事項名稱不能是空的"
                    return@setOnClickListener
                }
                Outbox.add(applicationContext, name, deadline?.toOffsetDateTime())
                dialog.dismiss()
                toast("已記錄「$name」，電腦收到後會給它編號")
                render()
            }
        }
        dialog.show()
        title.requestFocus()
    }

    /** 先選日期再選時間；沒選過時預設一小時後的整點 */
    private fun pickDeadline(current: ZonedDateTime?, done: (ZonedDateTime) -> Unit) {
        val base = current ?: ZonedDateTime.now().plusHours(1).withMinute(0)
        DatePickerDialog(this, { _, y, m, d ->
            TimePickerDialog(this, { _, h, min ->
                done(ZonedDateTime.of(LocalDate.of(y, m + 1, d), LocalTime.of(h, min), ZoneId.systemDefault()))
            }, base.hour, base.minute, DateFormat.is24HourFormat(this)).show()
        }, base.year, base.monthValue - 1, base.dayOfMonth).apply {
            datePicker.minDate = System.currentTimeMillis() - 1000
        }.show()
    }

    private fun fmtDeadline(d: OffsetDateTime): String =
        d.atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("M/d HH:mm"))

    private fun remaining(now: OffsetDateTime, d: OffsetDateTime): String {
        val mins = ChronoUnit.MINUTES.between(now, d)
        return when {
            mins >= 1440 -> "${mins / 1440} 天"
            mins >= 60 -> "${mins / 60} 小時 ${mins % 60} 分"
            else -> "${maxOf(mins, 1)} 分"
        }
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
}
