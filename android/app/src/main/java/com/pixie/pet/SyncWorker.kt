package com.pixie.pet

import android.app.Application
import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/** 背景定期同步。Android 限制週期性工作最短 15 分鐘。 */
class SyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result = when (val r = TodoSync.run(applicationContext)) {
        is TodoSync.Result.Error -> if (r.retryable) Result.retry() else Result.failure()
        else -> Result.success()
    }

    companion object {
        private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        fun schedulePeriodic(context: Context) {
            val req = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(network).build()
            WorkManager.getInstance(context)
                .enqueueUniquePeriodicWork("sync", ExistingPeriodicWorkPolicy.KEEP, req)
        }

        fun runOnce(context: Context) {
            val req = OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(network).build()
            WorkManager.getInstance(context).enqueueUniqueWork("sync-now", ExistingWorkPolicy.REPLACE, req)
        }

        /** 幾秒後再同步一次（手機送出操作後，等電腦處理完再拉結果） */
        fun runDelayed(context: Context, seconds: Long) {
            val req = OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(network)
                .setInitialDelay(seconds, TimeUnit.SECONDS).build()
            WorkManager.getInstance(context).enqueueUniqueWork("sync-later", ExistingWorkPolicy.REPLACE, req)
        }
    }
}

class PixieApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifications.createChannels(this)
        SyncWorker.schedulePeriodic(this)
    }
}
