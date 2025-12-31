# =============================
# managers.py
# State Data Managers - فصل البيانات
# =============================


class PatientDataManager:
    """مدير بيانات المرضى - منفصل تماماً عن الأطباء"""

    @staticmethod
    def clear_patient_data(context):
        """تنظيف بيانات المريض عند الرجوع"""
        report_tmp = context.user_data.get("report_tmp", {})
        patient_keys = ["patient_name", "patient_id", "patient_search_query"]
        for key in patient_keys:
            report_tmp.pop(key, None)

    @staticmethod
    def get_patient_data(context):
        """الحصول على بيانات المريض"""
        report_tmp = context.user_data.get("report_tmp", {})
        return {
            "patient_name": report_tmp.get("patient_name"),
            "patient_id": report_tmp.get("patient_id"),
        }


class DoctorDataManager:
    """مدير بيانات الأطباء - منفصل تماماً عن المرضى"""

    @staticmethod
    def clear_doctor_data(context):
        """تنظيف بيانات الطبيب عند الرجوع"""
        report_tmp = context.user_data.get("report_tmp", {})
        doctor_keys = ["doctor_name", "doctor_id", "doctor_manual_mode", "doctor_search_query"]
        for key in doctor_keys:
            report_tmp.pop(key, None)

    @staticmethod
    def get_doctor_data(context):
        """الحصول على بيانات الطبيب"""
        report_tmp = context.user_data.get("report_tmp", {})
        return {
            "doctor_name": report_tmp.get("doctor_name"),
            "doctor_id": report_tmp.get("doctor_id"),
            "manual_mode": report_tmp.get("doctor_manual_mode", False),
        }


class DepartmentDataManager:
    """مدير بيانات الأقسام - منفصل تماماً عن المرضى والأطباء"""

    @staticmethod
    def clear_department_data(context, full_clear=False):
        """تنظيف بيانات القسم عند الرجوع

        Args:
            full_clear: إذا True، ينظف جميع بيانات القسم (للرجوع إلى شاشة الأقسام)
                       إذا False، ينظف فقط بيانات الاختيار الحالي (للرجوع إلى شاشة الطبيب)
        """
        report_tmp = context.user_data.get("report_tmp", {})

        if full_clear:
            # تنظيف كامل للرجوع إلى شاشة الأقسام
            department_keys = ["department_name", "departments_search", "main_department", "subdepartments_list"]
            for key in department_keys:
                report_tmp.pop(key, None)
        else:
            # تنظيف جزئي للرجوع إلى شاشة الطبيب (الاحتفاظ بالمستشفى والقسم الأساسي)
            partial_keys = ["departments_search", "main_department", "subdepartments_list"]
            for key in partial_keys:
                report_tmp.pop(key, None)
            # الاحتفاظ بـ department_name و hospital_name للبحث عن الأطباء

    @staticmethod
    def get_department_data(context):
        """الحصول على بيانات القسم"""
        report_tmp = context.user_data.get("report_tmp", {})
        return {
            "department_name": report_tmp.get("department_name"),
            "main_department": report_tmp.get("main_department"),
        }






