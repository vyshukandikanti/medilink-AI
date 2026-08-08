import os
import sys
import tempfile
import sqlite3
import hashlib
import pytest

# Ensure the health directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../health')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from health.app import app, init_db
import health.app
import health.ai_helper

@pytest.fixture
def test_client():
    # Create a temporary file for the database
    db_fd, db_path = tempfile.mkstemp()
    app.config['TESTING'] = True
    app.config['DATABASE'] = db_path
    
    # Store old path and override global path
    old_db_path = health.app.DB_PATH
    health.app.DB_PATH = db_path
    
    # Initialize the database
    with app.app_context():
        init_db()
        
    with app.test_client() as client:
        yield client
        
    # Clean up database file
    os.close(db_fd)
    os.unlink(db_path)
    health.app.DB_PATH = old_db_path

def test_legacy_password_login_and_upgrade(test_client):
    # Manually seed a legacy user with SHA-256 password hash
    conn = sqlite3.connect(health.app.DB_PATH)
    cursor = conn.cursor()
    
    legacy_pw = "legacy123"
    legacy_hash = hashlib.sha256(legacy_pw.encode()).hexdigest()
    
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
        ("legacy_user", legacy_hash, "doctor", "Legacy Doctor")
    )
    conn.commit()
    conn.close()
    
    # Perform login using the legacy password
    response = test_client.post('/api/auth/login', json={
        'username': 'legacy_user',
        'password': legacy_pw
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['user']['username'] == 'legacy_user'
    
    # Check that the password was automatically upgraded to modern scrypt/pbkdf2
    conn = sqlite3.connect(health.app.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = 'legacy_user'")
    updated_hash = cursor.fetchone()[0]
    conn.close()
    
    assert updated_hash != legacy_hash
    assert updated_hash.startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))
    
    # Perform login again to verify the upgraded password works
    response2 = test_client.post('/api/auth/login', json={
        'username': 'legacy_user',
        'password': legacy_pw
    })
    assert response2.status_code == 200

def test_login_invalid_credentials(test_client):
    response = test_client.post('/api/auth/login', json={
        'username': 'admin',
        'password': 'wrongpassword'
    })
    assert response.status_code == 401
    assert response.get_json()['status'] == 'error'

def test_patient_registration_and_retrieval(test_client):
    # Register patient
    patient_data = {
        'full_name': 'John Doe',
        'age': 35,
        'gender': 'Male',
        'blood_group': 'O+',
        'phone': '123-456-7890',
        'address': '123 Health St',
        'emergency_contact': '987-654-3210',
        'allergies': 'Penicillin',
        'chronic_diseases': 'None'
    }
    response = test_client.post('/api/patients', json=patient_data)
    assert response.status_code == 200
    reg_result = response.get_json()
    assert reg_result['status'] == 'success'
    health_id = reg_result['patient']['health_id']
    assert health_id.startswith('MED-')
    
    # Retrieve patient by Health ID
    response2 = test_client.get(f'/api/patients/{health_id}')
    assert response2.status_code == 200
    ret_result = response2.get_json()
    assert ret_result['status'] == 'success'
    assert ret_result['patient']['full_name'] == 'John Doe'
    assert ret_result['patient']['allergies'] == 'Penicillin'

def test_ai_summary_endpoint(test_client):
    # Register patient
    patient_data = {
        'full_name': 'Jane Doe',
        'age': 28,
        'gender': 'Female',
        'blood_group': 'A-',
        'phone': '123-123-1234',
        'address': '456 Wellness Rd',
        'emergency_contact': 'None',
        'allergies': 'None',
        'chronic_diseases': 'Asthma'
    }
    reg_resp = test_client.post('/api/patients', json=patient_data).get_json()
    health_id = reg_resp['patient']['health_id']
    
    # Request AI summary (rule-based fallback mode)
    health.app.ai_helper.HAS_REAL_AI = False
    response = test_client.post('/api/ai/summary', json={'health_id': health_id})
    assert response.status_code == 200
    summary_data = response.get_json()
    assert summary_data['status'] == 'success'
    assert len(summary_data['summary']) > 0
    assert any("Jane Doe" in s for s in summary_data['summary'])
    assert any("Asthma" in s for s in summary_data['summary'])

def test_ai_drug_check(test_client):
    # Test safe drug check
    response = test_client.post('/api/ai/drug-check', json={'medicines': 'Amoxicillin, Paracetamol'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'Amoxicillin' in data['medicines_analyzed']
    
    # Test high risk interaction
    response2 = test_client.post('/api/ai/drug-check', json={'medicines': 'Aspirin, Warfarin'})
    assert response2.status_code == 200
    data2 = response2.get_json()
    assert any(i['severity'] == 'HIGH RISK' for i in data2['interactions'])

def test_ai_explain(test_client):
    response = test_client.post('/api/ai/explain', json={'text': 'hypertension stage 1'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'elevated' in data['simplified_explanation']

def test_ai_risk_alerts(test_client):
    # Register patient with Asthma
    patient_data = {
        'full_name': 'Aarav Kumar',
        'age': 12,
        'gender': 'Male',
        'blood_group': 'B+',
        'phone': '111-222-3333',
        'address': '789 City Rd',
        'emergency_contact': '999-999-9999',
        'allergies': 'None',
        'chronic_diseases': 'Asthma'
    }
    reg_resp = test_client.post('/api/patients', json=patient_data).get_json()
    health_id = reg_resp['patient']['health_id']
    
    # Get risk alerts
    response = test_client.get(f'/api/ai/risk-alerts/{health_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert any("ASTHMA" in a['title'] for a in data['alerts'])

def test_emergency_profile_xss_protection(test_client):
    # Register patient with XSS injection in name and allergy fields
    xss_name = "<script>alert('XSS Name')</script>"
    xss_allergy = "<img src=x onerror=alert('XSS Allergy')>"
    
    patient_data = {
        'full_name': xss_name,
        'age': 40,
        'gender': 'Female',
        'blood_group': 'AB+',
        'phone': '555-555-5555',
        'address': 'XSS St',
        'emergency_contact': 'None',
        'allergies': xss_allergy,
        'chronic_diseases': 'None'
    }
    reg_resp = test_client.post('/api/patients', json=patient_data).get_json()
    health_id = reg_resp['patient']['health_id']
    
    # Retrieve emergency card HTML
    response = test_client.get(f'/emergency/{health_id}')
    assert response.status_code == 200
    html_content = response.get_data(as_text=True)
    
    # Ensure unescaped tags do not exist, and are properly escaped
    assert xss_name not in html_content
    assert xss_allergy not in html_content
    assert "&lt;script&gt;alert(&#39;XSS Name&#39;)&lt;/script&gt;" in html_content
    assert "&lt;img src=x onerror=alert(&#39;XSS Allergy&#39;)&gt;" in html_content
