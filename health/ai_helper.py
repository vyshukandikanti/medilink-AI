import os
import re
import google.generativeai as genai

# Configure Google GenAI SDK if key is present
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
HAS_REAL_AI = False

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        HAS_REAL_AI = True
    except Exception as e:
        print("Failed to initialize Google Generative AI:", e)

def get_ai_summary(patient, records):
    """
    Generate an intelligence summary of patient demographics and records.
    If GEMINI_API_KEY is active, uses gemini-1.5-flash.
    Otherwise, falls back to rule-based summary.
    """
    if HAS_REAL_AI:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            records_summary = "\n".join([
                f"- Date: {r['visit_date']}, Hospital: {r['hospital_name']}, Diagnosis: {r['diagnosis']}, Symptoms: {r['symptoms']}, Medications: {r['medicines']}, Notes: {r['notes']}"
                for r in records
            ])
            prompt = f"""
            Analyze the following patient and their medical history. Generate a concise, bulleted professional clinical summary (4-6 bullets max) in Markdown format.
            Include:
            - Overview of patient demographics, blood type, and key vitals (if available).
            - Known allergies and chronic conditions.
            - Brief outline of visit history and active medications.
            - Clinical risk considerations (e.g. tracking patterns, potential warning signs).
            
            Patient Info:
            Name: {patient['full_name']}
            Age: {patient['age']}
            Gender: {patient['gender']}
            Blood Group: {patient['blood_group']}
            Allergies: {patient['allergies']}
            Chronic Diseases: {patient['chronic_diseases']}
            
            Medical Records:
            {records_summary if records else "No medical history recorded."}
            
            Format the response as a JSON array of strings, where each string is a summary bullet (omit the outer code blocks, just return the JSON). Example:
            ["Bullet 1", "Bullet 2", "Bullet 3"]
            """
            response = model.generate_content(prompt)
            # Try parsing the JSON response
            text = response.text.strip()
            # Clean up markdown code blocks if any
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n|```$", "", text, flags=re.MULTILINE).strip()
            import json
            bullets = json.loads(text)
            if isinstance(bullets, list) and all(isinstance(b, str) for b in bullets):
                return bullets
        except Exception as e:
            print("Gemini API call failed for summary, falling back to mock:", e)

    # Mock Fallback
    summary_bullets = [
        f"Patient **{patient['full_name']}** ({patient['age']} y/o {patient['gender']}, Blood Type {patient['blood_group']}) has **{len(records)} recorded visit(s)** in system.",
        f"**Known Allergies:** {patient['allergies'] if patient['allergies'] != 'None' else 'No documented drug allergies.'}",
        f"**Chronic Conditions:** {patient['chronic_diseases'] if patient['chronic_diseases'] != 'None' else 'No major chronic illnesses reported.'}"
    ]
    if records:
        latest = records[0]
        summary_bullets.append(f"**Latest Visit ({latest['visit_date']}):** Diagnosed with *{latest['diagnosis']}* at {latest['hospital_name']}.")
        if latest['medicines']:
            summary_bullets.append(f"**Active Medications:** {latest['medicines']}")
        if latest['blood_pressure']:
            summary_bullets.append(f"**Vitals Baseline:** BP {latest['blood_pressure']} mmHg | Blood Glucose {latest['sugar_level']} mg/dL.")
        
        hospitals = list(set(r['hospital_name'] for r in records))
        summary_bullets.append(f"**Hospital Coverage:** Records synced across {len(hospitals)} medical center(s): {', '.join(hospitals)}.")
    else:
        summary_bullets.append("No medical visits recorded yet for this patient.")
    return summary_bullets

def check_drug_interactions(medicines_str):
    """
    Check for potential interactions between medications.
    """
    medicines = [m.strip() for m in re.split(r'[,+\n&]', medicines_str) if m.strip()]
    if not medicines:
        return {"medicines_analyzed": [], "interactions": []}

    if HAS_REAL_AI:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
            Analyze the following list of medications for potential drug-to-drug interactions.
            List of meds: {', '.join(medicines)}
            
            Format your response as a JSON object containing the list of analyzed medicines and an array of detected interactions.
            The severity MUST be one of: 'SAFE', 'MODERATE RISK', or 'HIGH RISK'.
            Example JSON output:
            {{
              "medicines_analyzed": ["Drug A", "Drug B"],
              "interactions": [
                {{
                  "combination": "Drug A + Drug B",
                  "severity": "HIGH RISK",
                  "note": "Description of the clinical interaction risk and recommendation."
                }}
              ]
            }}
            Omit any markdown code blocks or additional explanation outside the JSON.
            """
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n|```$", "", text, flags=re.MULTILINE).strip()
            import json
            result = json.loads(text)
            if "interactions" in result:
                return result
        except Exception as e:
            print("Gemini API call failed for drug check, falling back to mock:", e)

    # Mock Fallback
    interactions = []
    meds_upper = [m.upper() for m in medicines]
    known_interactions = [
        ({'WARFARIN', 'ASPIRIN'}, 'HIGH RISK', 'Combined use significantly increases severe gastrointestinal bleeding risk.'),
        ({'METFORMIN', 'ALCOHOL'}, 'MODERATE RISK', 'Increases risk of severe lactic acidosis and hypoglycemia.'),
        ({'LISINOPRIL', 'IBUPROFEN'}, 'MODERATE RISK', 'NSAIDs reduce the antihypertensive effect of Lisinopril and increase renal risk.'),
        ({'AMOXICILLIN', 'METHOTREXATE'}, 'HIGH RISK', 'Amoxicillin reduces renal clearance of Methotrexate leading to toxicity.'),
        ({'ATORVASTATIN', 'CLARITHROMYCIN'}, 'HIGH RISK', 'Clarithromycin increases plasma concentration of Atorvastatin, risking myopathy.'),
        ({'CLOPIDOGREL', 'OMEPRAZOLE'}, 'MODERATE RISK', 'Omeprazole inhibits CYP2C19, reducing Clopidogrel efficacy.'),
        ({'PARACETAMOL', 'AMOXICILLIN'}, 'SAFE', 'No known major drug interaction detected. Safe for concurrent use under prescribed doses.')
    ]
    
    found = False
    for group, severity, note in known_interactions:
        if len(group) == 2:
            g1, g2 = list(group)
            if any(g1 in m for m in meds_upper) and any(g2 in m for m in meds_upper):
                found = True
                interactions.append({
                    'combination': f"{g1} + {g2}",
                    'severity': severity,
                    'note': note
                })
                
    if not found:
        if len(medicines) >= 2:
            interactions.append({
                'combination': f"{' + '.join(medicines[:2])}",
                'severity': 'SAFE',
                'note': 'No severe clinical contraindications detected between these medications.'
            })
        else:
            interactions.append({
                'combination': medicines[0] if medicines else 'Single Medication',
                'severity': 'SAFE',
                'note': 'Single drug regimen analyzed. No adverse dual-drug combinations flagged.'
            })
            
    return {
        'medicines_analyzed': medicines,
        'interactions': interactions
    }

def explain_medical_notes(text):
    """
    Explain medical terminology in patient notes in simple layman terms.
    """
    if not text:
        return ""

    if HAS_REAL_AI:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
            Explain the following medical note or diagnosis in extremely simple, reassuring, and clear layman terms for a patient.
            Keep it to 2-3 sentences.
            
            Medical Note: {text}
            """
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print("Gemini API call failed for explanation, falling back to mock:", e)

    # Mock Fallback
    explanations = {
        'hypertension stage 1': 'Your blood pressure reading is slightly elevated above normal (130-139/80-89 mmHg). Regular aerobic exercise, lower sodium intake, and routine monitoring are recommended.',
        'hypertension': 'High blood pressure. Your heart has to work harder to pump blood through your arteries. Medication and lifestyle tweaks keep it safe.',
        'type 2 diabetes': 'Your body struggles to process blood sugar efficiently. Maintaining a balanced low-carb diet, exercising, and taking prescribed medication helps stabilize glucose levels.',
        'acute asthma exacerbation': 'A sudden flare-up of asthma symptoms causing airway swelling and tightness. Rescue inhalers quickly open up airways for easier breathing.',
        'iron deficiency anemia': 'Your body has low iron levels, resulting in fewer red blood cells to carry oxygen. Iron supplements and iron-rich foods will rebuild energy levels.',
        'coronary artery disease': 'The blood vessels bringing oxygen to your heart muscle have narrowed. Cholesterol management and medication protect heart function.',
        'streptococcal tonsillitis': 'A bacterial throat infection causing throat soreness and fever. Completing the full antibiotic course clears the bacteria completely.',
        'osteoarthritis': 'Wear and tear of joint cartilage leading to stiffness or discomfort. Gentle exercise, joint gels, and pain relief support comfortable movement.',
        'hyperlipidemia': 'Elevated cholesterol or fats in the bloodstream. Healthy diet and statin medications help maintain clear arteries.'
    }
    
    text_lower = text.lower()
    for key, explanation in explanations.items():
        if key in text_lower:
            return explanation
            
    return f"Medical Summary: '{text}'. Your healthcare provider evaluated these findings. All vitals and lab markers were logged for trackable longitudinal care."

def get_risk_alerts(patient, records):
    """
    Evaluate vital trends and history to generate clinical risk flags or alerts.
    """
    if HAS_REAL_AI:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            records_summary = "\n".join([
                f"- Date: {r['visit_date']}, Diagnosis: {r['diagnosis']}, BP: {r.get('blood_pressure')}, Sugar: {r.get('sugar_level')}, Notes: {r.get('notes')}"
                for r in records
            ])
            prompt = f"""
            Analyze the patient's vitals (Blood Pressure, Sugar Level) and medical history for clinical risks.
            Generate a list of risk alerts. Each alert should contain a title, severity type ('danger', 'warning', or 'info'), a FontAwesome 6 icon class name, and a description.
            
            Patient details:
            Name: {patient['full_name']}
            Chronic Conditions: {patient['chronic_diseases']}
            Allergies: {patient['allergies']}
            
            Historical Records:
            {records_summary}
            
            Format response as a JSON array of objects. Example:
            [
              {{
                "title": "HYPERTENSION ALERT: STAGE 1",
                "type": "warning",
                "icon": "fa-gauge-high",
                "description": "BP shows persistent Stage 1 hypertension trend. Recommend daily home monitoring and sodium restriction."
              }}
            ]
            Omit any markdown formatting code blocks. Just return the JSON array.
            """
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n|```$", "", text, flags=re.MULTILINE).strip()
            import json
            alerts = json.loads(text)
            if isinstance(alerts, list):
                return alerts
        except Exception as e:
            print("Gemini API call failed for risk alerts, falling back to mock:", e)

    # Mock Fallback
    alerts = []
    
    # Drug allergies check
    allergies = [a.strip() for a in patient['allergies'].split(',') if a.strip() and a.strip().lower() != 'none']
    for allergy in allergies:
        alerts.append({
            'title': f"DRUG ALLERGY: {allergy.upper()}",
            'type': 'danger',
            'icon': 'fa-triangle-exclamation',
            'description': f"Strictly avoid prescribing or administering {allergy}. Potential anaphylaxis / severe reaction."
        })
        
    # Chronic conditions check
    chronic = [c.strip() for c in patient['chronic_diseases'].split(',') if c.strip() and c.strip().lower() != 'none']
    for condition in chronic:
        c_lower = condition.lower()
        if 'diabetes' in c_lower:
            alerts.append({
                'title': 'CHRONIC RISK: DIABETES MELLITUS',
                'type': 'warning',
                'icon': 'fa-droplet',
                'description': 'Requires continuous glycemic tracking, HbA1c monitoring, and kidney function checks.'
            })
        elif 'asthma' in c_lower:
            alerts.append({
                'title': 'RESPIRATORY RISK: ASTHMA',
                'type': 'warning',
                'icon': 'fa-lungs',
                'description': 'Keep rescue inhalers accessible. Avoid Beta-blockers and NSAIDs without respiratory consultation.'
            })
        elif 'heart' in c_lower or 'coronary' in c_lower:
            alerts.append({
                'title': 'CARDIAC RISK: CARDIOVASCULAR DISEASE',
                'type': 'danger',
                'icon': 'fa-heart-pulse',
                'description': 'High vulnerability for ischemic events. Lipid management & blood pressure control mandatory.'
            })
        elif 'hypertension' in c_lower:
            alerts.append({
                'title': 'VASCULAR RISK: HYPERTENSION',
                'type': 'warning',
                'icon': 'fa-gauge-high',
                'description': 'Monitor blood pressure log regularly. Target baseline < 130/80 mmHg.'
            })
        else:
            alerts.append({
                'title': f"CHRONIC CONDITION: {condition.upper()}",
                'type': 'info',
                'icon': 'fa-notes-medical',
                'description': f"Patient requires longitudinal care for {condition}."
            })
            
    # Scan records for drug interactions
    all_meds = []
    for r in records:
        if r['medicines']:
            meds = [m.strip().upper() for m in re.split(r'[,+\n&]', r['medicines']) if m.strip()]
            all_meds.extend(meds)
            
    known_interactions = [
        ({'WARFARIN', 'ASPIRIN'}, 'HIGH RISK', 'Combined use significantly increases severe gastrointestinal bleeding risk.'),
        ({'METFORMIN', 'ALCOHOL'}, 'MODERATE RISK', 'Increases risk of severe lactic acidosis and hypoglycemia.'),
        ({'LISINOPRIL', 'IBUPROFEN'}, 'MODERATE RISK', 'NSAIDs reduce the antihypertensive effect of Lisinopril and increase renal risk.'),
        ({'AMOXICILLIN', 'METHOTREXATE'}, 'HIGH RISK', 'Amoxicillin reduces renal clearance of Methotrexate leading to toxicity.'),
        ({'ATORVASTATIN', 'CLARITHROMYCIN'}, 'HIGH RISK', 'Clarithromycin increases plasma concentration of Atorvastatin, risking myopathy.'),
        ({'CLOPIDOGREL', 'OMEPRAZOLE'}, 'MODERATE RISK', 'Omeprazole inhibits CYP2C19, reducing Clopidogrel efficacy.')
    ]
    
    detected_interactions = set()
    for group, severity, note in known_interactions:
        g1, g2 = list(group)
        if any(g1 in m for m in all_meds) and any(g2 in m for m in all_meds):
            pair_name = f"{g1} + {g2}"
            if pair_name not in detected_interactions:
                detected_interactions.add(pair_name)
                alerts.append({
                    'title': f"DRUG INTERACTION DETECTED: {pair_name}",
                    'type': 'danger' if 'HIGH' in severity else 'warning',
                    'icon': 'fa-circle-exclamation',
                    'description': f"Prescription log contains active overlapping drugs. {note}"
                })
                
    # Check for missing vitals
    has_bp = False
    has_sugar = False
    if records:
        latest = records[0]
        if latest['blood_pressure'] and latest['blood_pressure'].strip() != 'N/A' and latest['blood_pressure'].strip() != '' and latest['blood_pressure'].strip() != '120/80':
            has_bp = True
        if latest['sugar_level'] and latest['sugar_level'].strip() != 'N/A' and latest['sugar_level'].strip() != '' and latest['sugar_level'].strip() != '95':
            has_sugar = True
            
    if not records or not has_bp or not has_sugar:
        missing_vitals = []
        if not has_bp: missing_vitals.append("Blood Pressure")
        if not has_sugar: missing_vitals.append("Blood Glucose")
        
        alerts.append({
            'title': "INCOMPLETE VITAL SCREENING",
            'type': 'warning',
            'icon': 'fa-flask-vial',
            'description': f"Missing recent custom {', '.join(missing_vitals)} measurements. Please update record vitals."
        })
            
    return alerts
