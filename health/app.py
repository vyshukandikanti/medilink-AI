import os
import sqlite3
import json
import re
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'medilink-ai-secret-key-2026')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db():
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn

def init_db():
  conn = get_db()
  cursor = conn.cursor()
  
  # Create Patients Table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS patients (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          health_id TEXT UNIQUE NOT NULL,
          full_name TEXT NOT NULL,
          age INTEGER NOT NULL,
          gender TEXT NOT NULL,
          blood_group TEXT NOT NULL,
          phone TEXT NOT NULL,
          address TEXT,
          emergency_contact TEXT,
          allergies TEXT,
          chronic_diseases TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  ''')
  
  # Create Medical Records Table (Without Doctor Name)
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS medical_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_id INTEGER NOT NULL,
          hospital_name TEXT NOT NULL,
          visit_date TEXT NOT NULL,
          symptoms TEXT,
          diagnosis TEXT NOT NULL,
          prescription TEXT,
          medicines TEXT,
          lab_report TEXT,
          blood_pressure TEXT,
          sugar_level TEXT,
          notes TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
      )
  ''')

  # Create Users Table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL,
          full_name TEXT NOT NULL
      )
  ''')

  # Create Appointments Table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS appointments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_health_id TEXT NOT NULL,
          patient_name TEXT NOT NULL,
          time_slot TEXT NOT NULL,
          doctor_name TEXT NOT NULL,
          department TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Confirmed'
      )
  ''')

  # Create Audit Logs Table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          username TEXT NOT NULL,
          role TEXT NOT NULL,
          action TEXT NOT NULL,
          details TEXT NOT NULL
      )
  ''')

  # Create Patient Documents Table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS patient_documents (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_health_id TEXT NOT NULL,
          filename TEXT NOT NULL,
          upload_date TEXT NOT NULL,
          file_size TEXT NOT NULL
      )
  ''')
  
  conn.commit()

  # Seed Users
  cursor.execute('SELECT COUNT(*) as count FROM users')
  if cursor.fetchone()['count'] == 0:
      import hashlib
      def hash_pw(pw):
          return hashlib.sha256(pw.encode()).hexdigest()
      users_data = [
          ('admin', hash_pw('admin123'), 'admin', 'System Admin'),
          ('doctor', hash_pw('doctor123'), 'doctor', 'Dr. Alexander'),
          ('nurse', hash_pw('nurse123'), 'nurse', 'Nurse Sarah'),
          ('recep', hash_pw('recep123'), 'receptionist', 'Receptionist Emma')
      ]
      cursor.executemany('INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)', users_data)

  # Seed Appointments
  cursor.execute('SELECT COUNT(*) as count FROM appointments')
  if cursor.fetchone()['count'] == 0:
      appointments_data = [
          ('MED-2026-278373', 'Rahul Kumar', '09:00 AM', 'Dr. Kumar', 'Cardiology', 'Confirmed'),
          ('MED-2026-961776', 'Sarah Smith', '10:30 AM', 'Dr. Alexander', 'General Medicine', 'Waiting'),
          ('MED-2026-622419', 'Aarav Sharma', '12:00 PM', 'Dr. Kumar', 'Cardiology', 'Completed'),
          ('MED-2026-896489', 'Ananya Patel', '03:30 PM', 'Dr. Alexander', 'Pediatrics', 'Confirmed')
      ]
      cursor.executemany('INSERT INTO appointments (patient_health_id, patient_name, time_slot, doctor_name, department, status) VALUES (?, ?, ?, ?, ?, ?)', appointments_data)

  # Seed Audit Logs
  cursor.execute('SELECT COUNT(*) as count FROM audit_logs')
  if cursor.fetchone()['count'] == 0:
      import datetime as dt
      now_str = dt.datetime.now().strftime('%d %b %Y %I:%M %p')
      yesterday_str = (dt.datetime.now() - dt.timedelta(days=1)).strftime('%d %b %Y %I:%M %p')
      logs_data = [
          (now_str, 'doctor', 'doctor', 'VIEW_PATIENT', 'Viewed Rahul Kumar\'s record'),
          (now_str, 'nurse', 'nurse', 'UPDATE_RECORD', 'Added vital signs for Ananya Patel'),
          (now_str, 'admin', 'admin', 'CREATE_RECORD', 'Registered patient Sarah Smith'),
          (yesterday_str, 'doctor', 'doctor', 'UPDATE_RECORD', 'Updated prescription for Rahul Kumar')
      ]
      cursor.executemany('INSERT INTO audit_logs (timestamp, username, role, action, details) VALUES (?, ?, ?, ?, ?)', logs_data)

  # Seed Documents
  cursor.execute('SELECT COUNT(*) as count FROM patient_documents')
  if cursor.fetchone()['count'] == 0:
      import datetime as dt
      now_date = dt.datetime.now().strftime('%Y-%m-%d')
      docs_data = [
          ('MED-2026-278373', 'Blood Report.pdf', now_date, '240 KB'),
          ('MED-2026-278373', 'Scan Report.pdf', now_date, '1.2 MB'),
          ('MED-2026-896489', 'Prescription.pdf', now_date, '180 KB'),
          ('MED-2026-896489', 'Discharge Summary.pdf', now_date, '420 KB')
      ]
      cursor.executemany('INSERT INTO patient_documents (patient_health_id, filename, upload_date, file_size) VALUES (?, ?, ?, ?)', docs_data)

  conn.commit()
  conn.close()

# Helper to format next randomized Health ID
def generate_health_id():
  year = datetime.now().year
  conn = get_db()
  cursor = conn.cursor()
  while True:
      # Generate random 6-digit number
      num = random.randint(100000, 999999)
      health_id = f"MED-{year}-{num}"
      # Check uniqueness in database
      cursor.execute('SELECT 1 FROM patients WHERE health_id = ?', (health_id,))
      if not cursor.fetchone():
          conn.close()
          return health_id

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as total_patients FROM patients')
    total_patients = cursor.fetchone()['total_patients']
    
    cursor.execute('SELECT COUNT(*) as total_visits FROM medical_records')
    total_visits = cursor.fetchone()['total_visits']
    
    cursor.execute('SELECT COUNT(DISTINCT hospital_name) as total_hospitals FROM medical_records')
    total_hospitals = cursor.fetchone()['total_hospitals']
    
    # Get 5 recent visits
    cursor.execute('''
        SELECT mr.*, p.full_name, p.health_id 
        FROM medical_records mr 
        JOIN patients p ON mr.patient_id = p.id 
        ORDER BY mr.created_at DESC LIMIT 5
    ''')
    recent_activity = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'status': 'success',
        'total_patients': total_patients,
        'total_visits': total_visits,
        'total_hospitals': total_hospitals,
        'ai_summaries': total_visits,
        'recent_activity': recent_activity
    })

@app.route('/api/patients', methods=['GET'])
def list_patients():
    query = request.args.get('search', '').strip()
    conn = get_db()
    cursor = conn.cursor()
    
    if query:
        search_pattern = f"%{query}%"
        cursor.execute('''
            SELECT * FROM patients 
            WHERE health_id LIKE ? OR full_name LIKE ? OR phone LIKE ?
            ORDER BY id DESC
        ''', (search_pattern, search_pattern, search_pattern))
    else:
        cursor.execute('SELECT * FROM patients ORDER BY id DESC')
        
    patients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'status': 'success', 'patients': patients})

@app.route('/api/patients/<identifier>', methods=['GET'])
def get_patient(identifier):
    conn = get_db()
    cursor = conn.cursor()
    
    if identifier.isdigit():
        cursor.execute('SELECT * FROM patients WHERE id = ?', (int(identifier),))
    else:
        cursor.execute('SELECT * FROM patients WHERE health_id = ?', (identifier,))
        
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Patient not found'}), 404
        
    patient_dict = dict(patient)
    
    # Fetch medical records sorted by visit_date DESC
    cursor.execute('''
        SELECT * FROM medical_records 
        WHERE patient_id = ? 
        ORDER BY visit_date DESC, id DESC
    ''', (patient_dict['id'],))
    
    records = [dict(row) for row in cursor.fetchall()]
    patient_dict['records'] = records
    
    conn.close()
    return jsonify({'status': 'success', 'patient': patient_dict})

@app.route('/api/patients', methods=['POST'])
def create_patient():
    data = request.json or {}
    
    full_name = data.get('full_name', '').strip()
    age = data.get('age')
    gender = data.get('gender', '').strip()
    blood_group = data.get('blood_group', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    emergency_contact = data.get('emergency_contact', '').strip()
    allergies = data.get('allergies', '').strip() or 'None'
    chronic_diseases = data.get('chronic_diseases', '').strip() or 'None'
    
    if not full_name or not age or not gender or not blood_group or not phone:
        return jsonify({'status': 'error', 'message': 'Please fill all required patient fields.'}), 400
        
    health_id = generate_health_id()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO patients (health_id, full_name, age, gender, blood_group, phone, address, emergency_contact, allergies, chronic_diseases)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (health_id, full_name, int(age), gender, blood_group, phone, address, emergency_contact, allergies, chronic_diseases))
    
    patient_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': 'Patient registered successfully!',
        'patient': {
            'id': patient_id,
            'health_id': health_id,
            'full_name': full_name,
            'age': age,
            'gender': gender,
            'blood_group': blood_group
        }
    })

@app.route('/api/records', methods=['POST'])
def create_medical_record():
    data = request.json or {}
    
    health_id = data.get('health_id', '').strip()
    hospital_name = data.get('hospital_name', '').strip() or 'Metro General Hospital'
    visit_date = data.get('visit_date', '').strip() or datetime.now().strftime('%Y-%m-%d')
    symptoms = data.get('symptoms', '').strip()
    diagnosis = data.get('diagnosis', '').strip()
    prescription = data.get('prescription', '').strip()
    medicines = data.get('medicines', '').strip()
    lab_report = data.get('lab_report', '').strip() or 'N/A'
    blood_pressure = data.get('blood_pressure', '').strip() or '120/80'
    sugar_level = data.get('sugar_level', '').strip() or '95'
    notes = data.get('notes', '').strip()
    
    if not health_id or not diagnosis:
        return jsonify({'status': 'error', 'message': 'Health ID and Diagnosis are required.'}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM patients WHERE health_id = ?', (health_id,))
    patient = cursor.fetchone()
    
    if not patient:
        conn.close()
        return jsonify({'status': 'error', 'message': f'Patient with Health ID {health_id} not found.'}), 404
        
    patient_id = patient['id']
    cursor.execute('''
        INSERT INTO medical_records (patient_id, hospital_name, visit_date, symptoms, diagnosis, prescription, medicines, lab_report, blood_pressure, sugar_level, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (patient_id, hospital_name, visit_date, symptoms, diagnosis, prescription, medicines, lab_report, blood_pressure, sugar_level, notes))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Medical record saved successfully!'})

# AI Routes with Intelligent Reasoning Engine
@app.route('/api/ai/summary', methods=['POST'])
def ai_summary():
    data = request.json or {}
    health_id = data.get('health_id')
    
    if not health_id:
        return jsonify({'status': 'error', 'message': 'Health ID required'}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients WHERE health_id = ?', (health_id,))
    patient = cursor.fetchone()
    
    if not patient:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Patient not found'}), 404
        
    patient_dict = dict(patient)
    cursor.execute('SELECT * FROM medical_records WHERE patient_id = ? ORDER BY visit_date DESC', (patient_dict['id'],))
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    summary_bullets = [
        f"Patient **{patient_dict['full_name']}** ({patient_dict['age']} y/o {patient_dict['gender']}, Blood Type {patient_dict['blood_group']}) has **{len(records)} recorded visit(s)** in system.",
        f"**Known Allergies:** {patient_dict['allergies'] if patient_dict['allergies'] != 'None' else 'No documented drug allergies.'}",
        f"**Chronic Conditions:** {patient_dict['chronic_diseases'] if patient_dict['chronic_diseases'] != 'None' else 'No major chronic illnesses reported.'}"
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
    
    return jsonify({
        'status': 'success',
        'summary': summary_bullets
    })

@app.route('/api/ai/drug-check', methods=['POST'])
def ai_drug_check():
    data = request.json or {}
    medicines_str = data.get('medicines', '')
    
    if not medicines_str:
        return jsonify({'status': 'error', 'message': 'Please enter medicines to check'}), 400
        
    medicines = [m.strip() for m in re.split(r'[,+\n&]', medicines_str) if m.strip()]
    
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
            
    return jsonify({
        'status': 'success',
        'medicines_analyzed': medicines,
        'interactions': interactions
    })

@app.route('/api/ai/explain', methods=['POST'])
def ai_explain():
    data = request.json or {}
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'status': 'error', 'message': 'Please provide medical notes to explain'}), 400
        
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
    matched_explanation = None
    
    for key, explanation in explanations.items():
        if key in text_lower:
            matched_explanation = explanation
            break
            
    if not matched_explanation:
        matched_explanation = f"Medical Summary: '{text}'. Your healthcare provider evaluated these findings. All vitals and lab markers were logged for trackable longitudinal care."
        
    return jsonify({
        'status': 'success',
        'original_text': text,
        'simplified_explanation': matched_explanation
    })

@app.route('/api/ai/smart-search', methods=['POST'])
def ai_smart_search():
    data = request.json or {}
    query = data.get('query', '').strip().lower()
    
    if not query:
        return jsonify({'status': 'error', 'message': 'Query required'}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT mr.*, p.full_name, p.health_id, p.age, p.gender 
        FROM medical_records mr
        JOIN patients p ON mr.patient_id = p.id
    ''')
    all_records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    filtered = []
    for r in all_records:
        combined = f"{r['diagnosis']} {r['symptoms']} {r['medicines']} {r['notes']} {r['hospital_name']}".lower()
        
        if ('diab' in query and 'diab' in combined) or \
           ('heart' in query and any(w in combined for w in ['heart', 'cardiac', 'angina', 'coronary', 'artery'])) or \
           ('asthma' in query and 'asthma' in combined) or \
           ('bp' in query or 'hyper' in query) and any(w in combined for w in ['hyper', 'bp', 'pressure']) or \
           ('bone' in query or 'joint' in query or 'osteo' in query) and any(w in combined for w in ['osteo', 'bone', 'joint', 'knee']) or \
           (query in combined):
            filtered.append(r)
            
    return jsonify({
        'status': 'success',
        'query': query,
        'count': len(filtered),
        'results': filtered
    })

@app.route('/api/ai/risk-alerts/<health_id>', methods=['GET'])
def ai_risk_alerts(health_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients WHERE health_id = ?', (health_id,))
    patient = cursor.fetchone()
    
    if not patient:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Patient not found'}), 404
        
    p = dict(patient)
    
    # Fetch medical records
    cursor.execute('SELECT * FROM medical_records WHERE patient_id = ? ORDER BY visit_date DESC', (p['id'],))
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    alerts = []
    
    # Drug allergies check
    allergies = [a.strip() for a in p['allergies'].split(',') if a.strip() and a.strip().lower() != 'none']
    for allergy in allergies:
        alerts.append({
            'title': f"DRUG ALLERGY: {allergy.upper()}",
            'type': 'danger',
            'icon': 'fa-triangle-exclamation',
            'description': f"Strictly avoid prescribing or administering {allergy}. Potential anaphylaxis / severe reaction."
        })
        
    # Chronic conditions check
    chronic = [c.strip() for c in p['chronic_diseases'].split(',') if c.strip() and c.strip().lower() != 'none']
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
            
    return jsonify({
        'status': 'success',
        'health_id': health_id,
        'patient_name': p['full_name'],
        'alerts': alerts
    })

# ===================================================
# ADVANCED CLINICAL WORKFLOW API ROUTERS
# ===================================================

def log_audit(username, role, action, details):
    try:
        conn = get_db()
        cursor = conn.cursor()
        now_str = datetime.now().strftime('%d %b %Y %I:%M %p')
        cursor.execute('''
            INSERT INTO audit_logs (timestamp, username, role, action, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (now_str, username, role, action, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Audit logging error:", e)

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password required'}), 400
        
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password_hash = ?', (username, password_hash))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Invalid username or password'}), 401
        
    user_dict = dict(user)
    session['username'] = user_dict['username']
    session['role'] = user_dict['role']
    session['full_name'] = user_dict['full_name']
    
    log_audit(user_dict['username'], user_dict['role'], 'LOGIN', f"User {user_dict['full_name']} logged in successfully")
    
    return jsonify({
        'status': 'success',
        'user': {
            'username': user_dict['username'],
            'role': user_dict['role'],
            'full_name': user_dict['full_name']
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    username = session.get('username', 'Unknown')
    role = session.get('role', 'Unknown')
    log_audit(username, role, 'LOGOUT', f"User {username} logged out")
    session.clear()
    return jsonify({'status': 'success', 'message': 'Logged out successfully'})

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    return jsonify({
        'status': 'success',
        'user': {
            'username': session['username'],
            'role': session['role'],
            'full_name': session['full_name']
        }
    })

@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM appointments ORDER BY id ASC')
    appts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'status': 'success', 'appointments': appts})

@app.route('/api/appointments', methods=['POST'])
def book_appointment():
    data = request.json or {}
    health_id = data.get('patient_health_id', '').strip()
    patient_name = data.get('patient_name', '').strip()
    time_slot = data.get('time_slot', '').strip()
    doctor_name = data.get('doctor_name', '').strip()
    department = data.get('department', '').strip()
    
    if not health_id or not patient_name or not time_slot or not doctor_name or not department:
        return jsonify({'status': 'error', 'message': 'Please fill all appointment fields.'}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO appointments (patient_health_id, patient_name, time_slot, doctor_name, department, status)
        VALUES (?, ?, ?, ?, ?, 'Confirmed')
    ''', (health_id, patient_name, time_slot, doctor_name, department))
    conn.commit()
    conn.close()
    
    username = session.get('username', 'recep')
    role = session.get('role', 'receptionist')
    log_audit(username, role, 'CREATE_RECORD', f"Booked appointment for {patient_name} with {doctor_name}")
    
    return jsonify({'status': 'success', 'message': 'Appointment booked successfully!'})

@app.route('/api/appointments/<int:appt_id>', methods=['PUT'])
def update_appointment(appt_id):
    data = request.json or {}
    action = data.get('action', '').strip()
    new_time = data.get('time_slot', '').strip()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM appointments WHERE id = ?', (appt_id,))
    appt = cursor.fetchone()
    
    if not appt:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Appointment not found'}), 404
        
    appt_dict = dict(appt)
    username = session.get('username', 'doctor')
    role = session.get('role', 'doctor')
    
    if action == 'cancel':
        cursor.execute('UPDATE appointments SET status = ? WHERE id = ?', ('Cancelled', appt_id))
        log_audit(username, role, 'UPDATE_RECORD', f"Cancelled appointment for {appt_dict['patient_name']}")
    elif action == 'complete':
        cursor.execute('UPDATE appointments SET status = ? WHERE id = ?', ('Completed', appt_id))
        log_audit(username, role, 'UPDATE_RECORD', f"Completed appointment for {appt_dict['patient_name']}")
    elif action == 'reschedule' and new_time:
        cursor.execute('UPDATE appointments SET time_slot = ? WHERE id = ?', (new_time, appt_id))
        log_audit(username, role, 'UPDATE_RECORD', f"Rescheduled appointment for {appt_dict['patient_name']} to {new_time}")
    else:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Invalid action'}), 400
        
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': f'Appointment updated: {action}'})

@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50')
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'status': 'success', 'audit_logs': logs})

@app.route('/api/search/global', methods=['GET'])
def global_search():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify({'status': 'success', 'patients': [], 'conditions': [], 'medicines': [], 'records': []})
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Search Patients
    cursor.execute('''
        SELECT health_id, full_name, age, gender 
        FROM patients 
        WHERE LOWER(health_id) LIKE ? OR LOWER(full_name) LIKE ? OR LOWER(phone) LIKE ?
    ''', (f"%{query}%", f"%{query}%", f"%{query}%"))
    patients = [dict(r) for r in cursor.fetchall()]
    
    # 2. Search Medical Records
    cursor.execute('''
        SELECT mr.diagnosis, mr.visit_date, p.full_name, p.health_id, mr.symptoms
        FROM medical_records mr
        JOIN patients p ON mr.patient_id = p.id
        WHERE LOWER(mr.diagnosis) LIKE ? OR LOWER(mr.symptoms) LIKE ? OR LOWER(mr.notes) LIKE ?
    ''', (f"%{query}%", f"%{query}%", f"%{query}%"))
    records = [dict(r) for r in cursor.fetchall()]
    
    # 3. Search Medicines
    all_medicines = [
        {"name": "Aspirin", "category": "NSAID / Antiplatelet", "risk": "Moderate"},
        {"name": "Warfarin", "category": "Anticoagulant", "risk": "High"},
        {"name": "Lisinopril", "category": "ACE Inhibitor", "risk": "Low"},
        {"name": "Metformin", "category": "Antidiabetic", "risk": "Low"},
        {"name": "Amoxicillin", "category": "Antibiotic", "risk": "Low"},
        {"name": "Albuterol Inhaler", "category": "Bronchodilator", "risk": "Low"},
        {"name": "Paracetamol", "category": "Analgesic / Antipyretic", "risk": "Low"}
    ]
    medicines = [m for m in all_medicines if query in m['name'].lower() or query in m['category'].lower()]
    
    # 4. Search Conditions
    all_conditions = [
        {"name": "Hypertension", "description": "High Blood Pressure"},
        {"name": "Diabetes Mellitus", "description": "High Blood Glucose"},
        {"name": "Asthma", "description": "Chronic respiratory obstruction"},
        {"name": "Seasonal Influenza", "description": "Type A Flu virus infection"}
    ]
    conditions = [c for c in all_conditions if query in c['name'].lower() or query in c['description'].lower()]
    
    conn.close()
    
    # Audit log
    username = session.get('username', 'doctor')
    role = session.get('role', 'doctor')
    log_audit(username, role, 'VIEW_PATIENT', f"Ran global database search for '{query}'")
    
    return jsonify({
        'status': 'success',
        'patients': patients,
        'records': records,
        'medicines': medicines,
        'conditions': conditions
    })

@app.route('/api/patients/<health_id>/documents', methods=['GET', 'POST'])
def patient_documents_api(health_id):
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT * FROM patient_documents WHERE patient_health_id = ? ORDER BY id DESC', (health_id,))
        docs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'status': 'success', 'documents': docs})
        
    elif request.method == 'POST':
        data = request.json or {}
        filename = data.get('filename', 'New Document.pdf').strip()
        file_size = data.get('file_size', '150 KB').strip()
        upload_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            INSERT INTO patient_documents (patient_health_id, filename, upload_date, file_size)
            VALUES (?, ?, ?, ?)
        ''', (health_id, filename, upload_date, file_size))
        conn.commit()
        conn.close()
        
        username = session.get('username', 'doctor')
        role = session.get('role', 'doctor')
        log_audit(username, role, 'UPDATE_RECORD', f"Uploaded simulated document '{filename}' for patient {health_id}")
        
        return jsonify({'status': 'success', 'message': 'Simulated document uploaded successfully!'})

@app.route('/api/patients/<health_id>/documents/<int:doc_id>', methods=['DELETE'])
def delete_patient_document_api(health_id, doc_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT filename FROM patient_documents WHERE id = ?', (doc_id,))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Document not found'}), 404
        
    filename = doc['filename']
    cursor.execute('DELETE FROM patient_documents WHERE id = ?', (doc_id,))
    conn.commit()
    conn.close()
    
    username = session.get('username', 'doctor')
    role = session.get('role', 'doctor')
    log_audit(username, role, 'UPDATE_RECORD', f"Deleted document '{filename}' for patient {health_id}")
    
    return jsonify({'status': 'success', 'message': 'Document deleted successfully!'})

@app.route('/emergency/<health_id>')
def public_emergency_card(health_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients WHERE health_id = ?', (health_id,))
    p = cursor.fetchone()
    
    if not p:
        conn.close()
        return "Patient Emergency Card Not Found", 404
        
    patient = dict(p)
    conn.close()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚨 MediLink Emergency Lifesaver Card</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #F6F9FC; padding: 2rem 1rem; color: #0F172A; display: flex; justify-content: center; }}
            .card {{ background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 5px solid #EF4444; border-radius: 12px; padding: 2rem; max-width: 480px; width: 100%; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); }}
            .header {{ text-align: center; margin-bottom: 1.5rem; }}
            .header i {{ font-size: 2.5rem; color: #EF4444; margin-bottom: 0.5rem; }}
            .header h2 {{ margin: 0; font-size: 1.5rem; }}
            .header p {{ color: #475569; font-size: 0.88rem; margin: 0.25rem 0; }}
            .details {{ display: flex; flex-direction: column; gap: 0.85rem; }}
            .row {{ display: flex; justify-content: space-between; border-bottom: 1px solid #F1F5F9; padding-bottom: 0.5rem; font-size: 0.95rem; }}
            .row span {{ color: #64748B; font-weight: 500; }}
            .row strong {{ color: #0F172A; }}
            .alert-box {{ background: #FEF2F2; border-left: 4px solid #EF4444; padding: 1rem; border-radius: 6px; margin-top: 1rem; color: #991B1B; font-size: 0.88rem; }}
            .alert-box strong {{ display: block; margin-bottom: 0.25rem; }}
            .footer {{ text-align: center; font-size: 0.72rem; color: #94A3B8; margin-top: 2rem; font-weight: 700; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <h2>🚨 Emergency Lifesaver Profile</h2>
                <p>Health ID: {patient['health_id']}</p>
            </div>
            <div class="details">
                <div class="row">
                    <span>Patient Name</span>
                    <strong>{patient['full_name']}</strong>
                </div>
                <div class="row">
                    <span>Age / Gender</span>
                    <strong>{patient['age']} years / {patient['gender']}</strong>
                </div>
                <div class="row">
                    <span>Blood Group</span>
                    <strong style="color:#EF4444; font-size:1.1rem;">{patient['blood_group']}</strong>
                </div>
                <div class="row">
                    <span>Emergency Contact</span>
                    <strong>{patient['emergency_contact'] or 'None'}</strong>
                </div>
            </div>
            <div class="alert-box">
                <strong>⚠️ Critical Medical Alerts</strong>
                <span>Allergies: {patient['allergies'] or 'None'}</span><br>
                <span>Chronic Diseases: {patient['chronic_diseases'] or 'None'}</span>
            </div>
            <div class="footer">
                MediLink AI • Secure Emergency Directory
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    print(f"MediLink AI Server starting on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
