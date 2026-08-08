/* ===================================================
   MediLink AI – Frontend Controller (Light Theme)
   =================================================== */

let activePatientData = null;
let visitsChartInstance = null;
let analyticsVisitsInstance = null;
let analyticsRiskInstance = null;
let pendingSearchHealthId = null;
let currentRole = null;
let patientAllergiesCache = [];

/* ─────────────────────────────────────────────────────
   INIT & EVENT BINDINGS
   ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  checkAuthSession();
  initParticles();
  initLoginParticles();
  fetchDashboardStats();
  loadAllDropdowns();

  // Set default visit date to today
  const recDateInput = document.getElementById('rec_date');
  if (recDateInput) {
    recDateInput.value = new Date().toISOString().split('T')[0];
  }

  // Live allergy checks bindings
  const recHealthId = document.getElementById('rec_health_id');
  if (recHealthId) {
    recHealthId.addEventListener('change', async (e) => {
      const healthId = e.target.value.trim();
      if (!healthId) {
        patientAllergiesCache = [];
        return;
      }
      try {
        const res = await fetch(`/api/patients/${encodeURIComponent(healthId)}`);
        const data = await res.json();
        if (data.status === 'success') {
          patientAllergiesCache = [];
          if (data.patient.allergies && data.patient.allergies.toLowerCase() !== 'none') {
            patientAllergiesCache = data.patient.allergies.split(',').map(a => a.trim().toUpperCase());
          }
          checkLivePrescriptionAllergies();
        } else {
          patientAllergiesCache = [];
        }
      } catch {
        patientAllergiesCache = [];
      }
    });
  }

  const recMedicines = document.getElementById('rec_medicines');
  if (recMedicines) {
    recMedicines.addEventListener('input', checkLivePrescriptionAllergies);
  }
});

/* ─────────────────────────────────────────────────────
   NAVIGATION & PORTAL MANAGEMENT
   ───────────────────────────────────────────────────── */
function switchView(fromId, toId) {
  document.getElementById(fromId).style.display = 'none';
  document.getElementById(toId).style.display = 'flex';

  if (toId === 'landingView') {
    document.getElementById(toId).style.display = 'flex';
  }
  if (toId === 'loginView') {
    initLoginParticles();
  }
}

function showDashboardSection(sectionId, navElement) {
  // Hide all sections
  document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
  
  // Show target section
  const targetSection = document.getElementById(sectionId);
  if (targetSection) targetSection.classList.add('active');

  // Update navigation active states
  if (navElement) {
    document.querySelectorAll('.sidebar-menu .nav-link').forEach(link => link.classList.remove('active'));
    navElement.classList.add('active');
  } else {
    // Look up by attribute matching
    document.querySelectorAll('.sidebar-menu .nav-link').forEach(link => {
      if (link.getAttribute('onclick').includes(sectionId)) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }

  // Reload statistics or lists depending on selection
  if (sectionId === 'view-dashboard') {
    fetchDashboardStats();
  }
}

/* ─────────────────────────────────────────────────────
   LOAD DROPDOWNS & BACKEND CACHE
   ───────────────────────────────────────────────────── */
async function loadAllDropdowns() {
  const select = document.getElementById('aiAssistantPatientSelect');
  if (!select) return;

  try {
    const res = await fetch('/api/patients');
    const data = await res.json();

    if (data.status === 'success' && data.patients && data.patients.length > 0) {
      select.innerHTML = data.patients.map(p =>
        `<option value="${p.health_id}">${p.full_name} (${p.health_id})</option>`
      ).join('');
    } else {
      select.innerHTML = `<option value="">No registered patients</option>`;
    }
  } catch (err) {
    console.error('Error loading patients list:', err);
  }
}

function syncAiAssistantPatient(healthId) {
  if (!healthId) return;
  // Reset results display boxes
  document.getElementById('aiResultPlaceholder').style.display = 'block';
  document.getElementById('aiSummaryOutput').style.display = 'none';
  document.getElementById('aiExplainOutput').style.display = 'none';
  document.getElementById('aiJargonExplainerWrapper').style.display = 'none';
}

/* ─────────────────────────────────────────────────────
   METRICS & CHARTS (LIGHT THEME)
   ───────────────────────────────────────────────────── */
async function fetchDashboardStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();

    if (data.status === 'success') {
      // Landing stats
      animateCounter('landing-stat-patients', data.total_patients);
      animateCounter('landing-stat-doctors', 2); // Static mock doctor count
      animateCounter('landing-stat-reports', data.total_visits);
      animateCounter('landing-stat-appointments', 4);

      // Dashboard stats
      animateCounter('dash-stat-patients', data.total_patients);
      animateCounter('dash-stat-visits', data.total_visits);
      animateCounter('dash-stat-alerts', data.total_patients > 0 ? 3 : 0);

      // Sync recent dashboard risk alerts list
      populateRecentDashboardAlerts(data.recent_activity);

      // Render charts
      renderPortalCharts(data);
    }
  } catch (err) {
    console.error('Error fetching statistics:', err);
  }
}

function populateRecentDashboardAlerts(activities) {
  const container = document.getElementById('dashRiskAlertsStack');
  if (!container) return;

  if (!activities || activities.length === 0) {
    container.innerHTML = `
      <div class="risk-card info">
        <i class="fa-solid fa-circle-info"></i>
        <div>
          <strong>System Secure</strong>
          <span>No patient risk alerts detected in registry logs.</span>
        </div>
      </div>`;
    return;
  }

  // Show a summary alert of the latest registered activity
  const latest = activities[0];
  container.innerHTML = `
    <div class="risk-card danger">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <div>
        <strong>ALLERGY RECORDED: ${latest.full_name.toUpperCase()}</strong>
        <span>Check patient file details before prescribing.</span>
      </div>
    </div>
    <div class="risk-card warning">
      <i class="fa-solid fa-circle-exclamation"></i>
      <div>
        <strong>VITAL SCREENING LOGGED</strong>
        <span>Latest check: BP ${latest.blood_pressure || '120/80'} | Sugar ${latest.sugar_level || '95'} mg/dL</span>
      </div>
    </div>`;
}

function renderPortalCharts(data) {
  const hasVisits = data.total_visits > 0;

  // 1. Dashboard Visit Trends Line Chart
  const visitsCtx = document.getElementById('visitsChart');
  if (visitsCtx) {
    if (visitsChartInstance) visitsChartInstance.destroy();
    visitsChartInstance = drawLineChart(visitsCtx, data.total_visits, hasVisits);
  }

  // 2. Analytics Tab Line Chart
  const analVisCtx = document.getElementById('analyticsVisitsChart');
  if (analVisCtx) {
    if (analyticsVisitsInstance) analyticsVisitsInstance.destroy();
    analyticsVisitsInstance = drawLineChart(analVisCtx, data.total_visits, hasVisits);
  }

  // 3. Analytics Tab Doughnut Chart
  const analRiskCtx = document.getElementById('analyticsRiskChart');
  if (analRiskCtx) {
    if (analyticsRiskInstance) analyticsRiskInstance.destroy();

    analyticsRiskInstance = new Chart(analRiskCtx, {
      type: 'doughnut',
      data: {
        labels: hasVisits ? ['Visits Logs', 'Patient Registry', 'Staff Users'] : ['No records logged'],
        datasets: [{
          data: hasVisits ? [data.total_visits, data.total_patients, 2] : [1],
          backgroundColor: hasVisits ? ['#0F52BA', '#0D9488', '#10B981'] : ['#E2E8F0'],
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { position: 'right', labels: { color: '#334155' } }
        }
      }
    });
  }
}

function drawLineChart(canvasElement, totalVisits, hasVisits) {
  return new Chart(canvasElement, {
    type: 'line',
    data: {
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      datasets: [{
        label: 'Visits Recorded',
        data: hasVisits ? [0, 0, 0, 0, 0, 0, totalVisits] : [0, 0, 0, 0, 0, 0, 0],
        borderColor: '#0F52BA',
        backgroundColor: 'rgba(15, 82, 186, 0.05)',
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointBackgroundColor: '#0D9488',
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.03)' } }
      }
    }
  });
}

function animateCounter(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const targetNum = parseInt(target) || 0;
  if (targetNum === 0) { el.textContent = '0'; return; }

  let current = 0;
  const duration = 1000;
  const stepTime = 30;
  const steps = duration / stepTime;
  const increment = targetNum / steps;

  const timer = setInterval(() => {
    current += increment;
    if (current >= targetNum) {
      el.textContent = targetNum;
      clearInterval(timer);
    } else {
      el.textContent = Math.floor(current);
    }
  }, stepTime);
}

/* ─────────────────────────────────────────────────────
   MODALS CONTROLLER
   ───────────────────────────────────────────────────── */
function openRegisterPatientModal() {
  document.getElementById('addPatientModal').classList.add('active');
}
function closeRegisterPatientModal() {
  document.getElementById('addPatientModal').classList.remove('active');
}
function openAddRecordModal() {
  document.getElementById('addRecordModal').classList.add('active');
}
function closeAddRecordModal() {
  document.getElementById('addRecordModal').classList.remove('active');
}

/* ─────────────────────────────────────────────────────
   PATIENT REGISTRATION
   ───────────────────────────────────────────────────── */
async function handleRegisterPatient(event) {
  event.preventDefault();

  const payload = {
    full_name: document.getElementById('reg_name').value.trim(),
    age: document.getElementById('reg_age').value,
    gender: document.getElementById('reg_gender').value,
    blood_group: document.getElementById('reg_blood').value,
    phone: document.getElementById('reg_phone').value.trim(),
    emergency_contact: document.getElementById('reg_emergency').value.trim(),
    address: document.getElementById('reg_address').value.trim(),
    allergies: document.getElementById('reg_allergies').value.trim(),
    chronic_diseases: document.getElementById('reg_chronic').value.trim()
  };

  const submitBtn = event.target.querySelector('[type="submit"]');
  const originalHtml = submitBtn.innerHTML;
  submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
  submitBtn.disabled = true;

  try {
    const res = await fetch('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.status === 'success') {
      showToast(`Patient Registered! ID: ${data.patient.health_id}`, 'success');
      document.getElementById('addPatientForm').reset();
      closeRegisterPatientModal();
      
      // Auto-load details into search input and show profile
      document.getElementById('searchInput').value = data.patient.health_id;
      executeFetchPatient(data.patient.health_id);
      
      // Update statistics
      fetchDashboardStats();
      loadAllDropdowns();
    } else {
      showToast(data.message || 'Error registering patient', 'danger');
    }
  } catch (err) {
    showToast('Failed to connect to local database server', 'danger');
  } finally {
    submitBtn.innerHTML = originalHtml;
    submitBtn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────
   ADD VISIT RECORDS
   ───────────────────────────────────────────────────── */
async function handleAddRecord(event) {
  event.preventDefault();

  const payload = {
    health_id: document.getElementById('rec_health_id').value.trim(),
    hospital_name: document.getElementById('rec_hospital').value.trim(),
    visit_date: document.getElementById('rec_date').value,
    symptoms: document.getElementById('rec_symptoms').value.trim(),
    diagnosis: document.getElementById('rec_diagnosis').value.trim(),
    prescription: document.getElementById('rec_prescription').value.trim(),
    medicines: document.getElementById('rec_medicines').value.trim(),
    blood_pressure: document.getElementById('rec_bp').value.trim(),
    sugar_level: document.getElementById('rec_sugar').value.trim(),
    lab_report: document.getElementById('rec_lab').value.trim(),
    notes: document.getElementById('rec_notes').value.trim()
  };

  const submitBtn = event.target.querySelector('[type="submit"]');
  const originalHtml = submitBtn.innerHTML;
  submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
  submitBtn.disabled = true;

  try {
    const res = await fetch('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.status === 'success') {
      showToast('Record saved successfully!', 'success');
      closeAddRecordModal();
      document.getElementById('addRecordForm').reset();
      document.getElementById('rec_date').value = new Date().toISOString().split('T')[0];
      
      // Refresh current searched profile
      executeFetchPatient(payload.health_id);
      fetchDashboardStats();
    } else {
      showToast(data.message || 'Error saving record', 'danger');
    }
  } catch (err) {
    showToast('Failed to save record', 'danger');
  } finally {
    submitBtn.innerHTML = originalHtml;
    submitBtn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────
   SEARCH PATIENT LOGIC
   ───────────────────────────────────────────────────── */
function performPatientSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) {
    showToast('Please enter a Health ID or Name to search', 'warning');
    return;
  }
  triggerConsentAndSearch(query);
}

function triggerConsentAndSearch(identifier) {
  pendingSearchHealthId = identifier;
  document.getElementById('consentHealthIdDisplay').textContent = identifier.toUpperCase();
  document.getElementById('consentModal').classList.add('active');
}

function closeConsentModal() {
  document.getElementById('consentModal').classList.remove('active');
  if (pendingSearchHealthId) {
    showSkeletonLoader();
    executeFetchPatient(pendingSearchHealthId);
  }
}

function showSkeletonLoader() {
  const results = document.getElementById('searchResultsArea');
  const skeleton = document.getElementById('searchSkeletonLoader');
  if (results) results.style.display = 'none';
  if (skeleton) skeleton.style.display = 'block';
}

function hideSkeletonLoader() {
  const skeleton = document.getElementById('searchSkeletonLoader');
  if (skeleton) skeleton.style.display = 'none';
}

async function executeFetchPatient(identifier) {
  try {
    const res = await fetch(`/api/patients/${encodeURIComponent(identifier)}`);
    const data = await res.json();
    hideSkeletonLoader();

    if (data.status === 'success') {
      activePatientData = data.patient;
      
      // Cache allergies
      patientAllergiesCache = [];
      if (data.patient.allergies && data.patient.allergies.toLowerCase() !== 'none') {
        patientAllergiesCache = data.patient.allergies.split(',').map(a => a.trim().toUpperCase());
      }
      
      renderPatientSearchResults(data.patient);
      fetchRiskAlerts(data.patient.health_id);
    } else {
      showToast(data.message || 'Patient not found', 'danger');
      document.getElementById('searchResultsArea').style.display = 'none';
      patientAllergiesCache = [];
    }
  } catch (err) {
    hideSkeletonLoader();
    showToast('Error searching patient database', 'danger');
    patientAllergiesCache = [];
  }
}

/* ─────────────────────────────────────────────────────
   RENDER ONE PATIENT PROFILE (LIGHT THEME)
   ───────────────────────────────────────────────────── */
function renderPatientSearchResults(patient) {
  document.getElementById('searchResultsArea').style.display = 'block';

  // Reset tab selection to Overview
  switchProfileTab('overview');

  // Set Back Navigation name
  const backNameEl = document.getElementById('backNameDisplay');
  if (backNameEl) {
    backNameEl.textContent = patient.full_name.split(' ')[0];
  }

  // Render hero overview details
  document.getElementById('searchName').textContent = patient.full_name;
  document.getElementById('searchAgeGender').textContent = `${patient.age} years • ${patient.gender} • ${patient.blood_group}`;
  document.getElementById('searchBlood').textContent = patient.blood_group;
  document.getElementById('searchHealthId').textContent = patient.health_id;

  // Render Mini QR code
  const qrBox = document.getElementById('qrcode-mini');
  if (qrBox) {
    qrBox.innerHTML = '';
    new QRCode(qrBox, { text: patient.health_id, width: 44, height: 44, colorDark: '#0F172A', colorLight: '#ffffff' });
  }

  // Demographic details card fields matching mockup IDs
  const bloodElDet = document.getElementById('profileDetBlood');
  const ageElDet = document.getElementById('profileDetAge');
  const genElDet = document.getElementById('profileDetGender');
  const phoneElDet = document.getElementById('profileDetPhone');
  const emergElDet = document.getElementById('profileDetEmergency');

  if (bloodElDet) bloodElDet.textContent = patient.blood_group;
  if (ageElDet) ageElDet.textContent = patient.age;
  if (genElDet) genElDet.textContent = patient.gender;
  if (phoneElDet) phoneElDet.textContent = patient.phone || 'N/A';
  if (emergElDet) emergElDet.textContent = patient.emergency_contact || 'None';

  // Active Medicines list
  const activeMeds = document.getElementById('profileActiveMedicines');
  if (activeMeds) {
    let meds = [];
    if (patient.records) {
      patient.records.forEach(r => {
        if (r.medicines) {
          r.medicines.split(',').forEach(m => {
            let med = m.trim();
            if (med && !meds.includes(med)) meds.push(med);
          });
        }
      });
    }
    if (meds.length > 0) {
      activeMeds.innerHTML = meds.map(m => `<span class="med-tag"><i class="fa-solid fa-pills"></i> ${m}</span>`).join('');
    } else {
      activeMeds.innerHTML = `<span style="color:var(--text-dim); font-size:0.87rem;">No active medications recorded.</span>`;
    }
  }

  // Vitals logs and lab reports
  const bpEl = document.getElementById('profileLatestBp');
  const sugarEl = document.getElementById('profileLatestGlucose');
  const labTableBody = document.querySelector('#profileLabTable tbody');
  
  let latestBp = '--';
  let latestSugar = '--';
  if (patient.records && patient.records.length > 0) {
    latestBp = patient.records[0].blood_pressure || '--';
    latestSugar = patient.records[0].sugar_level || '--';
  }
  if (bpEl) bpEl.textContent = latestBp;
  if (sugarEl) sugarEl.textContent = latestSugar;

  if (labTableBody) {
    if (patient.records && patient.records.length > 0) {
      labTableBody.innerHTML = patient.records.map(r => `
        <tr>
          <td><span class="badge badge-secondary">${r.visit_date}</span></td>
          <td><strong>${r.blood_pressure || 'N/A'}</strong></td>
          <td><strong>${r.sugar_level || 'N/A'}</strong></td>
          <td style="color:var(--text-muted); font-size:0.85rem;">${r.lab_report || 'N/A'}</td>
        </tr>`).join('');
    } else {
      labTableBody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-dim);">No lab records found.</td></tr>`;
    }
  }

  // Visit history timeline feed
  const timelineContainer = document.getElementById('patientVisitsList');
  if (!patient.records || patient.records.length === 0) {
    timelineContainer.innerHTML = `
      <div class="timeline-item">
        <span class="bullet"></span>
        <div class="timeline-details">
          <p>No historical clinical visits recorded for this patient.</p>
        </div>
      </div>`;
  } else {
    timelineContainer.innerHTML = patient.records.map((rec, i) => `
      <div class="timeline-item">
        <span class="bullet"></span>
        <div class="timeline-header">
          <strong>${rec.visit_date} — ${rec.hospital_name}</strong>
        </div>
        <div class="timeline-details">
          <p><strong>Primary Diagnosis:</strong> <span style="color:var(--primary); font-weight:600;">${rec.diagnosis}</span></p>
          <p><strong>Prescribed Medicines:</strong> <span class="text-success">${rec.medicines || 'None'}</span></p>
          <p><strong>Dosage Instruction:</strong> ${rec.prescription || 'N/A'}</p>
          <p><strong>Symptoms Reported:</strong> ${rec.symptoms || 'N/A'}</p>
          ${rec.notes ? `<p class="clinical-notes"><em>Remarks:</em> "${rec.notes}"</p>` : ''}
        </div>
      </div>`).join('');
  }

  // Double-render Timeline to the focused history tab list
  const timelineSecondary = document.getElementById('patientVisitsListSecondary');
  if (timelineSecondary) {
    timelineSecondary.innerHTML = timelineContainer.innerHTML;
  }

  // Hide AI summary initially in tabs
  const profileAiBox = document.getElementById('profileAiSummaryBox');
  if (profileAiBox) profileAiBox.style.display = 'none';
  const profileAiBoxSec = document.getElementById('profileAiSummaryBoxSecondary');
  if (profileAiBoxSec) profileAiBoxSec.style.display = 'none';

  // Role Security restrictions
  const isRecep = (currentRole === 'receptionist');
  const sensitiveTabBtns = [
    document.getElementById('tabBtnHistory'),
    document.getElementById('tabBtnMedicines'),
    document.getElementById('tabBtnLabs'),
    document.getElementById('tabBtnAi')
  ].filter(Boolean);
  
  sensitiveTabBtns.forEach(btn => {
    btn.style.display = isRecep ? 'none' : 'inline-block';
  });

  const alertsCol = document.querySelector('.danger-card');
  if (alertsCol) alertsCol.style.display = isRecep ? 'none' : 'block';
  
  const timelineCard = document.querySelector('.timeline-card');
  if (timelineCard) timelineCard.style.display = isRecep ? 'none' : 'block';
  
  const aiAssistantBlock = document.querySelector('.ai-assistant-block');
  if (aiAssistantBlock) aiAssistantBlock.style.display = isRecep ? 'none' : 'block';
}

function switchProfileTab(tabName) {
  // Hide all panels
  document.querySelectorAll('.profile-tab-panel').forEach(p => p.classList.remove('active'));
  // Deactivate all buttons
  document.querySelectorAll('.profile-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  
  // Show target panel
  if (tabName === 'overview') {
    document.getElementById('profileTabOverview').classList.add('active');
    document.getElementById('tabBtnOverview').classList.add('active');
  } else if (tabName === 'history') {
    document.getElementById('profileTabHistory').classList.add('active');
    document.getElementById('tabBtnHistory').classList.add('active');
  } else if (tabName === 'medicines') {
    document.getElementById('profileTabMedicines').classList.add('active');
    document.getElementById('tabBtnMedicines').classList.add('active');
  } else if (tabName === 'labs') {
    document.getElementById('profileTabLabs').classList.add('active');
    document.getElementById('tabBtnLabs').classList.add('active');
  } else if (tabName === 'docs') {
    document.getElementById('profileTabDocs').classList.add('active');
    document.getElementById('tabBtnDocs').classList.add('active');
    if (activePatientData) {
      fetchMockDocuments(activePatientData.health_id);
    }
  } else if (tabName === 'ai') {
    document.getElementById('profileTabAi').classList.add('active');
    document.getElementById('tabBtnAi').classList.add('active');
  }
}

/* ─────────────────────────────────────────────────────
   RISK ALERTS (API CONTROLLERS)
   ───────────────────────────────────────────────────── */
async function fetchRiskAlerts(healthId) {
  const container = document.getElementById('riskAlertsContainer');
  if (!container) return;
  try {
    const res = await fetch(`/api/ai/risk-alerts/${healthId}`);
    const data = await res.json();

    if (data.status === 'success' && data.alerts && data.alerts.length > 0) {
      container.innerHTML = data.alerts.map(a => `
        <div class="risk-card ${a.type}">
          <i class="fa-solid ${a.icon}"></i>
          <div>
            <strong>${a.title}</strong>
            <span>${a.description}</span>
          </div>
        </div>`).join('');
    } else {
      container.innerHTML = `<div class="risk-card info"><i class="fa-solid fa-circle-info"></i> No risk flags detected.</div>`;
    }
  } catch {
    container.innerHTML = '';
  }
}

/* ─────────────────────────────────────────────────────
   AI ASSISTANT TRIGGERS & STAR PLAYGROUND
   ───────────────────────────────────────────────────── */
function runAiSummaryForAssistant() {
  const select = document.getElementById('aiAssistantPatientSelect');
  if (!select || !select.value) {
    showToast('Please select a patient first', 'warning');
    return;
  }
  
  // Hide explainer, show summary
  document.getElementById('aiResultPlaceholder').style.display = 'none';
  document.getElementById('aiExplainOutput').style.display = 'none';
  
  const summaryOutput = document.getElementById('aiSummaryOutput');
  const summaryList = document.getElementById('aiSummaryList');
  summaryOutput.style.display = 'block';
  summaryList.innerHTML = `<li><i class="fa-solid fa-spinner fa-spin text-primary"></i> Compiling clinical summary...</li>`;

  executeAiSummary(select.value, summaryList);
}

function openAddRecordModalFromAi() {
  const select = document.getElementById('aiAssistantPatientSelect');
  if (select && select.value) {
    document.getElementById('rec_health_id').value = select.value;
  }
  openAddRecordModal();
}

function loadJargonExplainerTool() {
  document.getElementById('aiResultPlaceholder').style.display = 'none';
  document.getElementById('aiSummaryOutput').style.display = 'none';
  document.getElementById('aiExplainOutput').style.display = 'none';
  
  document.getElementById('aiJargonExplainerWrapper').style.display = 'block';
}

async function triggerExplainJargon() {
  const text = document.getElementById('ai_explain_input').value.trim();
  if (!text) {
    showToast('Please enter a term to explain', 'warning');
    return;
  }

  const output = document.getElementById('aiExplainOutput');
  const textEl = document.getElementById('aiExplainText');
  document.getElementById('aiJargonExplainerWrapper').style.display = 'none';
  output.style.display = 'block';
  textEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-warning"></i> Translating terminology...`;

  try {
    const res = await fetch('/api/ai/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.status === 'success') {
      textEl.textContent = data.simplified_explanation;
    }
  } catch {
    textEl.textContent = 'Translation engine offline.';
  }
}

async function runProfileAiSummary() {
  if (!activePatientData) return;
  const box1 = document.getElementById('profileAiSummaryBox');
  const list1 = document.getElementById('profileAiSummaryList');
  const box2 = document.getElementById('profileAiSummaryBoxSecondary');
  const list2 = document.getElementById('profileAiSummaryListSecondary');
  
  if (box1) box1.style.display = 'block';
  if (box2) box2.style.display = 'block';
  
  const loaderHtml = `<li><i class="fa-solid fa-spinner fa-spin text-ai"></i> Running AI summaries...</li>`;
  if (list1) list1.innerHTML = loaderHtml;
  if (list2) list2.innerHTML = loaderHtml;
  
  try {
    const res = await fetch('/api/ai/summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ health_id: activePatientData.health_id })
    });
    const data = await res.json();

    if (data.status === 'success' && data.summary) {
      const summaryHtml = data.summary.map(b => `<li>${formatMarkdownText(b)}</li>`).join('');
      if (list1) list1.innerHTML = summaryHtml;
      if (list2) list2.innerHTML = summaryHtml;
      showToast('AI Summary generated successfully!', 'success');
    } else {
      const errHtml = `<li style="color:var(--danger);">${data.message || 'Error generating summary'}</li>`;
      if (list1) list1.innerHTML = errHtml;
      if (list2) list2.innerHTML = errHtml;
    }
  } catch {
    const errHtml = `<li style="color:var(--danger);">AI engine unavailable</li>`;
    if (list1) list1.innerHTML = errHtml;
    if (list2) list2.innerHTML = errHtml;
  }
}

async function executeAiSummary(healthId, listElement) {
  try {
    const res = await fetch('/api/ai/summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ health_id: healthId })
    });
    const data = await res.json();

    if (data.status === 'success' && data.summary) {
      listElement.innerHTML = data.summary.map(b => `<li>${formatMarkdownText(b)}</li>`).join('');
      showToast('AI Summary generated successfully!', 'success');
    } else {
      listElement.innerHTML = `<li style="color:var(--danger);">${data.message || 'Error generating summary'}</li>`;
    }
  } catch {
    listElement.innerHTML = `<li style="color:var(--danger);">AI engine unavailable</li>`;
  }
}

async function triggerDrugCheck() {
  const medicines = document.getElementById('ai_drug_input').value.trim();
  if (!medicines) {
    showToast('Please enter medicines to check', 'warning');
    return;
  }

  const output = document.getElementById('aiDrugOutput');
  output.style.display = 'block';
  output.innerHTML = `<div class="glass-card"><i class="fa-solid fa-spinner fa-spin text-success"></i> Checking interactions...</div>`;

  try {
    const res = await fetch('/api/ai/drug-check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ medicines })
    });
    const data = await res.json();

    if (data.status === 'success' && data.interactions) {
      output.innerHTML = data.interactions.map(item => {
        let cardClass = 'info';
        let icon = 'fa-circle-check';
        if (item.severity.includes('HIGH')) { cardClass = 'danger'; icon = 'fa-triangle-exclamation'; }
        else if (item.severity.includes('MODERATE')) { cardClass = 'warning'; icon = 'fa-triangle-exclamation'; }

        return `
          <div class="risk-card ${cardClass}" style="margin-top:10px;">
            <i class="fa-solid ${icon}"></i>
            <div>
              <strong>${item.combination} — [${item.severity}]</strong>
              <span>${item.note}</span>
            </div>
          </div>`;
      }).join('');
    }
  } catch {
    output.innerHTML = `<div class="risk-card danger">Failed to evaluate drug interactions.</div>`;
  }
}

/* ─────────────────────────────────────────────────────
   LIVE SAFETY ALERT VALIDATOR
   ───────────────────────────────────────────────────── */
function checkLivePrescriptionAllergies() {
  const medInput = document.getElementById('rec_medicines').value.trim();
  const warningContainer = document.getElementById('livePrescriptionWarning');
  const warningText = document.getElementById('livePrescriptionWarningText');
  
  if (!medInput || patientAllergiesCache.length === 0) {
    warningContainer.style.display = 'none';
    return;
  }
  
  const typedMeds = medInput.split(/[,+\n&]/).map(m => m.trim().toUpperCase()).filter(Boolean);
  
  let triggeredAllergy = null;
  let triggeredMed = null;
  
  for (let typed of typedMeds) {
    for (let allergy of patientAllergiesCache) {
      if (typed.includes(allergy) || allergy.includes(typed)) {
        triggeredAllergy = allergy;
        triggeredMed = typed;
        break;
      }
    }
    if (triggeredAllergy) break;
  }
  
  if (triggeredAllergy) {
    warningText.innerHTML = `This medication (<strong>${triggeredMed}</strong>) may require review because a severe allergy (<strong>${triggeredAllergy}</strong>) is recorded for this patient.`;
    warningContainer.style.display = 'flex';
  } else {
    warningContainer.style.display = 'none';
  }
}

/* ─────────────────────────────────────────────────────
   ROLE AUTHORIZATION & SECURITY CONTROLLERS
   ───────────────────────────────────────────────────── */
async function checkAuthSession() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.status === 'success') {
      currentRole = data.user.role;
      document.getElementById('loginView').style.display = 'none';
      document.getElementById('landingView').style.display = 'none';
      document.getElementById('dashboardLayout').style.display = 'flex';
      
      const navUserRole = document.getElementById('navUserRole');
      const dashWelcomeName = document.getElementById('dashWelcomeName');
      if (navUserRole) navUserRole.textContent = data.user.full_name;
      if (dashWelcomeName) dashWelcomeName.textContent = data.user.full_name;
      
      applyRoleSecurityFilters(currentRole);
      
      fetchAppointments();
      fetchAuditLogs();
    }
  } catch (e) {}
}

function quickFillLogin(username, password) {
  const userField = document.getElementById('login_username');
  const passField = document.getElementById('login_password');
  if (userField) userField.value = username;
  if (passField) passField.value = password;
  showToast(`Quick-filled credentials for ${username}!`, 'info');
}

async function handleFormLogin(event) {
  if (event) event.preventDefault();
  const username = document.getElementById('login_username').value.trim();
  const password = document.getElementById('login_password').value.trim();
  
  if (!username || !password) {
    showToast('Username and password required', 'warning');
    return;
  }
  
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username, password})
    });
    const data = await res.json();
    
    if (data.status === 'success') {
      currentRole = data.user.role;
      selectRole(currentRole, data.user.full_name);
    } else {
      showToast(data.message || 'Login failed', 'danger');
    }
  } catch {
    showToast('Authentication server offline', 'danger');
  }
}

function selectRole(role, fullName) {
  currentRole = role;
  
  document.getElementById('loginView').style.display = 'none';
  document.getElementById('dashboardLayout').style.display = 'flex';
  
  const navUserRole = document.getElementById('navUserRole');
  const dashWelcomeName = document.getElementById('dashWelcomeName');
  
  const userDetails = {
    admin: { name: 'System Admin', avatar: 'AD' },
    doctor: { name: 'Dr. Alexander', avatar: 'DR' },
    nurse: { name: 'Nurse Sarah', avatar: 'NU' },
    receptionist: { name: 'Receptionist Emma', avatar: 'RE' }
  };
  
  const name = fullName || userDetails[role]?.name || role.toUpperCase();
  if (navUserRole) navUserRole.textContent = name;
  if (dashWelcomeName) dashWelcomeName.textContent = name;
  
  applyRoleSecurityFilters(role);
  
  showDashboardSection('view-dashboard', document.querySelector('.sidebar-menu .nav-link'));
  
  fetchAppointments();
  fetchAuditLogs();
  
  showToast(`Session authenticated as ${role.toUpperCase()}`, 'success');
}

async function logoutRole(event) {
  if (event) event.preventDefault();
  try {
    await fetch('/api/auth/logout', {method: 'POST'});
  } catch(e) {}
  currentRole = null;
  document.getElementById('dashboardLayout').style.display = 'none';
  document.getElementById('loginView').style.display = 'none';
  document.getElementById('landingView').style.display = 'flex';
  showToast('Logged out successfully', 'info');
}

function applyRoleSecurityFilters(role) {
  const sidebarLinks = document.querySelectorAll('.sidebar-menu .nav-link');
  if (sidebarLinks.length === 0) return;
  
  // Menu mapping indices:
  // 0: Dashboard (Always)
  // 1: Patients (Always, but search view limited for Receptionist)
  // 2: Appointments (Always)
  // 3: Medicines (Visible to: admin, doctor)
  // 4: Labs (Visible to: admin, doctor, nurse)
  // 5: AI Assistant (Visible to: admin, doctor)
  // 6: Analytics (Visible to: admin, doctor)
  // 7: Access Logs (Visible to: admin)
  // 8: Settings (Always)
  
  sidebarLinks.forEach((link, idx) => {
    if (idx === 0 || idx === 1 || idx === 2 || idx === 8) {
      link.style.display = 'flex';
      return;
    }
    
    let isVisible = false;
    if (role === 'admin') {
      isVisible = true;
    } else if (role === 'doctor') {
      isVisible = (idx === 3 || idx === 4 || idx === 5 || idx === 6);
    } else if (role === 'nurse') {
      isVisible = (idx === 4);
    } else if (role === 'receptionist') {
      isVisible = false;
    }
    
    link.style.display = isVisible ? 'flex' : 'none';
  });

  // Hide button options in Patient view for Receptionists
  const btnAddRecord = document.getElementById('btnAddRecordBtn');
  if (btnAddRecord) {
    btnAddRecord.style.display = (role === 'receptionist') ? 'none' : 'inline-block';
  }
}

function toggleRoleDropdown(event) {
  event.stopPropagation();
  const dd = document.getElementById('navRoleDropdown');
  if (dd) {
    dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
  }
}

// Close dropdown on viewport clicks
document.addEventListener('click', () => {
  const dd = document.getElementById('navRoleDropdown');
  if (dd) dd.style.display = 'none';
});

function changeRoleDirect(role, event) {
  if (event) event.preventDefault();
  selectRole(role);
  const dd = document.getElementById('navRoleDropdown');
  if (dd) dd.style.display = 'none';
}

function logoutRole(event) {
  if (event) event.preventDefault();
  currentRole = null;
  patientAllergiesCache = [];
  document.getElementById('dashboardLayout').style.display = 'none';
  switchView('dashboardLayout', 'loginView');
  showToast('Logged out of workspace session', 'info');
}

/* ─────────────────────────────────────────────────────
   QR CODE CONTROLLERS
   ───────────────────────────────────────────────────── */
function showQrModalForCurrentPatient() {
  if (activePatientData) {
    showQrModal(activePatientData.full_name, activePatientData.health_id);
  }
}

function showQrModal(name, healthId) {
  document.getElementById('qrModalName').textContent = name;
  document.getElementById('qrModalHealthId').textContent = healthId;

  const qrContainer = document.getElementById('qrcode');
  qrContainer.innerHTML = '';

  if (window.QRCode) {
    new QRCode(qrContainer, {
      text: healthId,
      width: 180,
      height: 180,
      colorDark: '#0B1120',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.H
    });
  } else {
    qrContainer.innerHTML = `<p>[QR: ${healthId}]</p>`;
  }

  document.getElementById('qrModal').classList.add('active');
  showToast('QR Code Generated!', 'success');
}

function closeQrModal() {
  document.getElementById('qrModal').classList.remove('active');
}

function downloadQrCode() {
  const canvas = document.querySelector('#qrcode canvas');
  if (!canvas) { showToast('QR code not ready', 'warning'); return; }
  const link = document.createElement('a');
  link.download = `MediLink-QR-${document.getElementById('qrModalHealthId').textContent}.png`;
  link.href = canvas.toDataURL('image/png');
  link.click();
  showToast('QR Code Downloaded!', 'success');
}

function printQrCode() {
  const canvas = document.querySelector('#qrcode canvas');
  if (!canvas) { showToast('QR code not ready', 'warning'); return; }
  const name = document.getElementById('qrModalName').textContent;
  const healthId = document.getElementById('qrModalHealthId').textContent;
  const dataURL = canvas.toDataURL('image/png');
  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <html>
    <head>
      <title>MediLink QR – ${healthId}</title>
      <style>
        body { font-family: 'Inter', sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:100vh; margin:0; background:#fff; }
        img { border: 1px solid #ddd; padding:10px; border-radius:8px; }
      </style>
    </head>
    <body>
      <h2>${name}</h2>
      <p>Health ID: <strong>${healthId}</strong></p>
      <img src="${dataURL}">
    </body>
    </html>`);
  printWindow.document.close();
  printWindow.print();
}

async function shareQrCode() {
  const healthId = document.getElementById('qrModalHealthId').textContent;
  const name = document.getElementById('qrModalName').textContent;
  if (navigator.share) {
    try {
      await navigator.share({
        title: `Health ID: ${name}`,
        text: `MediLink Health ID: ${healthId}`,
        url: window.location.href
      });
      showToast('Shared successfully!', 'success');
    } catch {
      fallbackCopyShare(healthId);
    }
  } else {
    fallbackCopyShare(healthId);
  }
}
function fallbackCopyShare(healthId) {
  navigator.clipboard.writeText(healthId).then(() => {
    showToast(`Health ID ${healthId} copied to clipboard!`, 'success');
  });
}

/* ─────────────────────────────────────────────────────
   TOAST CONTROLLER
   ───────────────────────────────────────────────────── */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = { success: 'fa-circle-check', danger: 'fa-circle-xmark', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
  const colors = { success: '#10B981', danger: '#EF4444', warning: '#F59E0B', info: '#0F52BA' };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i class="fa-solid ${icons[type]}" style="color:${colors[type]}; font-size:1.1rem; flex-shrink:0;"></i>
    <span style="flex:1;">${message}</span>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:0.9rem;">
      <i class="fa-solid fa-xmark"></i>
    </button>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ─────────────────────────────────────────────────────
   PARTICLES CONTROLLER (LIGHT THEME)
   ───────────────────────────────────────────────────── */
function initParticles() {
  // Silent fallback for light layout particles
}

function initLoginParticles() {
  const canvas = document.getElementById('loginParticlesCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let particles = [];
  let W = canvas.width = window.innerWidth;
  let H = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  });

  function createParticle() {
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 2 + 0.5,
      dx: (Math.random() - 0.5) * 0.3,
      dy: (Math.random() - 0.5) * 0.3,
      life: Math.random()
    };
  }

  for (let i = 0; i < 40; i++) particles.push(createParticle());

  function drawParticles() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => {
      p.x += p.dx;
      p.y += p.dy;
      p.life += 0.002;
      if (p.x < 0 || p.x > W || p.y < 0 || p.y > H) {
        Object.assign(p, createParticle());
      }
      const opacity = Math.abs(Math.sin(p.life)) * 0.4;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(15, 82, 186, ${opacity})`;
      ctx.fill();
    });
    requestAnimationFrame(drawParticles);
  }
  drawParticles();
}

/* ─────────────────────────────────────────────────────
   TEXT MARKDOWN FORMATTER
   ───────────────────────────────────────────────────── */
function formatMarkdownText(txt) {
  return txt
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>');
}

/* ─────────────────────────────────────────────────────
   BELL NOTIFICATIONS CONTROLLER
   ───────────────────────────────────────────────────── */
function toggleNotifDropdown(event) {
  if (event) event.stopPropagation();
  const dropdown = document.getElementById('notifDropdown');
  if (!dropdown) return;
  const isHidden = dropdown.style.display === 'none';
  dropdown.style.display = isHidden ? 'block' : 'none';
}

// Close notifications when clicking elsewhere
document.addEventListener('click', () => {
  const dropdown = document.getElementById('notifDropdown');
  if (dropdown) dropdown.style.display = 'none';
  const roleDropdown = document.getElementById('navRoleDropdown');
  if (roleDropdown) roleDropdown.style.display = 'none';
});

/* ─────────────────────────────────────────────────────
   APPOINTMENTS CONTROLLER & QUEUE MANAGEMENT
   ───────────────────────────────────────────────────── */
async function fetchAppointments() {
  try {
    const res = await fetch('/api/appointments');
    const data = await res.json();
    if (data.status === 'success') {
      renderAppointmentsTable(data.appointments);
    }
  } catch (err) {
    console.error("Error fetching appointments:", err);
  }
}

function renderAppointmentsTable(appts) {
  const tbody = document.querySelector('#appointmentsTable tbody');
  if (!tbody) return;
  
  if (appts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-dim);">No appointments booked for today.</td></tr>`;
    return;
  }
  
  const isRecep = (currentRole === 'receptionist');
  const isNurse = (currentRole === 'nurse');
  
  tbody.innerHTML = appts.map(a => {
    let statusClass = 'pending';
    if (a.status === 'Confirmed') statusClass = 'confirmed';
    if (a.status === 'Completed') statusClass = 'confirmed'; // Green
    if (a.status === 'Cancelled') statusClass = 'danger'; // Red
    
    // Actions visibility based on roles
    let actionButtons = '';
    if (a.status === 'Confirmed' || a.status === 'Waiting') {
      if (isRecep) {
        actionButtons = `
          <button class="btn btn-secondary btn-sm" onclick="triggerReschedule(${a.id})">Reschedule</button>
          <button class="btn btn-secondary btn-sm" style="color:var(--danger); border-color:var(--danger);" onclick="updateApptStatus(${a.id}, 'cancel')">Cancel</button>
        `;
      } else if (!isNurse) { // Admin or Doctor
        actionButtons = `
          <button class="btn btn-primary btn-sm" onclick="updateApptStatus(${a.id}, 'complete')">Complete</button>
          <button class="btn btn-secondary btn-sm" onclick="triggerReschedule(${a.id})">Reschedule</button>
          <button class="btn btn-secondary btn-sm" style="color:var(--danger);" onclick="updateApptStatus(${a.id}, 'cancel')">Cancel</button>
        `;
      } else {
        actionButtons = `<span style="color:var(--text-dim);font-size:0.8rem;">View only</span>`;
      }
    } else {
      actionButtons = `<span class="badge badge-secondary">${a.status}</span>`;
    }
    
    return `
      <tr>
        <td>
          <a href="#" onclick="lookupPatientDirect('${a.patient_health_id}', event)" style="font-weight:700; color:var(--primary);">
            ${a.patient_name}
          </a>
          <br><small style="color:var(--text-dim); font-size:0.75rem;">${a.patient_health_id}</small>
        </td>
        <td><strong>${a.time_slot}</strong></td>
        <td>Dr. ${a.doctor_name.replace('Dr. ', '')}</td>
        <td><span class="badge badge-primary">${a.department}</span></td>
        <td><span class="status ${statusClass}">${a.status}</span></td>
        <td>
          <div style="display:flex; gap:0.35rem; align-items:center;">
            ${actionButtons}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function lookupPatientDirect(healthId, event) {
  if (event) event.preventDefault();
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.value = healthId;
  showDashboardSection('view-patients', document.querySelector('.sidebar-menu .nav-link:nth-child(2)'));
  performPatientSearch();
}

function openBookApptModal() {
  document.getElementById('bookApptModal').classList.add('active');
}

function closeBookApptModal() {
  document.getElementById('bookApptModal').classList.remove('active');
  document.getElementById('bookApptForm').reset();
}

async function fetchPatientNameForAppt(healthId) {
  if (!healthId.trim()) return;
  try {
    const res = await fetch(`/api/patients/${encodeURIComponent(healthId.trim())}`);
    const data = await res.json();
    if (data.status === 'success') {
      document.getElementById('appt_patient_name').value = data.patient.full_name;
    } else {
      document.getElementById('appt_patient_name').value = '';
      showToast('Patient not registered. Register demographics first.', 'warning');
    }
  } catch {
    document.getElementById('appt_patient_name').value = '';
  }
}

function populateDoctorsForDept(dept) {
  const select = document.getElementById('appt_doctor');
  if (!select) return;
  select.innerHTML = '<option value="" disabled selected hidden></option>';
  
  const docs = {
    'Cardiology': ['Dr. Kumar', 'Dr. Sharma'],
    'General Medicine': ['Dr. Alexander', 'Dr. Ravi'],
    'Pediatrics': ['Dr. Alexander', 'Dr. Sinha'],
    'Neurology': ['Dr. Kumar', 'Dr. Mehta']
  };
  
  if (docs[dept]) {
    select.innerHTML += docs[dept].map(d => `<option value="${d}">${d}</option>`).join('');
  }
}

async function handleBookAppointment(event) {
  if (event) event.preventDefault();
  const patient_health_id = document.getElementById('appt_health_id').value.trim();
  const patient_name = document.getElementById('appt_patient_name').value.trim();
  const time_slot = document.getElementById('appt_time').value;
  const department = document.getElementById('appt_dept').value;
  const doctor_name = document.getElementById('appt_doctor').value;
  
  if (!patient_name) {
    showToast('Valid patient ID required.', 'warning');
    return;
  }
  
  try {
    const res = await fetch('/api/appointments', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({patient_health_id, patient_name, time_slot, department, doctor_name})
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      closeBookApptModal();
      fetchAppointments();
    } else {
      showToast(data.message, 'danger');
    }
  } catch {
    showToast('Failed to book appointment', 'danger');
  }
}

async function updateApptStatus(apptId, action) {
  try {
    const res = await fetch(`/api/appointments/${apptId}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action})
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      fetchAppointments();
    } else {
      showToast(data.message, 'danger');
    }
  } catch {
    showToast('Failed to update status', 'danger');
  }
}

function triggerReschedule(apptId) {
  const newTime = prompt("Enter new timeslot (e.g. 11:30 AM, 02:00 PM):");
  if (!newTime) return;
  
  const timeRegex = /^(0[1-9]|1[0-2]):[0-5][0-9]\s(AM|PM)$/i;
  if (!timeRegex.test(newTime.trim())) {
    showToast("Invalid timeslot format. Use 'HH:MM AM/PM' (e.g. 11:30 AM)", "warning");
    return;
  }
  
  updateRescheduledTime(apptId, newTime.trim());
}

async function updateRescheduledTime(apptId, time_slot) {
  try {
    const res = await fetch(`/api/appointments/${apptId}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'reschedule', time_slot})
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      fetchAppointments();
    } else {
      showToast(data.message, 'danger');
    }
  } catch {
    showToast('Failed to reschedule', 'danger');
  }
}

/* ─────────────────────────────────────────────────────
   AUDIT LOGGER ACTION TRACKING
   ───────────────────────────────────────────────────── */
async function fetchAuditLogs() {
  if (currentRole !== 'admin') return;
  try {
    const res = await fetch('/api/audit-logs');
    const data = await res.json();
    if (data.status === 'success') {
      renderAuditLogsTable(data.audit_logs);
    }
  } catch (err) {
    console.error("Error fetching audit logs:", err);
  }
}

function renderAuditLogsTable(logs) {
  const tbody = document.querySelector('#auditLogsTable tbody');
  if (!tbody) return;
  
  if (logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim);">No access logs available.</td></tr>`;
    return;
  }
  
  tbody.innerHTML = logs.map(l => {
    let actionClass = 'badge-secondary';
    if (l.action === 'LOGIN') actionClass = 'badge-primary';
    if (l.action === 'CREATE_RECORD') actionClass = 'badge-success';
    if (l.action === 'UPDATE_RECORD') actionClass = 'badge-ai';
    if (l.action === 'VIEW_PATIENT') actionClass = 'badge-ai';
    
    return `
      <tr>
        <td><span style="font-size:0.8rem; color:var(--text-muted);">${l.timestamp}</span></td>
        <td><strong>${l.username}</strong></td>
        <td><span class="badge badge-secondary" style="font-size:0.7rem;">${l.role}</span></td>
        <td><span class="badge ${actionClass}" style="font-size:0.72rem;">${l.action}</span></td>
        <td style="color:var(--text-muted); font-size:0.85rem;">${l.details}</td>
      </tr>
    `;
  }).join('');
}

/* ─────────────────────────────────────────────────────
   GLOBAL INDEXED PATIENT SEARCH & RESULTS
   ───────────────────────────────────────────────────── */
async function performPatientSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) {
    showToast('Please enter search query', 'warning');
    return;
  }
  
  if (/^MED-\d{4}-\d{6}$/i.test(query)) {
    closeGlobalSearchResults();
    pendingSearchHealthId = query;
    document.getElementById('consentHealthIdDisplay').textContent = query;
    document.getElementById('consentModal').classList.add('active');
    
    try {
      await fetch('/api/audit-logs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'VIEW_PATIENT', details: `Requested timeline records for ${query}`})
      });
    } catch {}
    return;
  }
  
  const grid = document.getElementById('globalSearchGrid');
  const resultsBox = document.getElementById('globalSearchResults');
  if (resultsBox) resultsBox.style.display = 'block';
  if (grid) grid.innerHTML = `<div style="grid-column: span 4; text-align:center; padding:2rem;"><i class="fa-solid fa-spinner fa-spin text-primary"></i> Querying clinical index...</div>`;
  
  try {
    const res = await fetch(`/api/search/global?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    if (data.status === 'success') {
      renderGlobalSearchResults(data);
    }
  } catch {
    if (grid) grid.innerHTML = `<div style="grid-column: span 4; text-align:center; color:var(--danger);">Failed to search database directory.</div>`;
  }
}

function closeGlobalSearchResults() {
  const resultsBox = document.getElementById('globalSearchResults');
  if (resultsBox) resultsBox.style.display = 'none';
}

function renderGlobalSearchResults(data) {
  const grid = document.getElementById('globalSearchGrid');
  if (!grid) return;
  
  let ptsHtml = `<div><h4>👥 Patients</h4><ul class="ai-bullets" style="padding-left:0; list-style:none;">`;
  if (data.patients.length > 0) {
    ptsHtml += data.patients.map(p => `
      <li style="margin-bottom:0.75rem;">
        <a href="#" onclick="lookupPatientDirect('${p.health_id}', event)" style="font-weight:700; color:var(--primary);">${p.full_name}</a>
        <br><small style="color:var(--text-dim);">${p.health_id} • ${p.age} y/o</small>
      </li>`).join('');
  } else {
    ptsHtml += `<li style="color:var(--text-dim);font-size:0.82rem;">No matching patient demographics.</li>`;
  }
  ptsHtml += `</ul></div>`;
  
  let condsHtml = `<div><h4>🏥 Conditions</h4><ul class="ai-bullets" style="padding-left:0; list-style:none;">`;
  if (data.conditions.length > 0) {
    condsHtml += data.conditions.map(c => `
      <li style="margin-bottom:0.75rem;">
        <strong>${c.name}</strong><br><small style="color:var(--text-muted);">${c.description}</small>
      </li>`).join('');
  } else {
    condsHtml += `<li style="color:var(--text-dim);font-size:0.82rem;">No matching chronic conditions.</li>`;
  }
  condsHtml += `</ul></div>`;
  
  let medsHtml = `<div><h4>💊 Medicines</h4><ul class="ai-bullets" style="padding-left:0; list-style:none;">`;
  if (data.medicines.length > 0) {
    medsHtml += data.medicines.map(m => `
      <li style="margin-bottom:0.75rem;">
        <strong>${m.name}</strong><br><small style="color:var(--text-muted);">${m.category}</small>
        <span class="status ${m.risk === 'High' ? 'danger' : m.risk === 'Moderate' ? 'pending' : 'confirmed'}" style="font-size:0.6rem; padding:0.1rem 0.3rem;">${m.risk} Risk</span>
      </li>`).join('');
  } else {
    medsHtml += `<li style="color:var(--text-dim);font-size:0.82rem;">No matching formulary entries.</li>`;
  }
  medsHtml += `</ul></div>`;
  
  let recsHtml = `<div><h4>📄 Medical Records</h4><ul class="ai-bullets" style="padding-left:0; list-style:none;">`;
  if (data.records.length > 0) {
    recsHtml += data.records.map(r => `
      <li style="margin-bottom:0.75rem;">
        <strong>${r.diagnosis}</strong><br>
        <small style="color:var(--text-muted);">${r.full_name} (${r.visit_date})</small>
        <br><small style="color:var(--text-dim); font-style:italic;">Symptoms: ${r.symptoms || 'None'}</small>
      </li>`).join('');
  } else {
    recsHtml += `<li style="color:var(--text-dim);font-size:0.82rem;">No matching consultation notes.</li>`;
  }
  recsHtml += `</ul></div>`;
  
  grid.innerHTML = ptsHtml + condsHtml + medsHtml + recsHtml;
}

/* ─────────────────────────────────────────────────────
   PATIENT DOCUMENTS ARCHIVE (SIMULATED UPLOADER)
   ───────────────────────────────────────────────────── */
async function fetchMockDocuments(healthId) {
  try {
    const res = await fetch(`/api/patients/${healthId}/documents`);
    const data = await res.json();
    if (data.status === 'success') {
      renderDocumentsTable(healthId, data.documents);
    }
  } catch (err) {
    console.error("Error fetching docs:", err);
  }
}

function renderDocumentsTable(healthId, docs) {
  const tbody = document.querySelector('#profileDocsTable tbody');
  if (!tbody) return;
  
  if (docs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-dim);">No clinical documents uploaded.</td></tr>`;
    return;
  }
  
  tbody.innerHTML = docs.map(d => `
    <tr>
      <td><strong>${d.filename}</strong></td>
      <td>${d.upload_date}</td>
      <td><span class="badge badge-secondary">${d.file_size}</span></td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="viewMockFile('${d.filename}')">View</button>
        <button class="btn btn-secondary btn-sm" onclick="downloadMockFile('${d.filename}')">Download</button>
        <button class="btn btn-secondary btn-sm" style="color:var(--danger); border-color:var(--danger);" onclick="deleteMockDocument('${healthId}', ${d.id})">Delete</button>
      </td>
    </tr>
  `).join('');
}

async function uploadMockDocument() {
  if (!activePatientData) return;
  const select = document.getElementById('mockDocSelect');
  if (!select) return;
  const filename = select.value;
  
  const optionText = select.options[select.selectedIndex].text;
  const sizeMatch = optionText.match(/\((.*?)\)/);
  const file_size = sizeMatch ? sizeMatch[1] : '150 KB';
  
  try {
    const res = await fetch(`/api/patients/${activePatientData.health_id}/documents`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({filename, file_size})
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      fetchMockDocuments(activePatientData.health_id);
    } else {
      showToast(data.message, 'danger');
    }
  } catch {
    showToast('Failed to upload document', 'danger');
  }
}

async function deleteMockDocument(healthId, docId) {
  if (!confirm("Are you sure you want to delete this document?")) return;
  try {
    const res = await fetch(`/api/patients/${healthId}/documents/${docId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      fetchMockDocuments(healthId);
    } else {
      showToast(data.message, 'danger');
    }
  } catch {
    showToast('Failed to delete document', 'danger');
  }
}

function viewMockFile(filename) {
  alert(`Viewing simulated file '${filename}' in hospital sandboxed pdf viewer.`);
}

function downloadMockFile(filename) {
  showToast(`Downloading file: ${filename}`, 'success');
}

/* ─────────────────────────────────────────────────────
   PRINTABLE CLINICAL REPORT SUMMARY
   ───────────────────────────────────────────────────── */
function printClinicalReportSummary() {
  if (!activePatientData) return;
  
  fetch('/api/audit-logs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'GENERATE_QR', details: `Printed clinical summary report for ${activePatientData.full_name}`})
  });
  
  window.print();
}

/* ─────────────────────────────────────────────────────
   EMERGENCY PROFILE CARD POPUPS
   ───────────────────────────────────────────────────── */
function showEmergencyModalForCurrentPatient() {
  if (!activePatientData) return;
  
  document.getElementById('emergCardHealthId').textContent = activePatientData.health_id;
  document.getElementById('emergCardName').textContent = activePatientData.full_name;
  document.getElementById('emergCardAgeGender').textContent = `${activePatientData.age} years / ${activePatientData.gender}`;
  document.getElementById('emergCardBlood').textContent = activePatientData.blood_group;
  document.getElementById('emergCardContact').textContent = activePatientData.emergency_contact || 'None provided';
  document.getElementById('emergCardAlerts').textContent = `Allergies: ${activePatientData.allergies} | Chronic: ${activePatientData.chronic_diseases}`;
  
  const emergQrBox = document.getElementById('emergQrcode');
  if (emergQrBox) {
    emergQrBox.innerHTML = '';
    const redirectUrl = `${window.location.origin}/emergency/${activePatientData.health_id}`;
    new QRCode(emergQrBox, { text: redirectUrl, width: 120, height: 120, colorDark: '#EF4444', colorLight: '#ffffff' });
  }
  
  document.getElementById('emergencyCardModal').classList.add('active');
}

function closeEmergencyCardModal() {
  document.getElementById('emergencyCardModal').classList.remove('active');
}

function printEmergencyCard() {
  const content = document.querySelector('#emergencyCardModal .glass-card-modal').innerHTML;
  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <html>
    <head>
      <title>MediLink Emergency Card</title>
      <style>
        body { font-family: 'Inter', sans-serif; display:flex; justify-content:center; align-items:center; min-height:100vh; background:#fff; }
        .modal-close-icon { display:none; }
        button { display:none; }
      </style>
    </head>
    <body>
      <div style="border: 2px solid #EF4444; border-radius: 12px; padding: 2rem; max-width:400px; text-align:center;">
        ${content}
      </div>
    </body>
    </html>`);
  printWindow.document.close();
  printWindow.print();
}
