/**
 * Dashboard Controller - Role-Based Dashboard Architecture (Admin vs HOD vs Faculty vs Student)
 */
let facultyAssignedStudents = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    setupRoleViews(user);
    loadDashboardData(user);
  }
});

function setupRoleViews(user) {
  const role = user.role;
  const dept = user.department || "General";

  const titleEl = document.getElementById("dashWelcomeTitle");
  const subEl = document.getElementById("dashWelcomeSubtitle");
  const badgeEl = document.getElementById("dashRoleScopeBadge");

  const adminMatrix = document.getElementById("adminDeptMatrixSection");
  const adminPending = document.getElementById("adminPendingUsersSection");
  const hodSection = document.getElementById("hodDepartmentSection");
  const facSection = document.getElementById("facultyMyStudentsSection");

  if (["Administrator", "Admin"].includes(role)) {
    if (titleEl) titleEl.textContent = "Institute Global Executive Dashboard";
    if (subEl) subEl.textContent = "Institute-wide analytics, all-department performance, faculty operations, and user approvals.";
    if (badgeEl) badgeEl.innerHTML = `<i class="bi bi-shield-lock-fill me-1"></i> Global Institute Scope (All Departments)`;

    if (adminMatrix) adminMatrix.classList.remove("d-none");
    if (adminPending) adminPending.classList.remove("d-none");
    if (hodSection) hodSection.classList.add("d-none");
    if (facSection) facSection.classList.add("d-none");

    const l1 = document.getElementById("labelStatStudents");
    const l2 = document.getElementById("labelStatFaculty");
    const l3 = document.getElementById("labelStatFees");
    if (l1) l1.textContent = "Total Students (All Depts)";
    if (l2) l2.textContent = "Total Faculty (All Depts)";
    if (l3) l3.textContent = "Total Fees Collected";

  } else if (role === "HOD") {
    if (titleEl) titleEl.textContent = `${dept} Executive Dashboard`;
    if (subEl) subEl.textContent = `Strict Department View: Manage ${dept} students, faculty members, academic attendance, and exam pass rates.`;
    if (badgeEl) badgeEl.innerHTML = `<i class="bi bi-building-fill-check me-1"></i> Department: ${dept}`;

    if (adminMatrix) adminMatrix.classList.add("d-none");
    if (adminPending) adminPending.classList.add("d-none");
    if (hodSection) hodSection.classList.remove("d-none");
    if (facSection) facSection.classList.add("d-none");

    const l1 = document.getElementById("labelStatStudents");
    const l2 = document.getElementById("labelStatFaculty");
    const l3 = document.getElementById("labelStatFees");
    if (l1) l1.textContent = `${dept} Students`;
    if (l2) l2.textContent = `${dept} Faculty`;
    if (l3) l3.textContent = `${dept} Fees Collected`;

  } else if (role === "Faculty") {
    if (titleEl) titleEl.textContent = `Faculty Academic & Mentorship Dashboard`;
    if (subEl) subEl.textContent = `Manage assigned students, course timetables, daily attendance, and exam submissions for ${dept}.`;
    if (badgeEl) badgeEl.innerHTML = `<i class="bi bi-person-badge me-1"></i> Faculty: ${user.name || user.username} (${dept})`;

    if (adminMatrix) adminMatrix.classList.add("d-none");
    if (adminPending) adminPending.classList.add("d-none");
    if (hodSection) hodSection.classList.add("d-none");
    if (facSection) facSection.classList.remove("d-none");

    const l1 = document.getElementById("labelStatStudents");
    const l2 = document.getElementById("labelStatFaculty");
    if (l1) l1.textContent = `Assigned Students`;
    if (l2) l2.textContent = `Department Faculty`;

  } else {
    // Student role
    if (titleEl) titleEl.textContent = `Student Academic Portal`;
    if (subEl) subEl.textContent = `Track your attendance, view examination marks, download fee receipts, and read campus notices.`;
    if (badgeEl) badgeEl.innerHTML = `<i class="bi bi-mortarboard-fill me-1"></i> Student: ${user.name || user.username} (${dept})`;

    if (adminMatrix) adminMatrix.classList.add("d-none");
    if (adminPending) adminPending.classList.add("d-none");
    if (hodSection) hodSection.classList.add("d-none");
    if (facSection) facSection.classList.add("d-none");
  }
}

async function loadDashboardData(user) {
  // Fetch stats from backend (server strictly handles RBAC)
  const statsRes = await fetchAPI("/api/dashboard/stats");
  if (statsRes.success && statsRes.stats) {
    const s = statsRes.stats;
    if (document.getElementById("statStudents")) document.getElementById("statStudents").textContent = s.totalStudents || 0;
    if (document.getElementById("statFaculty")) document.getElementById("statFaculty").textContent = s.totalFaculty || 0;
    if (document.getElementById("statFees")) document.getElementById("statFees").textContent = `₹${(s.totalPaidFees || s.paidFees || 0).toLocaleString()}`;
    if (document.getElementById("statNotices")) document.getElementById("statNotices").textContent = s.totalNotices || 0;

    // If Admin: Render Department Matrix & Pending Users
    if (["Administrator", "Admin"].includes(user.role)) {
      if (document.getElementById("adminStatHODs")) document.getElementById("adminStatHODs").textContent = s.totalHODs || 0;
      if (document.getElementById("adminStatDepts")) document.getElementById("adminStatDepts").textContent = s.totalDepartments || 0;
      if (document.getElementById("adminStatAttendance")) document.getElementById("adminStatAttendance").textContent = `${s.attendancePercentage || 100}%`;
      if (document.getElementById("adminStatPassRate")) document.getElementById("adminStatPassRate").textContent = `${s.resultPassPercentage || 100}%`;
      if (document.getElementById("adminStatPendingFees")) document.getElementById("adminStatPendingFees").textContent = `₹${(s.totalPendingFees || 0).toLocaleString()}`;
      if (document.getElementById("adminStatPendingUsers")) document.getElementById("adminStatPendingUsers").textContent = s.pendingUsers || 0;

      if (s.departmentStats) {
        renderAdminDeptMatrix(s.departmentStats);
      }
      await loadAdminPendingApprovals();
    }

    // If HOD: Render Year Distribution, Department Faculty, and Recent Students
    if (user.role === "HOD") {
      if (document.getElementById("hodStatFirstYear")) document.getElementById("hodStatFirstYear").textContent = `${s.firstYearStudents || 0} Students`;
      if (document.getElementById("hodStatSecondYear")) document.getElementById("hodStatSecondYear").textContent = `${s.secondYearStudents || 0} Students`;
      if (document.getElementById("hodStatThirdYear")) document.getElementById("hodStatThirdYear").textContent = `${s.thirdYearStudents || 0} Students`;
      if (document.getElementById("hodStatPassRate")) document.getElementById("hodStatPassRate").textContent = `${s.resultPassPercentage || 100}%`;

      renderHodDeptFaculty(s.departmentFaculty || []);
      renderHodRecentStudents(s.recentStudents || []);
    }
  }

  // If Faculty: Load My Assigned Students
  if (user.role === "Faculty" || user.faculty_id) {
    await loadFacultyMyStudents();
  }

  // Fetch recent notices
  const noticesRes = await fetchAPI("/api/notices");
  const tbody = document.getElementById("dashNoticesTableBody");
  if (tbody) {
    if (noticesRes.success && noticesRes.notices && noticesRes.notices.length > 0) {
      tbody.innerHTML = noticesRes.notices.slice(0, 5).map(n => `
        <tr>
          <td class="fw-bold">${n.title}</td>
          <td><span class="badge bg-secondary">${n.department}</span></td>
          <td>${n.date}</td>
          <td><span class="badge ${n.priority === 'High' ? 'bg-danger' : n.priority === 'Medium' ? 'bg-warning' : 'bg-primary'}">${n.priority}</span></td>
        </tr>
      `).join("");
    } else {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No notices available.</td></tr>`;
    }
  }
}

function renderAdminDeptMatrix(deptStats) {
  const tbody = document.getElementById("adminDeptMatrixTableBody");
  if (!tbody) return;

  if (!deptStats || deptStats.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No department records available.</td></tr>`;
    return;
  }

  tbody.innerHTML = deptStats.map(d => `
    <tr>
      <td>
        <div class="fw-bold text-dark">${d.department}</div>
        <span class="badge bg-light text-muted border">${d.code}</span>
      </td>
      <td>
        <div class="fw-semibold ${d.hod === 'Not Assigned' ? 'text-danger' : 'text-primary'}">
          <i class="bi bi-person-badge me-1"></i> ${d.hod}
        </div>
      </td>
      <td><span class="badge bg-info text-dark px-2 py-1">${d.faculty} Members</span></td>
      <td><span class="badge bg-primary px-2 py-1">${d.students} Students</span></td>
      <td class="fw-bold text-success">₹${(d.paidFees || 0).toLocaleString()}</td>
      <td>
        <div class="d-flex align-items-center gap-2">
          <div class="progress flex-grow-1" style="height: 6px; width: 60px; background-color: #e2e8f0;">
            <div class="progress-bar bg-success" style="width: ${Math.min(100, d.attendanceRate || 0)}%"></div>
          </div>
          <span class="small fw-bold">${d.attendanceRate}%</span>
        </div>
      </td>
      <td>
        <a href="hod.html?department=${encodeURIComponent(d.department)}" class="btn btn-sm btn-outline-primary py-0 px-2 fw-semibold">
          <i class="bi bi-box-arrow-up-right me-1"></i> View Dept
        </a>
      </td>
    </tr>
  `).join("");
}

function renderHodDeptFaculty(facultyList) {
  const tbody = document.getElementById("hodDeptFacultyTableBody");
  if (!tbody) return;

  if (!facultyList || facultyList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No faculty assigned to this department yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = facultyList.map(f => `
    <tr>
      <td class="fw-bold small">${f.id}</td>
      <td class="fw-semibold small">${f.name}</td>
      <td class="small"><span class="badge bg-light text-dark border">${f.designation || 'Faculty'}</span></td>
      <td class="small text-muted">${f.mobile || f.email || 'N/A'}</td>
    </tr>
  `).join("");
}

function renderHodRecentStudents(studentsList) {
  const tbody = document.getElementById("hodRecentStudentsTableBody");
  if (!tbody) return;

  if (!studentsList || studentsList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No students registered in this department yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = studentsList.map(s => `
    <tr>
      <td class="fw-bold small">${s.id}</td>
      <td class="fw-semibold small">${s.name}</td>
      <td class="small"><span class="badge bg-secondary">${s.year || '1st Year'} (${s.semester || 'Sem 1'})</span></td>
      <td class="small text-muted">${s.email || 'N/A'}</td>
    </tr>
  `).join("");
}

async function loadAdminPendingApprovals() {
  const tbody = document.getElementById("adminPendingUsersTableBody");
  const badge = document.getElementById("adminPendingCountBadge");
  if (!tbody) return;

  const res = await fetchAPI("/api/admin/pending-users");
  if (res.success && res.users && res.users.length > 0) {
    if (badge) badge.textContent = `${res.users.length} Pending Approval${res.users.length > 1 ? 's' : ''}`;
    tbody.innerHTML = res.users.map(u => `
      <tr>
        <td class="fw-bold">${u.username}</td>
        <td class="fw-semibold">${u.name}</td>
        <td><span class="badge ${u.role === 'Faculty' ? 'bg-primary' : u.role === 'HOD' ? 'bg-info text-dark' : u.role === 'Administrator' ? 'bg-dark' : 'bg-secondary'}">${u.role}</span></td>
        <td><span class="badge bg-light text-dark border">${u.department || 'General'}</span></td>
        <td>${u.email}</td>
        <td>${u.mobile || 'N/A'}</td>
        <td><span class="badge bg-warning text-dark fw-bold">PENDING</span></td>
        <td>
          <button class="btn btn-sm btn-success me-1 px-2 fw-semibold" onclick="approveUserDirect(${u.id}, '${u.username}', '${u.name}')" title="Approve & Activate"><i class="bi bi-check-circle me-1"></i> Approve</button>
          <button class="btn btn-sm btn-outline-danger px-2 fw-semibold" onclick="rejectUserDirect(${u.id}, '${u.username}', '${u.name}')" title="Reject"><i class="bi bi-x-circle me-1"></i> Reject</button>
        </td>
      </tr>
    `).join("");
  } else {
    if (badge) badge.textContent = `0 Pending Approvals`;
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-success py-3"><i class="bi bi-check2-all me-1"></i> No pending authorizations. All user accounts are active!</td></tr>`;
  }
}

async function approveUserDirect(id, username, name) {
  if (!confirm(`Are you sure you want to approve and activate user account '${name || username}'?`)) return;
  const res = await fetchAPI("/api/admin/approve-user", {
    method: "POST",
    body: JSON.stringify({ id, username })
  });
  if (res.success) {
    showToast(res.message || "User account approved successfully!", "success");
    await loadAdminPendingApprovals();
    // Also update dashboard stats
    const statsRes = await fetchAPI("/api/dashboard/stats");
    if (statsRes.success && statsRes.stats) {
      const s = statsRes.stats;
      if (document.getElementById("statStudents")) document.getElementById("statStudents").textContent = s.totalStudents || 0;
      if (document.getElementById("statFaculty")) document.getElementById("statFaculty").textContent = s.totalFaculty || 0;
      if (s.departmentStats) renderAdminDeptMatrix(s.departmentStats);
    }
  } else {
    showToast(res.message || "Approval failed", "danger");
  }
}

async function rejectUserDirect(id, username, name) {
  if (!confirm(`Are you sure you want to reject user account registration for '${name || username}'?`)) return;
  const res = await fetchAPI("/api/admin/reject-user", {
    method: "POST",
    body: JSON.stringify({ id, username })
  });
  if (res.success) {
    showToast(res.message || "User account rejected.", "warning");
    await loadAdminPendingApprovals();
  } else {
    showToast(res.message || "Rejection failed", "danger");
  }
}

async function loadFacultyMyStudents() {
  const res = await fetchAPI("/api/students?assigned_only=true");
  if (res.success && res.students) {
    facultyAssignedStudents = res.students;
  } else {
    facultyAssignedStudents = [];
  }

  // Calculate stat cards
  const total = facultyAssignedStudents.length;
  const deptCount = facultyAssignedStudents.filter(s => s.department).length;
  const syCount = facultyAssignedStudents.filter(s => s.year === "Second Year").length;
  const sem3Count = facultyAssignedStudents.filter(s => s.semester === "Semester 3").length;

  if (document.getElementById("facStatTotal")) document.getElementById("facStatTotal").textContent = total;
  if (document.getElementById("facStatDept")) document.getElementById("facStatDept").textContent = deptCount;
  if (document.getElementById("facStatYear")) document.getElementById("facStatYear").textContent = syCount;
  if (document.getElementById("facStatSem")) document.getElementById("facStatSem").textContent = sem3Count;
  if (document.getElementById("facultyTotalAssignedBadge")) document.getElementById("facultyTotalAssignedBadge").textContent = `${total} Assigned Students`;

  filterFacultyMyStudents();
}

function filterFacultyMyStudents() {
  const q = (document.getElementById("facSearchInput")?.value || "").toLowerCase().trim();
  const year = document.getElementById("facYearFilter")?.value || "All";
  const sem = document.getElementById("facSemFilter")?.value || "All";
  const div = document.getElementById("facDivFilter")?.value || "All";

  const filtered = facultyAssignedStudents.filter(s => {
    const matchesSearch = !q || (s.name || "").toLowerCase().includes(q) || (s.id || "").toLowerCase().includes(q) || (s.roll_number || "").toLowerCase().includes(q) || (s.email || "").toLowerCase().includes(q);
    const matchesYear = year === "All" || s.year === year;
    const matchesSem = sem === "All" || s.semester === sem;
    const matchesDiv = div === "All" || s.division === div;
    return matchesSearch && matchesYear && matchesSem && matchesDiv;
  });

  const tbody = document.getElementById("facMyStudentsTableBody");
  if (!tbody) return;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No matching assigned students found.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(s => `
    <tr>
      <td class="fw-bold">${s.id}</td>
      <td>${s.roll_number || 'N/A'}</td>
      <td class="fw-semibold">${s.name}</td>
      <td><span class="badge bg-secondary">${s.department}</span></td>
      <td><span class="badge bg-info text-dark">${s.year || 'First Year'}</span></td>
      <td>${s.semester || 'Semester 1'}</td>
      <td><span class="badge bg-dark">${s.division || 'A'}</span></td>
      <td>${s.email}</td>
      <td>${s.mobile}</td>
    </tr>
  `).join("");
}

// ----------------------------------------------------
// Dashboard Password Modal Handlers
// ----------------------------------------------------
function openDashboardPasswordModal() {
  const user = getSession() || {};
  const userEl = document.getElementById("dashModalUsername");
  const roleEl = document.getElementById("dashModalRole");

  if (userEl) userEl.textContent = user.username || user.name || "User";
  if (roleEl) roleEl.textContent = user.role || "Role";

  if (document.getElementById("dashNewPassword")) document.getElementById("dashNewPassword").value = "";
  if (document.getElementById("dashConfirmPassword")) document.getElementById("dashConfirmPassword").value = "";
  if (document.getElementById("dashPassStrength")) document.getElementById("dashPassStrength").classList.add("d-none");

  openModal("dashPasswordModal");
}

async function handleDashboardPasswordSubmit(e) {
  e.preventDefault();
  const newPass = (document.getElementById("dashNewPassword")?.value || "").trim();
  const confirmPass = (document.getElementById("dashConfirmPassword")?.value || "").trim();

  if (newPass.length < 6) {
    showToast("Password must be at least 6 characters long!", "warning");
    return;
  }

  if (newPass !== confirmPass) {
    showToast("Passwords do not match! Please verify and try again.", "danger");
    return;
  }

  const submitBtn = document.getElementById("btnSubmitDashPass");
  const originalHtml = submitBtn ? submitBtn.innerHTML : "";
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';
  }

  try {
    const user = getSession() || {};
    const res = await fetchAPI("/api/auth/profile", {
      method: "POST",
      body: JSON.stringify({
        password: newPass
      })
    });

    if (res.success) {
      closeModal("dashPasswordModal");
      showToast("Account password updated successfully!", "success");
    } else {
      showToast(res.message || "Failed to update password", "danger");
    }
  } catch (err) {
    showToast("Network error updating password", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml;
    }
  }
}

