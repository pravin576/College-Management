/**
 * HOD Module Controller - Robust HOD Management & Department Isolation
 */
let allHods = [];
let hodAllStudents = [];
let currentDept = "Computer Engineering";
let currentFacultyId = "";
let currentAssignedStudents = [];
let departmentFacultyList = [];
let isEditingHod = false;

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    const urlParams = new URLSearchParams(window.location.search);
    const queryDept = urlParams.get("department");

    if (user.role === "HOD" && user.department) {
      currentDept = user.department;
    } else if (queryDept) {
      currentDept = queryDept;
    }
    
    const globalDeptSelect = document.getElementById("hodGlobalDeptFilter");
    if (globalDeptSelect) {
      globalDeptSelect.value = currentDept;
      if (user.role === "HOD") {
        globalDeptSelect.disabled = true;
        globalDeptSelect.title = `Department strictly locked to ${currentDept}`;
      }
    }

    const pageTitleEl = document.querySelector(".erp-page-title");
    if (pageTitleEl) {
      if (["Administrator", "Admin"].includes(user.role)) {
        pageTitleEl.textContent = "HOD Leadership & Department Management";
      } else if (user.role === "HOD") {
        pageTitleEl.textContent = `${currentDept} - Faculty-Student Assignment Portal`;
      }
    }

    const assignCard = document.getElementById("facultyStudentAssignmentCard");
    if (["Administrator", "Admin"].includes(user.role)) {
      if (assignCard) assignCard.classList.add("d-none");
      document.querySelectorAll(".role-hod-only, .section-faculty-student-assignment, .action-assign-student, .action-remove-assignment").forEach(el => el.classList.add("d-none"));
    } else if (user.role === "HOD") {
      if (assignCard) assignCard.classList.remove("d-none");
      document.querySelectorAll(".action-add-hod, .action-edit-hod").forEach(btn => btn.classList.add("d-none"));
    } else {
      if (assignCard) assignCard.classList.add("d-none");
      document.querySelectorAll(".action-add-hod, .action-edit-hod").forEach(btn => btn.classList.add("d-none"));
    }

    await loadHodDashboardStats(currentDept);
    await loadHodStudents(currentDept);
    if (user.role === "HOD") {
      await loadHodFacultyList(currentDept);
    }
    await loadHodData();
  }
});

async function onHodGlobalDeptChange(dept) {
  const user = getSession();
  if (user && user.role === "HOD") {
    currentDept = user.department || currentDept;
  } else {
    currentDept = dept;
  }
  currentFacultyId = "";
  await loadHodDashboardStats(currentDept);
  await loadHodStudents(currentDept);
  await loadHodFacultyList(currentDept);
}

async function loadHodDashboardStats(dept = currentDept) {
  const res = await fetchAPI(`/api/hod/dashboard-stats?department=${encodeURIComponent(dept)}`);
  if (res.success && res.stats) {
    const s = res.stats;
    if (document.getElementById("countFirstYear")) document.getElementById("countFirstYear").textContent = `${s.firstYearStudents || 0} Students`;
    if (document.getElementById("countSecondYear")) document.getElementById("countSecondYear").textContent = `${s.secondYearStudents || 0} Students`;
    if (document.getElementById("countThirdYear")) document.getElementById("countThirdYear").textContent = `${s.thirdYearStudents || 0} Students`;
    if (document.getElementById("countTotalStudents")) document.getElementById("countTotalStudents").textContent = `${s.totalStudents || 0} Students`;

    if (document.getElementById("hodTotalFaculty")) document.getElementById("hodTotalFaculty").textContent = `${s.totalFaculty || 0} Faculty`;
    if (document.getElementById("hodAttendanceRate")) document.getElementById("hodAttendanceRate").textContent = `${s.attendancePercentage || 100}%`;
    if (document.getElementById("hodPassPercentage")) document.getElementById("hodPassPercentage").textContent = `${s.resultPassPercentage || 100}%`;
    if (document.getElementById("hodPendingFees")) document.getElementById("hodPendingFees").textContent = `₹${(s.pendingFees || 0).toLocaleString()}`;
  }
}

async function loadHodStudents(dept = currentDept) {
  const res = await fetchAPI(`/api/students?department=${encodeURIComponent(dept)}`);
  if (res.success && res.students) {
    hodAllStudents = res.students;
    filterHodStudentsTable();
  } else {
    hodAllStudents = [];
    renderHodStudentsTable([]);
  }
}

function filterHodStudentsTable() {
  const q = (document.getElementById("hodSearchInput")?.value || "").toLowerCase().trim();
  const year = document.getElementById("hodYearFilter")?.value || "All";
  const sem = document.getElementById("hodSemFilter")?.value || "All";
  const div = document.getElementById("hodDivFilter")?.value || "All";

  const filtered = hodAllStudents.filter(s => {
    const matchesSearch = !q || (s.name || "").toLowerCase().includes(q) || (s.id || "").toLowerCase().includes(q) || (s.roll_number || "").toLowerCase().includes(q) || (s.email || "").toLowerCase().includes(q);
    const matchesYear = year === "All" || s.year === year;
    const matchesSem = sem === "All" || s.semester === sem;
    const matchesDiv = div === "All" || s.division === div;
    return matchesSearch && matchesYear && matchesSem && matchesDiv;
  });

  renderHodStudentsTable(filtered);
}

function renderHodStudentsTable(students) {
  const tbody = document.getElementById("hodStudentsTableBody");
  if (!tbody) return;

  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No matching student records found for ${currentDept}.</td></tr>`;
    return;
  }

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
    </tr>
  `).join("");
}

// Faculty-Student Assignment Module Functions
async function loadHodFacultyList(dept = currentDept) {
  const res = await fetchAPI(`/api/faculty?department=${encodeURIComponent(dept)}`);
  const select = document.getElementById("assignFacultySelect");
  if (!select) return;

  if (res.success && res.faculty && res.faculty.length > 0) {
    departmentFacultyList = res.faculty;
    select.innerHTML = `<option value="">-- Select Faculty Member --</option>` + res.faculty.map(f => `
      <option value="${f.id}">${f.name} (${f.designation || 'Faculty'})</option>
    `).join("");
  } else {
    departmentFacultyList = [];
    select.innerHTML = `<option value="">No Faculty Found in ${dept}</option>`;
  }

  document.getElementById("assignedStudentsTableBody").innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">Select a faculty member above to manage assignments.</td></tr>`;
  document.getElementById("assignedCountBadge").textContent = `0 Assigned`;
  renderAssignStudentPool();
}

async function onAssignFacultyChange() {
  const select = document.getElementById("assignFacultySelect");
  currentFacultyId = select ? select.value : "";
  
  if (!currentFacultyId) {
    document.getElementById("assignedStudentsTableBody").innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">Select a faculty member above to manage assignments.</td></tr>`;
    document.getElementById("assignedCountBadge").textContent = `0 Assigned`;
    currentAssignedStudents = [];
    renderAssignStudentPool();
    return;
  }

  const res = await fetchAPI(`/api/faculty-students?faculty_id=${encodeURIComponent(currentFacultyId)}`);
  if (res.success && res.students) {
    currentAssignedStudents = res.students;
  } else {
    currentAssignedStudents = [];
  }

  renderAssignedStudentsTable(currentAssignedStudents);
  renderAssignStudentPool();
}

function renderAssignedStudentsTable(assigned) {
  const tbody = document.getElementById("assignedStudentsTableBody");
  const badge = document.getElementById("assignedCountBadge");
  if (badge) badge.textContent = `${assigned.length} Assigned`;
  if (!tbody) return;

  if (assigned.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">No students assigned to this faculty member yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = assigned.map(s => `
    <tr>
      <td class="fw-bold small">${s.id}</td>
      <td class="small">${s.roll_number || 'N/A'}</td>
      <td class="fw-semibold small">${s.name}</td>
      <td class="small">${s.year} / ${s.semester}</td>
      <td class="small"><span class="badge bg-secondary">${s.division || 'A'}</span></td>
      <td>
        <button class="btn btn-sm btn-outline-danger py-0 px-1" onclick="removeFacultyStudentAssignment('${currentFacultyId}', '${s.id}')" title="Remove Assignment">
          <i class="bi bi-x-circle"></i> Remove
        </button>
      </td>
    </tr>
  `).join("");
}

function renderAssignStudentPool() {
  const container = document.getElementById("assignStudentsChecklist");
  if (!container) return;

  if (!currentFacultyId) {
    container.innerHTML = `<div class="text-muted small text-center py-3">Select a faculty member above to view students.</div>`;
    return;
  }

  const poolYear = document.getElementById("assignPoolYear")?.value || "All";
  const poolSem = document.getElementById("assignPoolSem")?.value || "All";

  const assignedIds = new Set(currentAssignedStudents.map(s => s.id));
  
  const pool = hodAllStudents.filter(s => {
    const notAssigned = !assignedIds.has(s.id);
    const matchesYear = poolYear === "All" || s.year === poolYear;
    const matchesSem = poolSem === "All" || s.semester === poolSem;
    return notAssigned && matchesYear && matchesSem;
  });

  if (pool.length === 0) {
    container.innerHTML = `<div class="text-muted small text-center py-3">All matching students are already assigned or no records found.</div>`;
    return;
  }

  container.innerHTML = pool.map(s => `
    <div class="form-check py-1 border-bottom border-light">
      <input class="form-check-input assign-student-cb" type="checkbox" value="${s.id}" id="cb_assign_${s.id}">
      <label class="form-check-label small d-flex justify-content-between cursor-pointer" for="cb_assign_${s.id}">
        <span><strong>${s.roll_number || s.id}</strong> - ${s.name}</span>
        <span class="text-muted">${s.year} (${s.division || 'A'})</span>
      </label>
    </div>
  `).join("");

  const selectAll = document.getElementById("selectAllAssignCheck");
  if (selectAll) selectAll.checked = false;
}

function toggleSelectAllAssign(checked) {
  document.querySelectorAll(".assign-student-cb").forEach(cb => cb.checked = checked);
}

async function submitFacultyStudentAssignment() {
  if (!currentFacultyId) {
    showToast("Please select a faculty member first!", "warning");
    return;
  }

  const selectedCbs = Array.from(document.querySelectorAll(".assign-student-cb:checked"));
  const studentIds = selectedCbs.map(cb => cb.value);

  if (studentIds.length === 0) {
    showToast("Please select at least one student to assign!", "warning");
    return;
  }

  const res = await fetchAPI("/api/faculty-students/assign", {
    method: "POST",
    body: JSON.stringify({
      faculty_id: currentFacultyId,
      student_ids: studentIds
    })
  });

  if (res.success) {
    showToast(res.message, "success");
    await onAssignFacultyChange();
  } else {
    showToast(res.message || "Failed to assign students", "danger");
  }
}

async function removeFacultyStudentAssignment(facultyId, studentId) {
  if (!confirm(`Are you sure you want to remove assignment for student '${studentId}'?`)) return;

  const res = await fetchAPI("/api/faculty-students/remove", {
    method: "POST",
    body: JSON.stringify({
      faculty_id: facultyId,
      student_id: studentId
    })
  });

  if (res.success) {
    showToast("Student assignment removed", "success");
    await onAssignFacultyChange();
  } else {
    showToast(res.message || "Failed to remove student assignment", "danger");
  }
}

// ----------------------------------------------------
// HOD Leadership Directory Functions
// ----------------------------------------------------
async function loadHodData() {
  const res = await fetchAPI("/api/hods");
  if (res.success && res.hods) {
    allHods = res.hods;
    renderHodTable(allHods);
  } else {
    renderHodTable([]);
  }
}

function renderHodTable(hods) {
  const tbody = document.getElementById("hodTableBody");
  if (!tbody) return;

  if (hods.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No HOD records available.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const isAdmin = ["Administrator", "Admin"].includes(user.role);

  tbody.innerHTML = hods.map(h => {
    const isPending = (h.status || "").toLowerCase() === "pending";
    const isInactive = (h.status || "").toLowerCase() === "inactive" || (h.status || "").toLowerCase() === "rejected";
    const statusBadge = isPending 
      ? `<span class="badge bg-warning text-dark fw-bold">PENDING</span>` 
      : isInactive 
        ? `<span class="badge bg-danger">${(h.status || 'INACTIVE').toUpperCase()}</span>` 
        : `<span class="badge bg-success">ACTIVE</span>`;

    return `
      <tr>
        <td class="fw-bold"><span class="badge bg-secondary">${h.department}</span></td>
        <td class="fw-semibold">${h.name}</td>
        <td>${h.qualification || 'Ph.D.'}</td>
        <td>${h.experience || '10 Years'}</td>
        <td>${h.email}</td>
        <td>${h.contact}</td>
        <td>${statusBadge}</td>
        <td>
          ${isAdmin ? `
            <button class="btn btn-sm btn-outline-primary py-0 px-2 me-1" onclick="editHod('${h.department}')" title="Edit / Reassign HOD"><i class="bi bi-pencil"></i> Edit</button>
            ${isPending ? `
              <button class="btn btn-sm btn-success me-1" onclick="approveHodDirect('${h.user_id || h.id || ''}', '${h.email}', '${h.department}')" title="Approve & Activate"><i class="bi bi-check-circle"></i> Approve</button>
            ` : ''}
            <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteHod('${h.id || h.department}')" title="Delete"><i class="bi bi-trash"></i> Delete</button>
          ` : `<span class="text-muted small"><i class="bi bi-check2 me-1"></i> Active HOD</span>`}
        </td>
      </tr>
    `;
  }).join("");
}

// ----------------------------------------------------
// Assign / Edit HOD Modal Helpers
// ----------------------------------------------------
async function openAssignHodModal(dept = currentDept) {
  isEditingHod = false;

  const titleEl = document.getElementById("addHodModalTitle");
  if (titleEl) titleEl.innerHTML = `<i class="bi bi-person-badge me-2"></i> Assign Head of Department (HOD)`;

  const deptEl = document.getElementById("modalHodDepartment");
  if (deptEl) deptEl.value = dept;

  document.getElementById("modalHodFacultyId").value = "";
  document.getElementById("modalHodName").value = "";
  document.getElementById("modalHodQualification").value = "Ph.D. in Engineering";
  document.getElementById("modalHodExperience").value = "10 Years";
  document.getElementById("modalHodEmail").value = "";
  document.getElementById("modalHodContact").value = "";
  if (document.getElementById("modalHodPassword")) document.getElementById("modalHodPassword").value = "";

  await loadModalFacultyOptions(dept);
  openModal("addHodModal");
}

async function loadModalFacultyOptions(dept) {
  const select = document.getElementById("modalHodFacultySelect");
  if (!select) return;

  select.innerHTML = `<option value="">-- Loading Department Faculty... --</option>`;
  const res = await fetchAPI(`/api/faculty?department=${encodeURIComponent(dept)}`);
  
  if (res.success && res.faculty && res.faculty.length > 0) {
    select.innerHTML = `<option value="">-- Or Create New / External HOD --</option>` + res.faculty.map(f => `
      <option value="${f.id}" data-name="${encodeURIComponent(f.name)}" data-email="${encodeURIComponent(f.email)}" data-mobile="${encodeURIComponent(f.mobile || '')}" data-exp="${encodeURIComponent(f.experience || '8 Years')}">
        Promote: ${f.name} (${f.id} - ${f.designation || 'Faculty'})
      </option>
    `).join("");
  } else {
    select.innerHTML = `<option value="">-- No Faculty in ${dept} (Create New HOD) --</option>`;
  }
}

async function onModalDeptChange(dept) {
  await loadModalFacultyOptions(dept);
}

function onModalFacultySelect(facultyId) {
  const select = document.getElementById("modalHodFacultySelect");
  const opt = select.options[select.selectedIndex];
  const fidInput = document.getElementById("modalHodFacultyId");

  if (!facultyId || !opt) {
    if (fidInput) fidInput.value = "";
    return;
  }

  const fName = decodeURIComponent(opt.getAttribute("data-name") || "");
  const fEmail = decodeURIComponent(opt.getAttribute("data-email") || "");
  const fMobile = decodeURIComponent(opt.getAttribute("data-mobile") || "");
  const fExp = decodeURIComponent(opt.getAttribute("data-exp") || "10 Years");

  if (fidInput) fidInput.value = facultyId;
  if (fName && document.getElementById("modalHodName")) document.getElementById("modalHodName").value = fName;
  if (fEmail && document.getElementById("modalHodEmail")) document.getElementById("modalHodEmail").value = fEmail;
  if (fMobile && document.getElementById("modalHodContact")) document.getElementById("modalHodContact").value = fMobile;
  if (fExp && document.getElementById("modalHodExperience")) document.getElementById("modalHodExperience").value = fExp;
}

async function editHod(department) {
  const h = allHods.find(x => x.department === department);
  if (!h) return;
  isEditingHod = true;

  const titleEl = document.getElementById("addHodModalTitle");
  if (titleEl) titleEl.innerHTML = `<i class="bi bi-pencil-square me-2"></i> Update / Reassign HOD — ${department}`;

  const deptEl = document.getElementById("modalHodDepartment");
  const nameEl = document.getElementById("modalHodName");
  const qualEl = document.getElementById("modalHodQualification");
  const expEl = document.getElementById("modalHodExperience");
  const emailEl = document.getElementById("modalHodEmail");
  const contactEl = document.getElementById("modalHodContact");
  const fidInput = document.getElementById("modalHodFacultyId");

  if (deptEl) deptEl.value = h.department;
  if (nameEl) nameEl.value = h.name || "";
  if (qualEl) qualEl.value = h.qualification || "Ph.D.";
  if (expEl) expEl.value = h.experience || "10 Years";
  if (emailEl) emailEl.value = h.email || "";
  if (contactEl) contactEl.value = h.contact || "";
  if (fidInput) fidInput.value = h.faculty_id || "";

  await loadModalFacultyOptions(h.department);
  openModal("addHodModal");
}

async function approveHodDirect(userId, email, department) {
  const res = await fetchAPI("/api/admin/approve-user", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, id: userId, email: email, department: department })
  });
  if (res.success) {
    showToast("HOD account approved and activated successfully!", "success");
    loadHodData();
  } else {
    showToast(res.message || "Approval failed", "danger");
  }
}

async function saveHodForm(e) {
  e.preventDefault();
  const submitBtn = e.target.querySelector('button[type="submit"]') || document.querySelector('#addHodModal button[type="submit"]');
  const originalHtml = submitBtn ? submitBtn.innerHTML : "";

  const selectedDept = document.getElementById("modalHodDepartment").value;
  const existingHodInDept = allHods.some(h => h.department === selectedDept);

  const payload = {
    is_edit: isEditingHod,
    reassign: existingHodInDept,
    department: selectedDept,
    faculty_id: document.getElementById("modalHodFacultyId").value || undefined,
    name: document.getElementById("modalHodName").value.trim(),
    qualification: document.getElementById("modalHodQualification").value.trim(),
    experience: document.getElementById("modalHodExperience").value.trim(),
    email: document.getElementById("modalHodEmail").value.trim(),
    contact: document.getElementById("modalHodContact").value.trim(),
    password: (document.getElementById("modalHodPassword")?.value || "").trim()
  };

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving HOD Record...';
  }

  try {
    const res = await fetchAPI("/api/hods", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (res.success) {
      isEditingHod = false;
      closeModal("addHodModal");
      await loadHodData();
      await loadHodDashboardStats(payload.department);
      if (res.credentials) {
        showCredentialModal(res.credentials);
      } else {
        showToast(res.message || "HOD record saved successfully!", "success");
      }
    } else {
      showToast(res.message || "Failed to save HOD record", "danger");
    }
  } catch (err) {
    showToast("Network error while saving HOD record", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml;
    }
  }
}

async function deleteHod(idOrDept) {
  if (!confirm(`Are you sure you want to delete HOD leadership record for '${idOrDept}'?`)) return;

  const res = await fetchAPI(`/api/hods?id=${encodeURIComponent(idOrDept)}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("HOD record deleted successfully", "success");
    await loadHodData();
    await loadHodDashboardStats(currentDept);
  } else {
    showToast(res.message || "Failed to delete HOD", "danger");
  }
}
