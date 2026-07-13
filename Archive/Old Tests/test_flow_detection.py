#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اختبار تحديد نوع المسار (flow_type detection)
"""

def test_flow_type_detection():
    """اختبار منطق تحديد نوع المسار"""
    
    # Constants
    FOLLOWUP_COMPLAINT = 16
    FOLLOWUP_DIAGNOSIS = 17
    FOLLOWUP_DECISION = 18
    FOLLOWUP_ROOM_FLOOR = 19
    FOLLOWUP_DATE_TIME = 19  # Wait, this might be the problem!
    FOLLOWUP_REASON = 20
    FOLLOWUP_TRANSLATOR = 21
    
    print("="*80)
    print("🔍 اختبار تحديد نوع المسار")
    print("="*80)
    
    # سيناريوهات مختلفة
    scenarios = [
        {
            'name': 'مراجعة دورية واضحة',
            'medical_action': 'مراجعة / عودة دورية',
            'current_flow': 'periodic_followup',
            'current_state': FOLLOWUP_DIAGNOSIS,
            'room_number': None,
            'expected_flow': 'periodic_followup'
        },
        {
            'name': 'متابعة رقود واضحة', 
            'medical_action': 'متابعة في الرقود',
            'current_flow': 'followup',
            'current_state': FOLLOWUP_DIAGNOSIS,
            'room_number': 'غرفة 205',
            'expected_flow': 'followup'
        },
        {
            'name': 'حالة غامضة - لا medical_action',
            'medical_action': '',
            'current_flow': None,
            'current_state': FOLLOWUP_DIAGNOSIS,
            'room_number': None,
            'expected_flow': 'periodic_followup'  # افتراضي للأمان
        },
        {
            'name': 'في تاريخ العودة بدون رقم غرفة',
            'medical_action': '',
            'current_flow': None,
            'current_state': FOLLOWUP_DATE_TIME,
            'room_number': None,
            'expected_flow': 'periodic_followup'  # اكتشاف ذكي
        }
    ]
    
    for scenario in scenarios:
        print(f"\n🧪 {scenario['name']}:")
        print(f"   medical_action: '{scenario['medical_action']}'")
        print(f"   current_flow: {scenario['current_flow']}")
        print(f"   current_state: {scenario['current_state']}")
        print(f"   room_number: {scenario['room_number']}")
        
        # محاكاة منطق الكشف
        detected_flow = detect_flow_type(scenario)
        
        print(f"   🎯 المتوقع: {scenario['expected_flow']}")
        print(f"   🔍 المكتشف: {detected_flow}")
        
        if detected_flow == scenario['expected_flow']:
            print(f"   ✅ صحيح!")
        else:
            print(f"   ❌ خطأ!")

def detect_flow_type(scenario):
    """محاكاة منطق detect flow_type"""
    
    # Constants
    FOLLOWUP_COMPLAINT = 16
    FOLLOWUP_DIAGNOSIS = 17
    FOLLOWUP_DECISION = 18
    FOLLOWUP_ROOM_FLOOR = 19
    FOLLOWUP_DATE_TIME = 19  # Same as ROOM_FLOOR?
    FOLLOWUP_REASON = 20
    FOLLOWUP_TRANSLATOR = 21
    
    medical_action = scenario['medical_action']
    current_flow = scenario['current_flow']
    current_state = scenario['current_state']
    room_number = scenario['room_number']
    
    # نسخة من منطق التحديد في الكود
    flow_type = current_flow
    
    if not flow_type:
        if medical_action == "متابعة في الرقود":
            flow_type = "followup"
        elif medical_action == "مراجعة / عودة دورية":
            flow_type = "periodic_followup"
        elif medical_action == "استشارة جديدة":
            flow_type = "new_consult"
        elif medical_action == "طوارئ":
            flow_type = "emergency"
        elif current_state:
            # تحديد من current_state
            followup_states = [FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR, FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR]
            if current_state in followup_states:
                # تحديد دقيق لنوع المسار
                if medical_action == "مراجعة / عودة دورية":
                    flow_type = "periodic_followup"
                elif medical_action == "متابعة في الرقود":
                    flow_type = "followup"
                else:
                    # اكتشاف ذكي
                    if current_state == FOLLOWUP_DATE_TIME and not room_number:
                        flow_type = "periodic_followup"
                    else:
                        # افتراضي للأمان
                        flow_type = "periodic_followup"
            else:
                flow_type = 'new_consult'
        else:
            flow_type = 'new_consult'
    
    return flow_type

def test_state_values():
    """اختبار قيم الحالات للتأكد من التضارب"""
    
    print("\n" + "="*80)
    print("🔢 فحص قيم الحالات")
    print("="*80)
    
    states = {
        'FOLLOWUP_COMPLAINT': 16,
        'FOLLOWUP_DIAGNOSIS': 17, 
        'FOLLOWUP_DECISION': 18,
        'FOLLOWUP_ROOM_FLOOR': 19,
        'FOLLOWUP_DATE_TIME': 19,  # Is this the same as ROOM_FLOOR?
        'FOLLOWUP_REASON': 20,
        'FOLLOWUP_TRANSLATOR': 21
    }
    
    for name, value in states.items():
        print(f"{name:20} = {value}")
    
    # فحص التضارب
    print("\n🔍 فحص التضارب:")
    if states['FOLLOWUP_ROOM_FLOOR'] == states['FOLLOWUP_DATE_TIME']:
        print("❌ تضارب! FOLLOWUP_ROOM_FLOOR و FOLLOWUP_DATE_TIME لهما نفس القيمة!")
        print("   هذا قد يؤدي لمشاكل في التنقل")
    else:
        print("✅ لا توجد تضاربات في قيم الحالات")

if __name__ == "__main__":
    test_state_values()
    test_flow_type_detection()