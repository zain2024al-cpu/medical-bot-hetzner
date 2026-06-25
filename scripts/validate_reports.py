"""
scripts/validate_reports.py
Proof-of-Concept validation runner:
- Builds 2 reports (Global, Patient) using real DB
- Exports PDFs, saves files
- Renders PDF pages to PNGs using PyMuPDF
- Collects metrics: pages, file size, generation time

Usage:
    python scripts/validate_reports.py

Outputs:
    outputs/validation_<timestamp>/global_report.pdf
    outputs/validation_<timestamp>/patient_report.pdf
    outputs/validation_<timestamp>/global_page_1.png ...

"""

import os
import io
import time
from datetime import datetime
from pathlib import Path
import sys

# Ensure project root is on sys.path so local packages can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.logging_config import setup_logging
from services.reporting_engine.report_engine import ReportEngine
from services.reporting_engine.filters import CompositeFilter
from services.reporting_engine.filters.date_range_filter import DateRangeFilter
from shared.report_constants import ReportType, DateRangePreset, ExportFormat
from services.export_handlers.export_factory import ExportFactory

# PyMuPDF for rendering
import fitz

# DB helpers
from db.session import get_db
from db.models import Patient


def ensure_output_dir(base_name: str = "validation") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / f"{base_name}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def save_pdf_and_metrics(buffer: io.BytesIO, out_path: Path, out_dir: Path, base_name: str):
    data = buffer.getvalue()
    out_path.write_bytes(data)
    size_kb = len(data) / 1024.0

    # load with fitz to count pages and export images to files
    doc = fitz.open(stream=data, filetype="pdf")
    page_count = doc.page_count
    page_image_paths = []
    for i in range(page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=150)
        img_path = out_dir / f"{base_name}_page_{i+1}.png"
        img_path.write_bytes(pix.tobytes("png"))
        page_image_paths.append(str(img_path))
    doc.close()

    return {
        "file_path": str(out_path),
        "size_kb": size_kb,
        "pages": page_count,
        "page_image_paths": page_image_paths,
    }


def find_any_patient_id() -> int | None:
    try:
        with get_db() as db:
            p = db.query(Patient).filter(Patient.id.isnot(None)).order_by(Patient.created_at.desc()).first()
            if p:
                return p.id
    except Exception:
        return None
    return None


def run_validation():
    setup_logging()
    out_dir = ensure_output_dir()
    results = {}

    engine = ReportEngine()

    # Global report
    filters = CompositeFilter()
    filters.add("date", DateRangeFilter(preset=DateRangePreset.LAST_MONTH))

    start = time.time()
    report = engine.build_report(ReportType.GLOBAL, filters, title="تقرير شامل - POC")
    build_time = time.time() - start

    # Export PDF
    pdf_buf = ExportFactory.export(report_data=report, format=ExportFormat.PDF)

    global_pdf_path = out_dir / "global_report.pdf"
    metrics = save_pdf_and_metrics(pdf_buf, global_pdf_path, out_dir, "global")
    metrics.update({"build_time_s": build_time, "engine_report_stats": report.get_generation_stats()})
    results['global'] = metrics

    # Patient report
    patient_id = find_any_patient_id()
    if patient_id is None:
        print("⚠️ لم يتم العثور على أي مريض في قاعدة البيانات. تم تخطي تقرير المريض.")
    else:
        filters2 = CompositeFilter()
        filters2.add("date", DateRangeFilter(preset=DateRangePreset.LAST_3_MONTHS))
        # Add patient filter dynamically if available
        try:
            from services.reporting_engine.filters.patient_filter import PatientFilter
            filters2.add("patient", PatientFilter(patient_id=patient_id))
        except Exception:
            pass

        start = time.time()
        report2 = engine.build_report(ReportType.PATIENT, filters2, title=f"تقرير مريض - {patient_id}", patient_id=patient_id)
        build_time2 = time.time() - start

        pdf_buf2 = ExportFactory.export(report_data=report2, format=ExportFormat.PDF)
        patient_pdf_path = out_dir / f"patient_report_{patient_id}.pdf"
        metrics2 = save_pdf_and_metrics(pdf_buf2, patient_pdf_path, out_dir, f"patient_{patient_id}")
        metrics2.update({"build_time_s": build_time2, "engine_report_stats": report2.get_generation_stats()})
        results['patient'] = metrics2

    # Save metadata
    import json
    with open(out_dir / "validation_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # page images already saved by save_pdf_and_metrics

    print("✅ Validation complete. Outputs:")
    print(out_dir)
    return results


if __name__ == '__main__':
    run_validation()
