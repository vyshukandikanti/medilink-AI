import os
import sqlite3
import json
import re
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

load_dotenv()

from werkzeug.security import generate_password_hash, check_password_hash
import ai_helper

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'medilink-ai-secret-key-2026')

# Check if persistent storage mount is connected, otherwise fall back to local sqlite file
DB_DIR = '/mnt/dbstorage'
if os.path.exists(DB_DIR):
  DB_PATH = os.path.join(DB_DIR, 'database.db')
else:
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
    
    summary_bullets = ai_helper.get_ai_summary(patient_dict, records)
    
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
        
    result = ai_helper.check_drug_interactions(medicines_str)
    
    return jsonify({
        'status': 'success',
        'medicines_analyzed': result['medicines_analyzed'],
        'interactions': result['interactions']
    })

@app.route('/api/ai/explain', methods=['POST'])
def ai_explain():
    data = request.json or {}
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'status': 'error', 'message': 'Please provide medical notes to explain'}), 400
        
    explained = ai_helper.explain_medical_notes(text)
        
    return jsonify({
        'status': 'success',
        'original_text': text,
        'simplified_explanation': explained
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
    
    cursor.execute('SELECT * FROM medical_records WHERE patient_id = ? ORDER BY visit_date DESC', (p['id'],))
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    alerts = ai_helper.get_risk_alerts(p, records)
            
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
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Invalid username or password'}), 401
        
    user_dict = dict(user)
    stored_hash = user_dict['password_hash']
    
    is_valid = False
    needs_upgrade = False
    
    # Check if modern hash format
    if stored_hash.startswith(('scrypt:', 'pbkdf2:', 'bcrypt:')):
        is_valid = check_password_hash(stored_hash, password)
    else:
        # Fallback to legacy SHA-256 for backward compatibility
        import hashlib
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        if legacy_hash == stored_hash:
            is_valid = True
            needs_upgrade = True
            
    if not is_valid:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Invalid username or password'}), 401
        
    if needs_upgrade:
        modern_hash = generate_password_hash(password)
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (modern_hash, user_dict['id']))
        conn.commit()
        
    conn.close()
    
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
    conn.close()
    
    if not p:
        return "Patient Emergency Card Not Found", 404
        
    return render_template('emergency.html', patient=dict(p))

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    print(f"MediLink AI Server starting on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
