/**
 * Reports Module Controller
 */
let currentReportData = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadReportData();
  }
});

async function loadReportData() {
  const reportType = document.getElementById("reportTypeSelect").value;
  const dept = document.getElementById("reportDeptFilter").value;
  const year = document.getElementById("reportYearFilter").value;
  const search = document.getElementById("reportSearchInput").value.trim();

  const url = `/api/reports/data?type=${encodeURIComponent(reportType)}&department=${encodeURIComponent(dept)}&year=${encodeURIComponent(year)}&search=${encodeURIComponent(search)}`;
  const res = await fetchAPI(url);

  if (res.success && res.data) {
    currentReportData = res.data;
    renderReportTable(reportType, res.data, res.summary);
  } else {
    currentReportData = [];
    renderReportTable(reportType, [], {});
  }

  if (document.getElementById("reportTimestamp")) {
    document.getElementById("reportTimestamp").textContent = `Generated: ${new Date().toLocaleString()}`;
  }
}

function renderReportTable(type, data, summary) {
  const head = document.getElementById("reportTableHead");
  const body = document.getElementById("reportTableBody");
  const title = document.getElementById("reportTableTitle");

  if (!head || !body) return;

  // Update Summary Metric Cards
  document.getElementById("reportMetric1").textContent = data.length;

  if (type === "student") {
    title.innerHTML = `<i class="bi bi-mortarboard-fill me-2 text-primary"></i> Student Directory Report`;
    document.getElementById("reportMetric2Title").textContent = "First Year Students";
    document.getElementById("reportMetric2").textContent = data.filter(d => d.year === "First Year").length;
    document.getElementById("reportMetric3Title").textContent = "Second/Third Year";
    document.getElementById("reportMetric3").textContent = data.filter(d => d.year !== "First Year").length;

    head.innerHTML = `
      <tr>
        <th>Enrollment Number</th>
        <th>Roll No</th>
        <th>Student Name</th>
        <th>Department</th>
        <th>Year</th>
        <th>Semester</th>
        <th>Email</th>
        <th>Mobile</th>
      </tr>
    `;

    body.innerHTML = data.length > 0 ? data.map(d => `
      <tr>
        <td class="fw-bold">${d.id}</td>
        <td>${d.roll_number || 'N/A'}</td>
        <td class="fw-semibold">${d.name}</td>
        <td><span class="badge bg-secondary">${d.department}</span></td>
        <td><span class="badge bg-info text-dark">${d.year || 'First Year'}</span></td>
        <td>${d.semester || 'Semester 1'}</td>
        <td>${d.email}</td>
        <td>${d.mobile}</td>
      </tr>
    `).join("") : `<tr><td colspan="8" class="text-center text-muted py-4">No report records found.</td></tr>`;

  } else if (type === "faculty") {
    title.innerHTML = `<i class="bi bi-person-video3 me-2 text-primary"></i> Faculty Directory Report`;
    document.getElementById("reportMetric2Title").textContent = "Total Faculty Members";
    document.getElementById("reportMetric2").textContent = data.length;
    document.getElementById("reportMetric3Title").textContent = "Active Status";
    document.getElementById("reportMetric3").textContent = data.filter(d => d.status === "Active").length;

    head.innerHTML = `
      <tr>
        <th>Faculty ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Designation</th>
        <th>Email</th>
        <th>Mobile</th>
        <th>Experience</th>
      </tr>
    `;

    body.innerHTML = data.length > 0 ? data.map(d => `
      <tr>
        <td class="fw-bold">${d.id}</td>
        <td class="fw-semibold">${d.name}</td>
        <td><span class="badge bg-secondary">${d.department}</span></td>
        <td>${d.designation}</td>
        <td>${d.email}</td>
        <td>${d.mobile}</td>
        <td>${d.experience || '1 Year'}</td>
      </tr>
    `).join("") : `<tr><td colspan="7" class="text-center text-muted py-4">No report records found.</td></tr>`;

  } else if (type === "attendance") {
    title.innerHTML = `<i class="bi bi-calendar-check-fill me-2 text-primary"></i> Attendance Summary Report`;
    const presentCnt = summary.presentCount || data.filter(d => d.status === "Present").length;
    const attPct = data.length > 0 ? `${((presentCnt / data.length) * 100).toFixed(1)}%` : "N/A";

    document.getElementById("reportMetric2Title").textContent = "Present Entries";
    document.getElementById("reportMetric2").textContent = presentCnt;
    document.getElementById("reportMetric3Title").textContent = "Overall Attendance %";
    document.getElementById("reportMetric3").textContent = attPct;

    head.innerHTML = `
      <tr>
        <th>ID</th>
        <th>Enrollment Number</th>
        <th>Student Name</th>
        <th>Subject</th>
        <th>Date</th>
        <th>Status</th>
        <th>Department</th>
      </tr>
    `;

    body.innerHTML = data.length > 0 ? data.map(d => `
      <tr>
        <td class="fw-bold">${d.id}</td>
        <td>${d.student_id}</td>
        <td class="fw-semibold">${d.student_name}</td>
        <td>${d.subject}</td>
        <td>${d.date}</td>
        <td><span class="badge ${d.status === 'Present' ? 'bg-success' : 'bg-danger'}">${d.status}</span></td>
        <td><span class="badge bg-secondary">${d.department}</span></td>
      </tr>
    `).join("") : `<tr><td colspan="7" class="text-center text-muted py-4">No report records found.</td></tr>`;

  } else if (type === "results") {
    title.innerHTML = `<i class="bi bi-journal-bookmark-fill me-2 text-primary"></i> Academic Results Report`;
    const passCnt = summary.passCount || data.filter(d => d.status === "Pass").length;
    const passPct = data.length > 0 ? `${((passCnt / data.length) * 100).toFixed(1)}%` : "N/A";

    document.getElementById("reportMetric2Title").textContent = "Passed Students";
    document.getElementById("reportMetric2").textContent = passCnt;
    document.getElementById("reportMetric3Title").textContent = "Pass Percentage";
    document.getElementById("reportMetric3").textContent = passPct;

    head.innerHTML = `
      <tr>
        <th>ID</th>
        <th>Enrollment Number</th>
        <th>Subject</th>
        <th>Semester</th>
        <th>Internal</th>
        <th>End Sem</th>
        <th>Total</th>
        <th>Grade</th>
        <th>Status</th>
      </tr>
    `;

    body.innerHTML = data.length > 0 ? data.map(d => `
      <tr>
        <td class="fw-bold">${d.id}</td>
        <td>${d.student_id}</td>
        <td class="fw-semibold">${d.subject}</td>
        <td>${d.semester}</td>
        <td>${d.internal_marks}</td>
        <td>${d.end_sem_marks}</td>
        <td class="fw-bold">${d.total_marks}</td>
        <td><span class="badge bg-info text-dark">${d.grade}</span></td>
        <td><span class="badge ${d.status === 'Pass' ? 'bg-success' : 'bg-danger'}">${d.status}</span></td>
      </tr>
    `).join("") : `<tr><td colspan="9" class="text-center text-muted py-4">No report records found.</td></tr>`;

  } else if (type === "fees") {
    title.innerHTML = `<i class="bi bi-credit-card-fill me-2 text-primary"></i> Fees Ledger Report`;
    const paid = summary.totalPaid || data.reduce((acc, curr) => acc + (curr.paid_fees || 0), 0);
    const pending = summary.totalPending || data.reduce((acc, curr) => acc + (curr.pending_fees || 0), 0);

    document.getElementById("reportMetric2Title").textContent = "Total Paid Fees (₹)";
    document.getElementById("reportMetric2").textContent = `₹${paid.toLocaleString()}`;
    document.getElementById("reportMetric3Title").textContent = "Total Pending Fees (₹)";
    document.getElementById("reportMetric3").textContent = `₹${pending.toLocaleString()}`;

    head.innerHTML = `
      <tr>
        <th>Receipt No</th>
        <th>Enrollment Number</th>
        <th>Student Name</th>
        <th>Department</th>
        <th>Total Fees</th>
        <th>Paid Fees</th>
        <th>Pending Fees</th>
        <th>Status</th>
      </tr>
    `;

    body.innerHTML = data.length > 0 ? data.map(d => `
      <tr>
        <td class="fw-bold">${d.receipt_number || ('REC-2026-' + (1000 + d.id))}</td>
        <td>${d.student_id}</td>
        <td class="fw-semibold">${d.student_name}</td>
        <td><span class="badge bg-secondary">${d.department}</span></td>
        <td>₹${d.total_fees}</td>
        <td class="text-success fw-bold">₹${d.paid_fees}</td>
        <td class="text-danger fw-bold">₹${d.pending_fees}</td>
        <td><span class="badge ${d.payment_status === 'Paid' ? 'bg-success' : d.payment_status === 'Partial' ? 'bg-warning text-dark' : 'bg-danger'}">${d.payment_status}</span></td>
      </tr>
    `).join("") : `<tr><td colspan="8" class="text-center text-muted py-4">No report records found.</td></tr>`;
  }
}

function filterReportTable() {
  loadReportData();
}

function exportReportCSV() {
  const type = document.getElementById("reportTypeSelect").value;
  const dept = document.getElementById("reportDeptFilter").value;
  window.location.href = `/api/reports/export?type=${encodeURIComponent(type)}&department=${encodeURIComponent(dept)}`;
}
