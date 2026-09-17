# ================================================
# db/maintenance.py
# 🔹 Database Maintenance & Strengthening Tools
# ================================================

import logging
import os
import time
from datetime import datetime
from sqlalchemy import text
from db.session import engine, DATABASE_PATH, get_db

logger = logging.getLogger(__name__)


def _migrate_column(conn, table: str, column: str, sql_type: str) -> None:
    """يفحص عموداً واحداً ويضيفه إن كان ناقصاً، مع طباعة صريحة في الـ log
    لكل حالة (موجود مسبقاً / أُضيف بنجاح / فشلت إضافته) — بمعزل تام عن أي
    عمود آخر، حتى تكون نتيجة كل عمود مرئية دائماً بدل تحذير عام واحد يُخفي
    التفاصيل."""
    try:
        existing_cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
    except Exception as exc:
        logger.error(f"❌ Migration: failed to read schema for table '{table}': {exc}")
        return

    if column in existing_cols:
        logger.info(f"✅ Migration: column '{table}.{column}' already exists — skipping.")
        return

    logger.info(f"⚠️ Migration: column '{table}.{column}' NOT FOUND — adding it now...")
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
        conn.commit()
        logger.info(f"✅ Migration: added column '{table}.{column}' successfully.")
    except Exception as exc:
        logger.error(f"❌ Migration: FAILED to add column '{table}.{column}': {exc}", exc_info=True)


def _ensure_indexes(conn) -> None:
    """يبني أي فهرس يعرّفه النموذج ولا يحمله الملف.

    ⚠️ **`ALTER TABLE ADD COLUMN` لا يبني فهرساً أبداً**، ولو كان العمود
    مُعرَّفاً بـ`index=True`. فكل عمود أُضيف بترحيل هنا بقي بلا فهرسه —
    `res_persons.frozen_at` و`patients.archived_at` وغيرهما، وهي أعمدة
    تُرشَّح بها استعلامات يومية. لا يسقط شيء، لكنه بطءٌ صامت يزداد مع
    نموّ الجداول ولا يظهر في أي سجلّ.

    ⚠️ **ولا يُرفَع أي فشل**: اسم فهرس قد يكون محجوزاً بفهرس جدولٍ آخر
    (يحدث بعد `ALTER TABLE ... RENAME` الذي ينقل فهارس الجدول معه).
    تخطّي واحد لا يمنع بناء البقية.
    """
    from db.models import Base

    try:
        tables = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table'")).fetchall()}
        have = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'index'")).fetchall()}
    except Exception as exc:
        logger.error(f"❌ Indexes: failed to read schema: {exc}")
        return

    built = 0
    for t in Base.metadata.sorted_tables:
        if t.name not in tables:
            continue
        cols = {r[1] for r in conn.execute(text(f"PRAGMA table_info({t.name})")).fetchall()}
        # ⚠️ فهارس **هذا الجدول** لا الأسماء في القاعدة كلها: الاسم قد
        # يكون معلَّقاً بجدول آخر (بعد RENAME) فيبدو موجوداً وهو ليس له.
        own = {r[1] for r in conn.execute(text(f"PRAGMA index_list({t.name})")).fetchall()}
        for ix in t.indexes:
            if ix.name in own:
                continue
            if ix.name in have:
                logger.warning(
                    f"⚠️ Indexes: name '{ix.name}' is taken by another table — "
                    f"'{t.name}' stays without it.")
                continue
            # فهرس على عمود لم يُضَف بعد يفشل — يُترَك لدورة قادمة
            if {c.name for c in ix.columns} - cols:
                continue
            try:
                ix.create(bind=conn, checkfirst=True)
                conn.commit()
                built += 1
                logger.info(f"✅ Indexes: built '{ix.name}' on '{t.name}'.")
            except Exception as exc:
                logger.warning(f"⚠️ Indexes: skipped '{ix.name}' on '{t.name}': {exc}")
    if built:
        logger.info(f"🔎 Indexes: built {built} missing index(es).")


class DatabaseMaintenance:
    """
    Tools to strengthen, repair, and maintain the SQLite database.
    """
    
    @staticmethod
    def run_maintenance():
        """
        Run full database maintenance routine.
        1. Check integrity
        2. Optimize (Vacuum + Analyze)
        3. Verify WAL mode
        """
        logger.info("🔧 Starting database maintenance...")
        
        results = {
            "integrity_check": False,
            "vacuum": False,
            "wal_mode": False,
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. Integrity Check
        try:
            with engine.connect() as conn:
                logger.info("🔍 Running PRAGMA integrity_check...")
                result = conn.execute(text("PRAGMA integrity_check")).scalar()
                
                if result == "ok":
                    logger.info("✅ Database integrity check passed.")
                    results["integrity_check"] = True
                else:
                    logger.error(f"❌ Database integrity check FAILED: {result}")
                    results["integrity_check_error"] = result
        except Exception as e:
            logger.error(f"❌ Error during integrity check: {e}")
            results["error"] = str(e)

        # 2. Optimize (Vacuum & Analyze)
        # Note: VACUUM requires no active transactions.
        # We try to do it, but if it fails due to locks, we log it.
        try:
            # We need a raw connection for VACUUM usually, or autocommit mode
            with engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                logger.info("🧹 Running VACUUM...")
                conn.execute(text("VACUUM"))
                
                logger.info("📊 Running ANALYZE...")
                conn.execute(text("ANALYZE"))
                
                logger.info("✅ Database optimized.")
                results["vacuum"] = True
        except Exception as e:
            logger.warning(f"⚠️ Optimization skipped (database might be busy): {e}")
            results["vacuum_error"] = str(e)

        # 3. Verify WAL Mode
        try:
            with engine.connect() as conn:
                mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                if mode.upper() == "WAL":
                    logger.info("✅ WAL mode is active.")
                    results["wal_mode"] = True
                else:
                    logger.warning(f"⚠️ WAL mode is NOT active (Current: {mode}). Attempting to enable...")
                    conn.execute(text("PRAGMA journal_mode=WAL"))
                    new_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                    if new_mode.upper() == "WAL":
                        logger.info("✅ WAL mode enabled successfully.")
                        results["wal_mode"] = True
                    else:
                        logger.error(f"❌ Failed to enable WAL mode. Current: {new_mode}")
        except Exception as e:
            logger.error(f"❌ Error checking WAL mode: {e}")

        logger.info("✅ Database maintenance completed.")
        return results

    @staticmethod
    def check_db_health_startup():
        """
        Run a quick health check on startup.
        If database is corrupted, try to restore from backup (if implemented) 
        or at least warn loudly.
        """
        logger.info("🏥 Running startup database health check...")
        try:
            with engine.connect() as conn:
                # Quick integrity check (quick_check is faster but less thorough)
                # Note: 'PRAGMA quick_check' is available in newer SQLite versions
                try:
                    check = conn.execute(text("PRAGMA quick_check")).scalar()
                except Exception:
                    # Fallback to full check if quick_check not supported
                    check = conn.execute(text("PRAGMA integrity_check")).scalar()
                
                # ── migrate: add new columns if missing ──
                # ✅ كل عمود يُفحص ويُضاف بشكل مستقل تماماً داخل try/except خاص
                # به (وليس كتلة واحدة مشتركة) — حتى لو فشل عمود واحد لأي سبب،
                # بقية الأعمدة تُفحص وتُضاف بشكل طبيعي، وكل نتيجة (موجود/أُضيف/
                # فشل) تُطبع صراحةً في الـ log بدل الاكتفاء بتحذير عام واحد عند
                # أي استثناء يُخفي أي عمود تحديداً تأثّر.
                logger.info(f"🔎 Migration check starting for DB: {DATABASE_PATH}")
                _migrate_column(conn, "reports", "has_paper_report", "INTEGER")
                _migrate_column(conn, "reports", "no_paper_report_reason", "TEXT")
                # ✅ نوع ظهور المريض — عمود جديد في patients. كل الصفوف
                # الحالية تحصل على NULL تلقائياً (= general = يظهر للجميع)،
                # فلا يختفي أي مريض ولا يتغيّر أي سلوك قائم.
                _migrate_column(conn, "patients", "patient_type", "VARCHAR(30)")
                # ✅ تتبع الإكمال الجزئي للتقارير المعلقة (عدة فحوصات لكل
                # تقرير). الصفوف القديمة تحصل على NULL — تُعامَل كـ"فحص
                # واحد متوقَّع" في كود القراءة، فلا يتغيّر سلوكها.
                _migrate_column(conn, "pending_reports", "expected_count", "INTEGER")
                _migrate_column(conn, "pending_reports", "uploaded_count", "INTEGER")
                _migrate_column(conn, "pending_reports", "uploaded_before_close", "INTEGER")
                _migrate_column(conn, "res_issuance_history", "reminder_date", "VARCHAR(50)")
                _migrate_column(conn, "res_persons", "frozen_at", "DATETIME")
                _migrate_column(conn, "res_persons", "frozen_by", "INTEGER")
                # ✅ تصنيف مسير الصيدلية عند الطباعة (A/B/C) — الصفوف القديمة
                # تحصل على NULL، تُعامَل كـ"A" افتراضياً في كود القراءة.
                _migrate_column(conn, "pharmacy_financial_records", "manifest_type", "VARCHAR(5)")
                # ✅ حقول وحدة المناظير — أعمدة جديدة في reports. الصفوف
                # الحالية تحصل على NULL تلقائياً (لا تخص مسار المناظير)، فلا
                # يتغيّر أي تقرير قائم ولا أي مسار آخر.
                _migrate_column(conn, "reports", "endoscopy_type", "VARCHAR(100)")
                _migrate_column(conn, "reports", "endoscopy_result", "TEXT")
                _migrate_column(conn, "reports", "endoscopy_procedures", "TEXT")
                # ✅ لقطة خطة العلاج (جلسات كيماوي/موجه/مناعي/غسيل كلى) — انظر
                # التعليق على العمود في db/models.py. جداول TreatmentPlan/
                # TreatmentPlanChangeLog نفسها جداول جديدة بالكامل فتُنشَأ
                # تلقائياً عبر Base.metadata.create_all عند بدء التشغيل، بلا
                # حاجة لأي migration صريح هنا.
                _migrate_column(conn, "reports", "treatment_plan_summary", "TEXT")
                # ✅ حقول 🫁 معاملة الزراعة (قسم "الرعاية الصحية - تشناي" فقط)
                # — أعمدة جديدة في reports. الصفوف الحالية تحصل على NULL
                # تلقائياً (لا تخص مسار الزراعة)، فلا يتغيّر أي تقرير قائم.
                _migrate_column(conn, "reports", "transplant_type", "VARCHAR(100)")
                _migrate_column(conn, "reports", "transplant_parties", "TEXT")
                _migrate_column(conn, "reports", "transplant_details", "TEXT")
                # ✅ أعمدة مستقلة لحقول أنواع الإجراءات القديمة (عملية/خروج/
                # ترقيد/طوارئ/علاج طبيعي/أجهزة تعويضية/استشارة مع قرار عملية)
                # — كانت مدموجة في نص doctor_decision واحد فقط، انظر التعليق
                # في db/models.py::Report لتفصيل السبب. الصفوف الحالية تحصل
                # على NULL — سكربت backfill منفصل (scripts/backfill_legacy_
                # report_fields.py) يملأ التقارير القديمة من doctor_decision.
                _migrate_column(conn, "reports", "operation_details", "TEXT")
                _migrate_column(conn, "reports", "operation_name_en", "VARCHAR(255)")
                _migrate_column(conn, "reports", "success_rate", "VARCHAR(50)")
                _migrate_column(conn, "reports", "benefit_rate", "VARCHAR(50)")
                _migrate_column(conn, "reports", "admission_reason", "TEXT")
                _migrate_column(conn, "reports", "discharge_type", "VARCHAR(100)")
                _migrate_column(conn, "reports", "admission_summary", "TEXT")
                _migrate_column(conn, "reports", "therapy_details", "TEXT")
                _migrate_column(conn, "reports", "device_details", "TEXT")
                _migrate_column(conn, "reports", "admission_notes", "TEXT")
                _migrate_column(conn, "reports", "admission_type", "VARCHAR(100)")

                # ✅ الخدمات العامة — الواصلون:
                #  - المختص أصبح لكل مريض (كان عموداً واحداً على الدفعة).
                #  - visa_expiry للمرافق لم يكن له عمود إطلاقاً، فكان التدفق
                #    يكتبه في residence_expiry بالخطأ (يفقد تاريخ الفيزا
                #    ويُفسد تاريخ الإقامة معاً).
                _migrate_column(conn, "gs_arrival_patients", "specialist_id", "VARCHAR(50)")
                _migrate_column(conn, "gs_arrival_patients", "specialist_label", "VARCHAR(255)")
                _migrate_column(conn, "gs_arrival_companions", "visa_expiry", "VARCHAR(50)")
                # ✅ ربط المرافق بمريضه — لم يكن موجوداً إطلاقاً رغم أن الأدمن
                # يُدخل المريض ومرافقيه في تدفق واحد.
                _migrate_column(conn, "patients", "companion_of_id", "INTEGER")
                # ✅ daily_patients لم يكن له أي ترحيل إطلاقاً، وقاعدة السيرفر
                # تسبق هذه الأعمدة. `s.query(DailyPatient)` يختار كل أعمدة
                # الموديل، فكان يسقط بـ`no such column: daily_patients.
                # translator_id` ⇒ شاشة «إدارة المرضى اليوميين» معطّلة كلياً.
                # لا يظهر محلياً لأن القاعدة المحلية تُبنى من الموديل.
                _migrate_column(conn, "daily_patients", "translator_id", "INTEGER")
                _migrate_column(conn, "daily_patients", "translator_name", "VARCHAR(255)")
                _migrate_column(conn, "daily_patients", "patient_count", "INTEGER")
                # ✅ رقم الجلسة ضمن الدورة الحالية — العلاج الكيماوي فقط،
                # منفصل عن current_session (رقم الدورة نفسها).
                _migrate_column(conn, "reports", "chemo_session_number", "INTEGER")
                # ✅ اسم أضافه الإداري عبر "مريض جديد مع مرافقين" ولم يُستخدَم
                # بعد في تقرير وصول فعلي — أساس شاشة "📋 الأسماء المعلّقة"
                # الجديدة في الخدمات العامة.
                _migrate_column(conn, "patients", "pending_arrival", "BOOLEAN")
                # ✅ أرشفة المرضى المسافرين: NULL = نشط (كل الصفوف الحالية)،
                # وتاريخ = مسافر فيختفي من قوائم اختيار المرضى مع بقاء بياناته
                # التاريخية كاملة للتقارير والإحصائيات.
                _migrate_column(conn, "patients", "archived_at", "DATETIME")
                # ✅ مريض قديم أُدخِل يدوياً لبوتَي الخدمات/الإقامة عبر شاشة
                # "🏠 الحالات الموجودة" (لم يمرّ بتدفق الوصول).
                _migrate_column(conn, "patients", "gs_onboarded_at", "DATETIME")
                # ✅ تاريخ آخر إصدار للإقامة — لمعالجة المرضى القدامى
                # ("🏠 معلّقات من الحالات السابقة" في وحدة الإقامة).
                _migrate_column(conn, "res_persons", "last_issue_date", "VARCHAR(50)")
                _migrate_column(conn, "reports", "group_chat_id", "VARCHAR(64)")
                # ✅ **نفس عطب `daily_patients` أعلاه، في ثلاثة جداول أخرى**:
                # الموديل يعرّف `translator_id` وقاعدة السيرفر لا تحمله، وأي
                # `s.query(Model)` يختار كل أعمدة الموديل فيسقط بـ
                # `no such column`. انكشفت بالصدفة عند دمج هويّة مترجم —
                # فالثلاثة كانت تسقط صامتةً منذ إنشائها:
                #   • followup_tracking ⇒ مهمة استخراج المتابعات (٩ مساءً)
                #     تسقط كل ليلة ويُبتلَع خطؤها في `except` — ولهذا بقي
                #     الجدول فارغاً دائماً حتى وُثِّق فراغه في تعليقات أخرى
                #     كأنه أمر طبيعي (services/tomorrow_appointments.py).
                #   • translator_notifications وtranslator_schedules ⇒ أي قراءة.
                # ولا يظهر شيء من هذا محلياً: القاعدة المحلية تُبنى من الموديل.
                _migrate_column(conn, "followup_tracking", "translator_id", "INTEGER")
                _migrate_column(conn, "followup_tracking", "translator_name", "VARCHAR(255)")
                _migrate_column(conn, "translator_notifications", "translator_id", "INTEGER")
                _migrate_column(conn, "translator_notifications", "translator_name", "VARCHAR(255)")
                _migrate_column(conn, "translator_schedules", "translator_id", "INTEGER")
                _migrate_column(conn, "translator_schedules", "translator_name", "VARCHAR(255)")
                # ✅ وبقيّة أعمدة الجداول نفسها — كشفها `scripts/audit_schema.py`
                # بعد إصلاح عمود المترجم: الانحراف لم يكن عموداً واحداً بل
                # جداول وُلدت بأشكال أخرى كاملة. ⚠️ `notification_text` تحديداً
                # يُكتَب فيه زر «تذكير للمترجمين المتأخرين» — فبدونه يسقط
                # الإدراج نفسه بعد أن صار الزر يعمل.
                _migrate_column(conn, "admin_notes", "admin_id", "INTEGER")
                _migrate_column(conn, "admin_notes", "admin_name", "VARCHAR(255)")
                _migrate_column(conn, "admin_notes", "target_user_id", "INTEGER")
                _migrate_column(conn, "admin_notes", "updated_at", "DATETIME")
                _migrate_column(conn, "followup_tracking", "patient_name", "VARCHAR(255)")
                _migrate_column(conn, "followup_tracking", "patient_phone", "VARCHAR(50)")
                _migrate_column(conn, "followup_tracking", "department", "VARCHAR(255)")
                _migrate_column(conn, "followup_tracking", "status", "VARCHAR(50)")
                _migrate_column(conn, "translator_notifications", "notification_text", "TEXT")
                _migrate_column(conn, "translator_notifications", "is_read", "BOOLEAN")
                _migrate_column(conn, "translator_schedules", "schedule_date", "DATETIME")
                _migrate_column(conn, "translator_schedules", "shift_start", "VARCHAR(50)")
                _migrate_column(conn, "translator_schedules", "shift_end", "VARCHAR(50)")
                _migrate_column(conn, "translator_schedules", "status", "VARCHAR(50)")
                _migrate_column(conn, "translator_schedules", "updated_at", "DATETIME")
                # ⚠️ `user_activity` **لا يُعالَج هنا**: ينقصه `id` نفسه —
                # المفتاح الأساسي، ولا يُضاف بـALTER في sqlite. الجدول على
                # الخادم وُلد من تعريف آخر تماماً (services/user_tracker.py
                # المحذوف)، فعلاجه إعادة بناء لا إضافة عمود:
                # scripts/rebuild_user_activity.py
                logger.info("🔎 Migration check finished.")
                # الأعمدة المُضافة أعلاه تصل بلا فهارسها — تُبنى هنا.
                _ensure_indexes(conn)

                if check == "ok":
                    logger.info("✅ Database is healthy.")
                    return True
                else:
                    logger.critical(f"❌ DATABASE CORRUPTION DETECTED: {check}")
                    # Here we could trigger a restore process
                    return False
        except Exception as e:
            logger.critical(f"❌ Failed to access database on startup: {e}")
            return False

def run_scheduled_maintenance(context=None):
    """
    Function to be called by the job queue.
    النسخ الاحتياطي اليومي/الساعي يتم محلياً عبر services/render_backup.py
    (وسكريبتات cron المستقلة على السيرفر) — لا يوجد استخدام لـGoogle Cloud
    Storage في هذا النشر، فلا داعي لمحاولة نسخة سحابية هنا.
    """
    try:
        DatabaseMaintenance.run_maintenance()
    except Exception as e:
        logger.error(f"❌ Scheduled maintenance failed: {e}")
