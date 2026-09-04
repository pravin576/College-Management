/**
 * Students Module Controller
 */
let allStudents = [];
let isEditingStudent = false;

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    if (user.role === "Faculty") {
      const pageTitle = document.querySelector(".erp-page-title");
      if (pageTitle) pageTitle.textContent = "My Assigned Students";
      const deptFilter = document.getElementById("filterStudentDept");
      if (deptFilter) {
        const col = deptFilter.closest(".col-md-3");
        if (col) col.style.display = "none";
      }
    } else if (user.role === "HOD") {
      const pageTitle = document.querySelector(".erp-page-title");
      if (pageTitle) pageTitle.textContent = `${user.department || "Department"} - Student Records`;
    } else if (["Administrator", "Admin"].includes(user.role)) {
      const pageTitle = document.querySelector(".erp-page-title");
      if (pageTitle) pageTitle.textContent = "Institutional Student Directory (All Departments)";
    }
    loadStudentsData();
  }
});

async function loadStudentsData() {
  const res = await fetchAPI("/api/students");
  if (res.success && res.students) {
    allStudents = res.students;
    filterStudentsTable();
  } else {
    allStudents = [];
    renderStudentsTable([]);
  }
}

function renderStudentsTable(students) {
  const tbody = document.getElementById("studentsTableBody");
  const badge = document.getElementById("studentsCountBadge");
  if (badge) badge.textContent = `${students.length} Students`;

  if (!tbody) return;

  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-4">No data available.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const canManageStudent = ["Administrator", "Admin", "HOD"].includes(user.role);

  tbody.innerHTML = students.map(s => `
    <tr>
      <td class="fw-bold">${s.id}</td>
      <td>${s.roll_number || 'N/A'}</td>
      <td class="fw-semibold">${s.name}</td>
      <td><span class="badge bg-secondary">${s.department}</span></td>
      <td><span class="badge bg-info text-dark">${s.year || 'First Year'}</span></td>
      <td>${s.semester || 'Semester 1'} (${s.division || 'A'})</td>
      <td>${s.email}</td>
      <td>${s.mobile}</td>
      <td><span class="badge bg-success">${s.status || 'Active'}</span></td>
      <td>
        <button class="btn btn-sm btn-outline-info me-1" onclick="viewStudentProfile('${s.id}')" title="Profile View"><i class="bi bi-eye"></i></button>
        <button class="btn btn-sm btn-outline-dark me-1" onclick="viewStudentIdCard('${s.id}')" title="ID Card"><i class="bi bi-card-heading"></i></button>
        ${canManageStudent ? `
          <button class="btn btn-sm btn-outline-primary me-1" onclick="editStudent('${s.id}')" title="Edit"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-warning me-1" onclick="resetStudentPassword('${s.id}')" title="Reset Temporary Password"><i class="bi bi-key-fill"></i></button>
          <button class="btn btn-sm btn-outline-danger" onclick="deleteStudent('${s.id}')" title="Delete"><i class="bi bi-trash"></i></button>
        ` : ''}
      </td>
    </tr>
  `).join("");
}

function filterStudentsTable() {
  const q = (document.getElementById("searchStudentInput")?.value || "").toLowerCase().trim();
  const dept = document.getElementById("filterStudentDept")?.value || "All";
  const year = document.getElementById("filterStudentYear")?.value || "All";
  const sem = document.getElementById("filterStudentSem")?.value || "All";
  const div = document.getElementById("filterStudentDiv")?.value || "All";

  const filtered = allStudents.filter(s => {
    const matchesSearch = !q || (s.name || "").toLowerCase().includes(q) || (s.id || "").toLowerCase().includes(q) || (s.roll_number || "").toLowerCase().includes(q) || (s.email || "").toLowerCase().includes(q);
    const matchesDept = dept === "All" || s.department === dept;
    const matchesYear = year === "All" || s.year === year;
    const matchesSem = sem === "All" || s.semester === sem;
    const matchesDiv = div === "All" || s.division === div;
    return matchesSearch && matchesDept && matchesYear && matchesSem && matchesDiv;
  });

  const statusText = document.getElementById("filterStatusText");
  if (statusText) {
    statusText.textContent = `Filtered View: ${dept !== "All" ? dept : "All Depts"} | ${year !== "All" ? year : "All Years"} | ${sem !== "All" ? sem : "All Sems"} | ${div !== "All" ? "Div " + div : "All Divs"} (${filtered.length} matching)`;
  }

  renderStudentsTable(filtered);
}

function viewStudentProfile(id) {
  const s = allStudents.find(item => item.id === id);
  if (!s) return;

  const modalBody = document.getElementById("studentProfileModalBody");
  if (!modalBody) return;

  modalBody.innerHTML = `
    <div class="row g-3">
      <div class="col-md-4 text-center border-end">
        <img src="${s.photo || 'images/img1.jpg'}" alt="Student Photo" class="img-fluid rounded border mb-2" style="max-height: 160px; object-fit: cover;">
        <h5 class="fw-bold text-dark mb-0">${s.name}</h5>
        <span class="badge bg-primary">${s.department}</span>
        <div class="mt-2 text-muted small">Year: ${s.year || 'First Year'} | ${s.semester} (${s.division || 'A'})</div>
      </div>
      <div class="col-md-8">
        <h6 class="fw-bold text-primary border-bottom pb-2 mb-3">Academic Information</h6>
        <div class="row g-2 small">
          <div class="col-6"><strong>Enrollment Number:</strong> ${s.id}</div>
          <div class="col-6"><strong>Roll Number:</strong> ${s.roll_number || 'N/A'}</div>
          <div class="col-6"><strong>Email ID:</strong> ${s.email}</div>
          <div class="col-6"><strong>Contact Phone:</strong> ${s.mobile}</div>
          <div class="col-6"><strong>Gender:</strong> ${s.gender || 'Male'}</div>
          <div class="col-6"><strong>Date of Birth:</strong> ${s.dob || 'N/A'}</div>
          <div class="col-6"><strong>Admission Year:</strong> ${s.admission_year || '2026'}</div>
          <div class="col-6"><strong>Account Status:</strong> <span class="badge bg-success">${s.status || 'Active'}</span></div>
          <div class="col-12 mt-2"><strong>Permanent Address:</strong> ${s.address || 'N/A'}</div>
        </div>
      </div>
    </div>
  `;

  openModal("studentProfileModal");
}

async function viewStudentIdCard(id) {
  const res = await fetchAPI(`/api/students/id-card?id=${encodeURIComponent(id)}`);
  if (res.success && res.card) {
    const c = res.card;
    if (document.getElementById("cardPhoto")) document.getElementById("cardPhoto").src = c.studentPhoto;
    if (document.getElementById("cardName")) document.getElementById("cardName").textContent = c.studentName;
    if (document.getElementById("cardDept")) document.getElementById("cardDept").textContent = c.department;
    if (document.getElementById("cardId")) document.getElementById("cardId").textContent = c.studentId;
    if (document.getElementById("cardRoll")) document.getElementById("cardRoll").textContent = c.rollNumber;
    if (document.getElementById("cardYear")) document.getElementById("cardYear").textContent = c.year;
    if (document.getElementById("cardSemDiv")) document.getElementById("cardSemDiv").textContent = `${c.semester} (${c.division})`;
    if (document.getElementById("cardContact")) document.getElementById("cardContact").textContent = `${c.mobile} | ${c.email}`;
    if (document.getElementById("cardStatus")) document.getElementById("cardStatus").textContent = c.status.toUpperCase();

    openModal("studentIdCardModal");
  } else {
    showToast(res.message || "Failed to load ID card", "danger");
  }
}

async function saveStudentForm(e) {
  e.preventDefault();
  const payload = {
    id: document.getElementById("modalStudentId").value.trim(),
    rollNumber: document.getElementById("modalRollNumber").value.trim(),
    name: document.getElementById("modalName").value.trim(),
    email: document.getElementById("modalEmail").value.trim(),
    mobile: document.getElementById("modalMobile").value.trim(),
    gender: document.getElementById("modalGender").value,
    dob: document.getElementById("modalDob").value,
    department: document.getElementById("modalDepartment").value,
    year: document.getElementById("modalYear") ? document.getElementById("modalYear").value : "First Year",
    semester: document.getElementById("modalSemester").value,
    division: document.getElementById("modalDivision").value,
    admissionYear: document.getElementById("modalAdmissionYear").value,
    address: document.getElementById("modalAddress").value.trim(),
    status: document.getElementById("modalStatus") ? document.getElementById("modalStatus").value : "Active",
    is_edit: isEditingStudent,
    password: (document.getElementById("modalStudentPassword")?.value || "").trim()
  };

  const res = await fetchAPI("/api/students", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    closeModal("addStudentModal");
    isEditingStudent = false;
    loadStudentsData();
    if (res.credentials) {
      showCredentialModal(res.credentials);
    } else {
      showToast(res.message || "Student saved successfully!", "success");
    }
  } else {
    showToast(res.message || "Failed to save student record", "danger");
  }
}

function editStudent(id) {
  const s = allStudents.find(item => item.id === id);
  if (!s) return;

  isEditingStudent = true;
  document.getElementById("modalStudentId").value = s.id;
  document.getElementById("modalStudentId").readOnly = true;
  document.getElementById("modalRollNumber").value = s.roll_number || "";
  document.getElementById("modalName").value = s.name || "";
  document.getElementById("modalEmail").value = s.email || "";
  document.getElementById("modalMobile").value = s.mobile || "";
  document.getElementById("modalGender").value = s.gender || "Male";
  document.getElementById("modalDob").value = s.dob || "";
  document.getElementById("modalDepartment").value = s.department || "Computer Engineering";
  if (document.getElementById("modalYear")) document.getElementById("modalYear").value = s.year || "First Year";
  document.getElementById("modalSemester").value = s.semester || "Semester 1";
  document.getElementById("modalDivision").value = s.division || "A";
  document.getElementById("modalAdmissionYear").value = s.admission_year || "2026";
  document.getElementById("modalAddress").value = s.address || "";
  if (document.getElementById("modalStatus")) document.getElementById("modalStatus").value = s.status || "Active";

  openModal("addStudentModal");
}

async function deleteStudent(id) {
  if (!confirm(`Are you sure you want to delete student '${id}'?`)) return;

  const res = await fetchAPI(`/api/students?id=${encodeURIComponent(id)}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Student deleted successfully", "success");
    loadStudentsData();
  } else {
    showToast(res.message || "Failed to delete student", "danger");
  }
}

function generateSampleBulkCsv() {
  const dept = document.getElementById("bulkDept").value;
  const year = document.getElementById("bulkYear").value;
  const sem = document.getElementById("bulkSem").value;
  const div = document.getElementById("bulkDiv").value;

  const firstNames = ["Aarav", "Ananya", "Rohan", "Priya", "Aditya", "Isha", "Kunal", "Tanvi", "Siddharth", "Neha", "Vikram", "Pooja", "Rahul", "Shreya", "Manish", "Divya", "Gaurav", "Ritu", "Amit", "Kavya"];
  const lastNames = ["Patil", "Deshmukh", "Joshi", "Kulkarni", "Pawar", "Shinde", "Kale", "Gaikwad", "More", "Chavan"];

  let lines = [];
  const startNum = Math.floor(Math.random() * 1000) + 100;

  for (let i = 1; i <= 50; i++) {
    const fn = firstNames[(i - 1) % firstNames.length];
    const ln = lastNames[(i - 1) % lastNames.length];
    const name = `${fn} ${ln}`;
    const rollNo = `R${startNum + i}`;
    const stuId = `STU${startNum + i}`;
    const email = `${fn.toLowerCase()}.${ln.toLowerCase()}${i}@college.edu`;
    const mobile = `987${(1000000 + i).toString().padStart(7, '0')}`;
    const gender = (i % 2 === 0) ? "Female" : "Male";

    lines.push(`${stuId}, ${rollNo}, ${name}, ${email}, ${mobile}, ${gender}`);
  }

  document.getElementById("bulkCsvText").value = lines.join("\n");
  showToast("Generated 50 sample student records in CSV format!", "info");
}

async function saveBulkStudents(e) {
  e.preventDefault();
  const dept = document.getElementById("bulkDept").value;
  const year = document.getElementById("bulkYear").value;
  const sem = document.getElementById("bulkSem").value;
  const div = document.getElementById("bulkDiv").value;
  const text = document.getElementById("bulkCsvText").value.trim();

  if (!text) {
    showToast("Please enter or generate student rows first!", "warning");
    return;
  }

  const lines = text.split("\n").filter(l => l.trim().length > 0);
  const students = [];

  lines.forEach((line, idx) => {
    const parts = line.split(",").map(p => p.trim());
    if (parts.length >= 3) {
      let stuId = "";
      let rollNo = "";
      let name = "";
      let email = "";
      let mobile = "";
      let gender = "Male";

      if (parts.length >= 5) {
        // Format: ID, RollNo, Name, Email, Mobile, Gender
        stuId = parts[0];
        rollNo = parts[1];
        name = parts[2];
        email = parts[3];
        mobile = parts[4];
        if (parts[5]) gender = parts[5];
      } else {
        // Format: RollNo, Name, Email
        rollNo = parts[0];
        stuId = `STU_${rollNo}`;
        name = parts[1];
        email = parts[2];
      }

      students.push({
        id: stuId,
        rollNumber: rollNo,
        name: name,
        email: email || `${stuId.toLowerCase()}@college.edu`,
        mobile: mobile || "9876543210",
        gender: gender,
        department: dept,
        year: year,
        semester: sem,
        division: div
      });
    }
  });

  if (students.length === 0) {
    showToast("Could not parse any valid student records from input!", "danger");
    return;
  }

  const res = await fetchAPI("/api/students/bulk", {
    method: "POST",
    body: JSON.stringify({
      department: dept,
      year: year,
      semester: sem,
      division: div,
      students: students
    })
  });

  if (res.success) {
    showToast(res.message, "success");
    closeModal("bulkStudentModal");
    document.getElementById("bulkCsvText").value = "";
    loadStudentsData();
  } else {
    showToast(res.message || "Failed to process bulk student insertion", "danger");
  }
}

// Student Password Reset Controller
async function resetStudentPassword(id) {
  if (!confirm(`Are you sure you want to reset the login password for student '${id}'? A new temporary password will be generated.`)) {
    return;
  }

  const res = await fetchAPI("/api/students/reset-password", {
    method: "POST",
    body: JSON.stringify({ id: id })
  });

  if (res.success && res.credentials) {
    showCredentialModal(res.credentials);
    showToast(`Password reset successfully for student '${id}'`, "success");
  } else {
    showToast(res.message || "Failed to reset password", "danger");
  }
}

// Excel Student Import Controller
let currentStudentExcelErrors = [];
let currentStudentCredentials = [];

async function submitStudentExcelImport(e) {
  e.preventDefault();
  const fileInput = document.getElementById("studentExcelFileInput");
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    showToast("Please select an Excel (.xlsx) file!", "warning");
    return;
  }

  const file = fileInput.files[0];
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    showToast("Invalid file format. Only .xlsx files are supported!", "danger");
    return;
  }

  const btn = document.getElementById("btnUploadStudentExcel");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Processing 1000+ Records...`;
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

    const res = await fetchAPI("/api/students/import-excel", {
      method: "POST",
      body: JSON.stringify({ file_base64: fileBase64 })
    });

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-cloud-upload me-1"></i> Upload & Import Students`;
    }

    if (res.success) {
      showToast(`Import Complete: ${res.addedCount} Added, ${res.duplicateCount} Duplicates, ${res.failedCount} Failed`, res.failedCount > 0 ? "warning" : "success");
      
      const container = document.getElementById("studentExcelResultContainer");
      if (container) container.classList.remove("d-none");

      if (document.getElementById("resStuTotal")) document.getElementById("resStuTotal").textContent = res.totalRecords || 0;
      if (document.getElementById("resStuAdded")) document.getElementById("resStuAdded").textContent = res.addedCount || 0;
      if (document.getElementById("resStuDup")) document.getElementById("resStuDup").textContent = res.duplicateCount || 0;
      if (document.getElementById("resStuFailed")) document.getElementById("resStuFailed").textContent = res.failedCount || 0;

      // Handle Generated Credentials Report
      currentStudentCredentials = res.credentials || [];
      const credSection = document.getElementById("studentExcelCredSection");
      const credTbody = document.getElementById("studentExcelCredTableBody");
      const credCount = document.getElementById("resStuCredCount");

      if (credCount) credCount.textContent = currentStudentCredentials.length;

      if (currentStudentCredentials.length > 0) {
        if (credSection) credSection.classList.remove("d-none");
        if (credTbody) {
          credTbody.innerHTML = currentStudentCredentials.map(c => `
            <tr>
              <td class="fw-bold text-dark">${c.enrollmentNumber || c.username}</td>
              <td class="fw-semibold">${c.name}</td>
              <td><span class="badge bg-secondary">${c.department}</span></td>
              <td>${c.year || 'First Year'}</td>
              <td>${c.semester || 'Semester 1'}</td>
              <td>${c.division || 'A'}</td>
              <td><code>${c.username}</code></td>
              <td><code class="text-danger fw-bold">${c.temporaryPassword}</code></td>
              <td><span class="badge bg-success">${c.status || 'Created'}</span></td>
            </tr>
          `).join("");
        }
      } else {
        if (credSection) credSection.classList.add("d-none");
      }

      // Handle Failed / Duplicate Errors Report
      currentStudentExcelErrors = res.errors || [];
      const errSection = document.getElementById("studentExcelErrorSection");
      const errTbody = document.getElementById("studentExcelErrorTableBody");

      if (currentStudentExcelErrors.length > 0) {
        if (errSection) errSection.classList.remove("d-none");
        if (errTbody) {
          errTbody.innerHTML = currentStudentExcelErrors.map(err => `
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

      loadStudentsData();
    } else {
      showToast(res.message || "Failed to process Excel import", "danger");
    }
  };
  reader.readAsArrayBuffer(file);
}

async function downloadStudentCredentialsExcel() {
  if (!currentStudentCredentials || currentStudentCredentials.length === 0) {
    showToast("No generated credentials available to export!", "warning");
    return;
  }

  try {
    const token = localStorage.getItem("token");
    const response = await fetch("/api/students/export-credentials", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": token ? `Bearer ${token}` : ""
      },
      body: JSON.stringify({ credentials: currentStudentCredentials })
    });

    if (response.ok) {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = response.headers.get("Content-Disposition") || "";
      let filename = `student_login_credentials_${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)}.xlsx`;
      if (disposition.includes("filename=")) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = match[1];
      }
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      showToast("Credentials downloaded successfully!", "success");
    } else {
      // Fallback to CSV format
      downloadStudentCredentialsCsvFallback();
    }
  } catch (err) {
    console.warn("Server XLSX export fallback triggered:", err);
    downloadStudentCredentialsCsvFallback();
  }
}

function downloadStudentCredentialsCsvFallback() {
  let csv = "Enrollment Number,Student Name,Department,Year,Semester,Division,Username,Temporary Password,Account Status\n";
  currentStudentCredentials.forEach(c => {
    csv += `"${c.enrollmentNumber}","${c.name}","${c.department}","${c.year || 'First Year'}","${c.semester || 'Semester 1'}","${c.division || 'A'}","${c.username}","${c.temporaryPassword}","${c.status || 'Created'}"\n`;
  });
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `student_login_credentials_${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)}.csv`;
  document.body.appendChild(a);
  a.click();
  URL.revokeObjectURL(url);
  document.body.removeChild(a);
  showToast("Credentials exported in CSV format!", "success");
}

function downloadStudentErrorReport() {
  if (!currentStudentExcelErrors || currentStudentExcelErrors.length === 0) {
    showToast("No errors to export!", "info");
    return;
  }
  let csvContent = "data:text/csv;charset=utf-8,Excel Row Number,Enrollment Number,Student Name,Failure Reason\n";
  currentStudentExcelErrors.forEach(err => {
    csvContent += `"${err.row}","${err.student_id}","${err.name}","${err.reason}"\n`;
  });
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "student_excel_import_error_report.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
