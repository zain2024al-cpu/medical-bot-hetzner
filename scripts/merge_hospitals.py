# -*- coding: utf-8 -*-
"""
Merge all hospitals into unified database
"""

import json
import os
from datetime import datetime

def merge_hospitals():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', 'data')
    
    # Get hospitals from doctors.txt with their doctors
    doctors_by_hospital = {}
    
    doctors_file = os.path.join(data_dir, 'doctors.txt')
    with open(doctors_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split('|')
                if len(parts) >= 4:
                    doctor_name = parts[0].strip()
                    hospital_name = parts[1].strip()
                    dept_en = parts[3].strip()  # English only
                    
                    if hospital_name not in doctors_by_hospital:
                        doctors_by_hospital[hospital_name] = {}
                    
                    if dept_en not in doctors_by_hospital[hospital_name]:
                        doctors_by_hospital[hospital_name][dept_en] = []
                    
                    doctors_by_hospital[hospital_name][dept_en].append(doctor_name)
    
    # Normalize hospital names (remove duplicates)
    normalized_hospitals = {}
    name_mapping = {
        'Aster CMI Hospital, Bangalore': 'Aster CMI Hospital, Bangalore',
        'Aster RV Hospital, Bangalore': 'Aster RV Hospital, Bangalore', 
        'Aster Whitefield Hospital, Bangalore': 'Aster Whitefield Hospital, Bangalore',
    }
    
    # Merge similar names
    for hospital_name, depts in list(doctors_by_hospital.items()):
        # Check if this is a duplicate
        normalized = hospital_name
        for key, val in name_mapping.items():
            if key.lower() in hospital_name.lower() or hospital_name.lower() in key.lower():
                normalized = val
                break
        
        if normalized not in normalized_hospitals:
            normalized_hospitals[normalized] = {}
        
        # Merge departments
        for dept, docs in depts.items():
            if dept not in normalized_hospitals[normalized]:
                normalized_hospitals[normalized][dept] = []
            normalized_hospitals[normalized][dept].extend(docs)
    
    doctors_by_hospital = normalized_hospitals
    
    # Additional hospitals (no doctors yet)
    additional_hospitals = [
        'Manipal Hospital - Millers Road',
        'Manipal Hospital - Whitefield',
        'Manipal Hospital - Yeshwanthpur',
        'Manipal Hospital - Sarjapur Road',
        'Silverline Diagnostics Kalyan Nagar',
        'Gleneagles Global Hospital, Kengeri, Bangalore',
        'Zion Hospital, Kammanahalli',
        'Cura Hospital, Kammanahalli',
        'KIMS Hospital, Mahadevapura',
        'KARE Prosthetics and Orthotics, Bangalore',
        'Nueclear Diagnostics, Bangalore',
        'BLK-Max Super Specialty Hospital, Delhi',
        'Max Super Speciality Hospital, Saket, Delhi',
        'Bhagwan Mahaveer Jain Hospital - Millers Road',
        'St John Hospital, Bangalore',
        'Fortis Hospital BG Road, Bangalore',
        'Apollo Hospital, Bannerghatta, Bangalore',
    ]
    
    # Add additional hospitals with no doctors
    for h in additional_hospitals:
        if h not in doctors_by_hospital:
            doctors_by_hospital[h] = {}
    
    # Build unified database
    hospitals = []
    doctors = []
    doctor_id = 1
    hospital_id = 1
    
    for hospital_name in sorted(doctors_by_hospital.keys()):
        departments_data = doctors_by_hospital[hospital_name]
        
        hospital_record = {
            "id": hospital_id,
            "name": hospital_name,
            "name_normalized": hospital_name.lower().strip(),
            "departments": []
        }
        
        dept_id = 1
        for dept_name, doctor_names in sorted(departments_data.items()):
            department_record = {
                "id": dept_id,
                "name": dept_name,
                "doctor_count": len(doctor_names)
            }
            hospital_record["departments"].append(department_record)
            
            for doctor_name in doctor_names:
                doctor_record = {
                    "id": doctor_id,
                    "name": doctor_name,
                    "name_normalized": doctor_name.lower().strip(),
                    "hospital_id": hospital_id,
                    "hospital_name": hospital_name,
                    "department": dept_name,
                    "search_text": f"{doctor_name} {hospital_name} {dept_name}".lower()
                }
                doctors.append(doctor_record)
                doctor_id += 1
            
            dept_id += 1
        
        hospital_record["doctor_count"] = sum(d["doctor_count"] for d in hospital_record["departments"])
        hospitals.append(hospital_record)
        hospital_id += 1
    
    # Build final file
    unified_data = {
        "version": "4.0",
        "created_at": datetime.now().isoformat(),
        "description": "Unified Doctors & Hospitals Database - Merged & Deduplicated",
        "statistics": {
            "total_hospitals": len(hospitals),
            "total_doctors": len(doctors),
            "total_departments": sum(len(h["departments"]) for h in hospitals)
        },
        "hospitals": hospitals,
        "doctors": doctors
    }
    
    # Save unified file
    output_file = os.path.join(data_dir, 'doctors_unified.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unified_data, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Merged database:")
    print(f"   - Hospitals: {len(hospitals)}")
    print(f"   - Doctors: {len(doctors)}")
    print(f"   - Departments: {unified_data['statistics']['total_departments']}")
    
    return unified_data

if __name__ == '__main__':
    merge_hospitals()

