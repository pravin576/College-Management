/**
 * Attendance Module Controller
 */
let allAttendance = [];
let currentAttendanceExcelErrors = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadAttendanceData();
  }
});

async function loadAttendanceData() {
  const res = await fetchAPI("/api/attendance");
  if (res.success && res.attendance) {
    allAttendance = res.attendance;
    renderAttendanceTable(allAttendance);
  } else {
    renderAttendanceTable([]);
  }
}

function renderAttendanceTable(recs) {
  const tbody = document.getElementById("attendanceTableBody");
  if (!tbody) return;

  if (recs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No attendance records found matching filters.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const isStudent = user.role === "Student";

  tbody.innerHTML = recs.map(a => `
    <tr>
      <td class="fw-bold text-nowrap">${a.date}</td>
      <td><span class="badge bg-light text-dark border font-monospace">${a.student_id}</span></td>
      <td class="fw-semibold">${a.student_name}</td>
      <td><span class="badge bg-secondary">${a.department || 'N/A'}</span></td>
      <td class="small text-muted">${a.year || '1st Year'} (${a.semester || 'Sem 1'} / Div ${a.division || 'A'})</td>
      <td class="fw-medium">${a.subject}${a.subject_code ? ` <span class="badge bg-light text-secondary border">${a.subject_code}</span>` : ''}</td>
      <td>
        <span class="badge ${a.status === 'Present' ? 'bg-success' : a.status === 'Absent' ? 'bg-danger' : 'bg-warning'}">${a.status}</span>
      </td>
      <td class="action-col text-end me-3">
        ${!isStudent ? `
          <button class="btn btn-sm btn-outline-danger" onclick="deleteAttendance(${a.id})" title="Delete"><i class="bi bi-trash"></i></button>
        ` : `<span class="text-muted small">View Only</span>`}
      </td>
    </tr>
  `).join("");

  if (isStudent) {
    document.querySelectorAll(".action-col").forEach(el => el.style.display = "none");
  }
}

function filterAttendanceTable() {
  const q = (document.getElementById("searchAttendanceInput")?.value || "").toLowerCase().trim();
  const deptVal = document.getElementById("filterAttendanceDept")?.value || "All";
  const yearVal = document.getElementById("filterAttendanceYear")?.value || "All";
  const semVal = document.getElementById("filterAttendanceSem")?.value || "All";
  const divVal = document.getElementById("filterAttendanceDiv")?.value || "All";
  const dateVal = document.getElementById("filterAttendanceDate")?.value || "";
  const statusVal = document.getElementById("filterAttendanceStatus")?.value || "All";

  const filtered = allAttendance.filter(a => {
    const matchesSearch = !q || (a.student_id || "").toLowerCase().includes(q) || (a.student_name || "").toLowerCase().includes(q) || (a.subject || "").toLowerCase().includes(q);
    const matchesDept = deptVal === "All" || (a.department || "") === deptVal;
    const matchesYear = yearVal === "All" || (a.year || "First Year") === yearVal;
    const matchesSem = semVal === "All" || (a.semester || "Semester 1") === semVal;
    const matchesDiv = divVal === "All" || (a.division || "A") === divVal;
    const matchesDate = !dateVal || a.date === dateVal;
    const matchesStatus = statusVal === "All" || a.status === statusVal;
    return matchesSearch && matchesDept && matchesYear && matchesSem && matchesDiv && matchesDate && matchesStatus;
  });

  renderAttendanceTable(filtered);
}

function exportAttendanceCSV() {
  window.location.href = "/api/attendance/export";
}

async function saveAttendanceForm(e) {
  e.preventDefault();
  const payload = {
    studentId: document.getElementById("attStudentId").value.trim(),
    studentName: document.getElementById("attStudentName").value.trim(),
    subject: document.getElementById("attSubject").value.trim(),
    date: document.getElementById("attDate").value,
    status: document.getElementById("attStatus").value
  };

  const res = await fetchAPI("/api/attendance", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    showToast(res.message || "Attendance record saved!", "success");
    closeModal("markAttendanceModal");
    loadAttendanceData();
  } else {
    showToast(res.message || "Failed to save attendance", "danger");
  }
}

async function deleteAttendance(id) {
  if (!confirm("Are you sure you want to delete this attendance record?")) return;

  const res = await fetchAPI(`/api/attendance?id=${id}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Attendance record deleted", "success");
    loadAttendanceData();
  } else {
    showToast(res.message || "Failed to delete attendance", "danger");
  }
}

// Excel Attendance Import Handler
async function submitAttendanceExcelImport(e) {
  e.preventDefault();
  const fileInput = document.getElementById("attendanceExcelFileInput");
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    showToast("Please select an Excel (.xlsx) file!", "warning");
    return;
  }

  const file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    showToast("Invalid file format. Only .xlsx files are supported!", "danger");
    return;
  }

  const btn = document.getElementById("btnUploadAttendanceExcel");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Processing Attendance Excel...`;
  }

  const reader = new FileReader();
  reader.onload = async function (evt) {
    const arrayBuffer = evt.target.result;
    const bytes = new Uint8Array(arrayBuffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const fileBase64 = btoa(binary);

    const res = await fetchAPI("/api/attendance/import-excel", {
      method: "POST",
      body: JSON.stringify({ file_base64: fileBase64 })
    });

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-cloud-upload me-1"></i> Upload & Import Attendance`;
    }

    if (res.success) {
      showToast(`Attendance Import Complete: ${res.addedCount} Imported, ${res.duplicateCount} Duplicates, ${res.failedCount} Failed`, res.failedCount > 0 ? "warning" : "success");
      
      const container = document.getElementById("attendanceExcelResultContainer");
      if (container) container.classList.remove("d-none");

      if (document.getElementById("resAttTotal")) document.getElementById("resAttTotal").textContent = res.totalRecords || 0;
      if (document.getElementById("resAttAdded")) document.getElementById("resAttAdded").textContent = res.addedCount || 0;
      if (document.getElementById("resAttDup")) document.getElementById("resAttDup").textContent = res.duplicateCount || 0;
      if (document.getElementById("resAttFailed")) document.getElementById("resAttFailed").textContent = res.failedCount || 0;

      currentAttendanceExcelErrors = res.errors || [];
      const errSection = document.getElementById("attendanceExcelErrorSection");
      const errTbody = document.getElementById("attendanceExcelErrorTableBody");

      if (currentAttendanceExcelErrors.length > 0) {
        if (errSection) errSection.classList.remove("d-none");
        if (errTbody) {
          errTbody.innerHTML = currentAttendanceExcelErrors.map(err => `
            <tr>
              <td class="fw-bold text-danger">Row ${err.row}</td>
              <td>${err.student_id || 'N/A'}</td>
              <td>${err.name || 'N/A'}</td>
              <td class="text-danger fw-semibold">${err.reason}</td>
            </tr>
          `).join("");
        }
      } else {
        if (errSection) errSection.classList.add("d-none");
      }

      loadAttendanceData();
    } else {
      showToast(res.message || "Failed to process Attendance Excel import", "danger");
    }
  };
  reader.readAsArrayBuffer(file);
}

function downloadAttendanceErrorReport() {
  if (!currentAttendanceExcelErrors || currentAttendanceExcelErrors.length === 0) {
    showToast("No errors to export!", "info");
    return;
  }
  let csvContent = "data:text/csv;charset=utf-8,Excel Row Number,Enrollment Number,Student Name,Failure Reason\n";
  currentAttendanceExcelErrors.forEach(err => {
    csvContent += `"${err.row}","${err.student_id}","${err.name}","${err.reason}"\n`;
  });
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "attendance_excel_import_error_report.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
