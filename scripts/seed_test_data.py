# Seed local DB with test hospitals, departments, doctors, and patients.
# Run from project root:
#   python scripts/seed_test_data.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.session import SessionLocal
from db.models import Hospital, Department, Doctor, Patient

def seed():
    with SessionLocal() as s:
        # --- Hospitals ---
        existing = {h.name: h for h in s.query(Hospital).all()}

        hosp_data = [
            "Apollo Hospital, Bannerghatta, Bangalore",
            "Fortis Hospital, Bangalore",
            "Manipal Hospital, Bangalore",
        ]
        hospitals = {}
        for name in hosp_data:
            if name in existing:
                hospitals[name] = existing[name]
                print(f"  [skip] hospital exists: {name}")
            else:
                h = Hospital(name=name)
                s.add(h)
                s.flush()
                hospitals[name] = h
                print(f"  [add]  hospital: {name}")

        # --- Departments ---
        dept_data = {
            "Apollo Hospital, Bannerghatta, Bangalore": [
                "ENT", "Cardiology", "Orthopedics", "Oncology", "Neurology"
            ],
            "Fortis Hospital, Bangalore": [
                "ENT", "Cardiology", "General Surgery"
            ],
            "Manipal Hospital, Bangalore": [
                "ENT", "Orthopedics", "Dermatology"
            ],
        }
        departments = {}  # (hosp_name, dept_name) -> Department
        # departments.name has a UNIQUE constraint — query by name to avoid duplicates
        existing_depts_by_name = {d.name: d for d in s.query(Department).all()}
        for hosp_name, dept_names in dept_data.items():
            hosp = hospitals[hosp_name]
            for dept_name in dept_names:
                if dept_name in existing_depts_by_name:
                    departments[(hosp_name, dept_name)] = existing_depts_by_name[dept_name]
                    print(f"  [skip] dept exists: {dept_name}")
                else:
                    d = Department(name=dept_name, hospital_id=hosp.id, hospital_name=hosp_name)
                    s.add(d)
                    s.flush()
                    existing_depts_by_name[dept_name] = d
                    departments[(hosp_name, dept_name)] = d
                    print(f"  [add]  dept: {hosp_name} / {dept_name}")

        # --- Doctors ---
        doctor_data = {
            ("Apollo Hospital, Bannerghatta, Bangalore", "ENT"): [
                "Dr. Rajesh Kumar", "Dr. Priya Sharma", "Dr. Anil Mehta"
            ],
            ("Apollo Hospital, Bannerghatta, Bangalore", "Cardiology"): [
                "Dr. Sunita Rao", "Dr. Vikram Singh"
            ],
            ("Apollo Hospital, Bannerghatta, Bangalore", "Orthopedics"): [
                "Dr. Manoj Patel", "Dr. Deepa Nair"
            ],
            ("Apollo Hospital, Bannerghatta, Bangalore", "Oncology"): [
                "Dr. Kavitha Reddy", "Dr. Suresh Babu"
            ],
            ("Fortis Hospital, Bangalore", "ENT"): [
                "Dr. Ravi Verma", "Dr. Anita Joshi"
            ],
            ("Fortis Hospital, Bangalore", "Cardiology"): [
                "Dr. Mohan Das"
            ],
            ("Manipal Hospital, Bangalore", "ENT"): [
                "Dr. Lakshmi Iyer"
            ],
        }
        existing_docs = {d.full_name: d for d in s.query(Doctor).all()}
        for (hosp_name, dept_name), doc_names in doctor_data.items():
            hosp = hospitals[hosp_name]
            dept = departments.get((hosp_name, dept_name))
            for doc_name in doc_names:
                if doc_name in existing_docs:
                    print(f"  [skip] doctor exists: {doc_name}")
                else:
                    doc = Doctor(
                        name=doc_name,
                        full_name=doc_name,
                        specialty=dept_name,
                        hospital_id=hosp.id,
                        department_id=dept.id if dept else None,
                    )
                    s.add(doc)
                    print(f"  [add]  doctor: {doc_name} @ {hosp_name} / {dept_name}")

        # --- Patients ---
        patient_data = [
            {"full_name": "Ahmed Ali",       "file_number": "P001", "nationality": "Saudi"},
            {"full_name": "Mohammed Hassan", "file_number": "P002", "nationality": "Yemeni"},
            {"full_name": "Fatima Noor",     "file_number": "P003", "nationality": "Iraqi"},
            {"full_name": "Omar Abdullah",   "file_number": "P004", "nationality": "Syrian"},
            {"full_name": "Sara Khalid",     "file_number": "P005", "nationality": "Jordanian"},
        ]
        existing_patients = {p.file_number: p for p in s.query(Patient).all()}
        for pd in patient_data:
            if pd["file_number"] in existing_patients:
                print(f"  [skip] patient exists: {pd['full_name']}")
            else:
                p = Patient(**pd)
                s.add(p)
                print(f"  [add]  patient: {pd['full_name']}")

        s.commit()
        print("\nSeed complete.")

        # Summary
        print(f"\nDB summary:")
        print(f"  Hospitals:   {s.query(Hospital).count()}")
        print(f"  Departments: {s.query(Department).count()}")
        print(f"  Doctors:     {s.query(Doctor).count()}")
        print(f"  Patients:    {s.query(Patient).count()}")

if __name__ == "__main__":
    seed()
