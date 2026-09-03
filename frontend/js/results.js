/**
 * Exam Results Module Controller
 */
let allResults = [];
let currentResultsExcelErrors = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadResultsData();
  }
});

async function loadResultsData() {
  const res = await fetchAPI("/api/results");
  if (res.success && res.results) {
    allResults = res.results;
    renderResultsTable(allResults);
  } else {
    renderResultsTable([]);
  }
}

function renderResultsTable(recs) {
  const tbody = document.getElementById("resultsTableBody");
  if (!tbody) return;

  if (recs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="12" class="text-center text-muted py-4">No exam results available matching filters.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const isStudent = user.role === "Student";

  tbody.innerHTML = recs.map(r => {
    let docBadge = `<span class="text-muted small">No file attached</span>`;
    if (r.document) {
      const isImg = r.document.match(/\.(png|jpg|jpeg|gif)$/i);
      const isPdf = r.document.match(/\.pdf$/i);
      const isDoc = r.document.match(/\.(doc|docx)$/i);
      const icon = isImg ? 'bi-file-image-fill text-success' : isPdf ? 'bi-file-pdf-fill text-danger' : isDoc ? 'bi-file-word-fill text-primary' : 'bi-file-earmark-fill text-info';
      docBadge = `<a href="${r.document}" target="_blank" class="btn btn-xs btn-outline-dark fw-bold py-0 px-2" title="View attached document or photo"><i class="bi ${icon} me-1"></i> View ${isImg ? 'Photo' : isPdf ? 'PDF' : 'Doc'}</a>`;
    }

    return `
      <tr>
        <td class="fw-bold"><span class="badge bg-light text-dark border font-monospace">${r.student_id}</span></td>
        <td class="fw-semibold">${r.student_name}</td>
        <td>${r.semester}</td>
        <td class="fw-medium">${r.subject}</td>
        <td>${r.internal_marks}</td>
        <td>${r.end_sem_marks}</td>
        <td class="fw-bold">${r.total_marks}</td>
        <td>${r.percentage}%</td>
        <td><span class="badge bg-primary">${r.grade}</span></td>
        <td><span class="badge ${r.status === 'Pass' ? 'bg-success' : 'bg-danger'}">${r.status}</span></td>
        <td>${docBadge}</td>
        <td class="action-col text-end me-3">
          ${!isStudent ? `
            <button class="btn btn-sm btn-outline-primary py-0 px-2 me-1" onclick="editResult(${r.id})" title="Edit Result"><i class="bi bi-pencil"></i></button>
            <label class="btn btn-sm btn-outline-primary mb-0 py-0 px-2 me-1" title="Upload/Attach Marksheet Photo or Document">
              <i class="bi bi-paperclip"></i>
              <input type="file" class="d-none" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" onchange="uploadResultDocument(${r.id}, this)">
            </label>
            <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteResult(${r.id})" title="Delete"><i class="bi bi-trash"></i></button>
          ` : `<span class="text-muted small">View Only</span>`}
        </td>
      </tr>
    `;
  }).join("");

  if (isStudent) {
    document.querySelectorAll(".action-col").forEach(el => el.style.display = "none");
  }
}

let editingResultId = null;

function editResult(id) {
  const r = allResults.find(x => x.id == id);
  if (!r) return;
  editingResultId = id;

  const sIdEl = document.getElementById("resStudentId");
  const sNameEl = document.getElementById("resStudentName");
  const semEl = document.getElementById("resSemester");
  const subjEl = document.getElementById("resSubject");
  const intEl = document.getElementById("resInternal");
  const endEl = document.getElementById("resEndSem");

  if (sIdEl) sIdEl.value = r.student_id || "";
  if (sNameEl) sNameEl.value = r.student_name || "";
  if (semEl) semEl.value = r.semester || "Semester 1";
  if (subjEl) subjEl.value = r.subject || "";
  if (intEl) intEl.value = r.internal_marks !== undefined ? r.internal_marks : "";
  if (endEl) endEl.value = r.end_sem_marks !== undefined ? r.end_sem_marks : "";

  openModal("addResultModal");
}

function filterResultsTable() {
  const q = (document.getElementById("searchResultsInput")?.value || "").toLowerCase();
  const semVal = document.getElementById("filterResultsSem")?.value || "All";

  const filtered = allResults.filter(r => {
    const matchesSearch = (r.student_id || "").toLowerCase().includes(q) || (r.student_name || "").toLowerCase().includes(q) || (r.subject || "").toLowerCase().includes(q);
    const matchesSem = semVal === "All" || r.semester === semVal;
    return matchesSearch && matchesSem;
  });

  renderResultsTable(filtered);
}

function exportResultsFile() {
  const semVal = document.getElementById("filterResultsSem")?.value || "All";
  window.location.href = `/api/results/export?semester=${encodeURIComponent(semVal)}`;
}

async function saveResultForm(e) {
  e.preventDefault();
  const payload = {
    id: editingResultId,
    studentId: document.getElementById("resStudentId").value.trim(),
    studentName: document.getElementById("resStudentName").value.trim(),
    semester: document.getElementById("resSemester").value,
    subject: document.getElementById("resSubject").value.trim(),
    internalMarks: parseFloat(document.getElementById("resInternal").value || 0),
    endSemMarks: parseFloat(document.getElementById("resEndSem").value || 0)
  };

  const res = await fetchAPI("/api/results", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    const fileInput = document.getElementById("resDocumentInput");
    if (fileInput && fileInput.files && fileInput.files.length > 0 && (res.id || editingResultId)) {
      await uploadResultDocumentFile(res.id || editingResultId, fileInput.files[0]);
    }
    showToast(res.message || "Exam result saved successfully!", "success");
    editingResultId = null;
    closeModal("addResultModal");
    loadResultsData();
  } else {
    showToast(res.message || "Failed to save exam result", "danger");
  }
}

async function uploadResultDocument(resId, inputEl) {
  if (!inputEl || !inputEl.files || inputEl.files.length === 0) return;
  const file = inputEl.files[0];
  await uploadResultDocumentFile(resId, file);
  loadResultsData();
}

async function uploadResultDocumentFile(resId, file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = async function (evt) {
      const fileBase64 = evt.target.result;

      const res = await fetchAPI("/api/results/upload-document", {
        method: "POST",
        body: JSON.stringify({
          result_id: resId,
          file_name: file.name,
          file_base64: fileBase64
        })
      });

      if (res.success) {
        showToast("Marksheet document/photo attached!", "success");
      } else {
        showToast(res.message || "Failed to attach document", "danger");
      }
      resolve(res);
    };
    reader.readAsDataURL(file);
  });
}

async function submitResultsExcelImport(e) {
  e.preventDefault();
  const fileInput = document.getElementById("resultsExcelFileInput");
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    showToast("Please select an Excel (.xlsx) file!", "warning");
    return;
  }

  const file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    showToast("Invalid file format. Only .xlsx files are supported!", "danger");
    return;
  }

  const btn = document.getElementById("btnUploadResultsExcel");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Processing Exam Results Excel...`;
  }

  const reader = new FileReader();
  reader.onload = async function (evt) {
    const fileBase64 = evt.target.result;

    const res = await fetchAPI("/api/results/import-excel", {
      method: "POST",
      body: JSON.stringify({ file_base64: fileBase64 })
    });

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-cloud-upload me-1"></i> Upload & Import Exam Results`;
    }

    if (res.success) {
      showToast(`Exam Results Import Complete: ${res.addedCount} Added, ${res.duplicateCount} Updated, ${res.failedCount} Failed`, res.failedCount > 0 ? "warning" : "success");
      
      const container = document.getElementById("resultsExcelResultContainer");
      if (container) container.classList.remove("d-none");

      if (document.getElementById("resTotal")) document.getElementById("resTotal").textContent = res.totalRecords || 0;
      if (document.getElementById("resAdded")) document.getElementById("resAdded").textContent = res.addedCount || 0;
      if (document.getElementById("resDup")) document.getElementById("resDup").textContent = res.duplicateCount || 0;
      if (document.getElementById("resFailed")) document.getElementById("resFailed").textContent = res.failedCount || 0;

      currentResultsExcelErrors = res.errors || [];
      const errSection = document.getElementById("resultsExcelErrorSection");
      const errTbody = document.getElementById("resultsExcelErrorTableBody");

      if (currentResultsExcelErrors.length > 0) {
        if (errSection) errSection.classList.remove("d-none");
        if (errTbody) {
          errTbody.innerHTML = currentResultsExcelErrors.map(err => `
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

      loadResultsData();
    } else {
      showToast(res.message || "Failed to process Exam Results Excel import", "danger");
    }
  };
  reader.readAsDataURL(file);
}

function downloadResultsErrorReport() {
  if (!currentResultsExcelErrors || currentResultsExcelErrors.length === 0) {
    showToast("No errors to export!", "info");
    return;
  }
  let csvContent = "data:text/csv;charset=utf-8,Excel Row Number,Enrollment Number,Student Name,Failure Reason\n";
  currentResultsExcelErrors.forEach(err => {
    csvContent += `"${err.row}","${err.student_id}","${err.name}","${err.reason}"\n`;
  });
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "exam_results_import_error_report.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

async function deleteResult(id) {
  if (!confirm("Are you sure you want to delete this result record?")) return;

  const res = await fetchAPI(`/api/results?id=${id}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Result record deleted", "success");
    loadResultsData();
  } else {
    showToast(res.message || "Failed to delete result", "danger");
  }
}
