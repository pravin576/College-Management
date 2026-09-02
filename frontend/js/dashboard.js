/**
 * Dashboard Controller
 */
let facultyAssignedStudents = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadDashboardData(user);
  }
});

async function loadDashboardData(user) {
  // Fetch stats from backend
  const statsRes = await fetchAPI("/api/dashboard/stats");
  if (statsRes.success && statsRes.stats) {
    const s = statsRes.stats;
    if (document.getElementById("statStudents")) document.getElementById("statStudents").textContent = s.totalStudents || 0;
    if (document.getElementById("statFaculty")) document.getElementById("statFaculty").textContent = s.totalFaculty || 0;
    if (document.getElementById("statFees")) document.getElementById("statFees").textContent = `₹${(s.totalPaidFees || s.paidFees || 0).toLocaleString()}`;
    if (document.getElementById("statNotices")) document.getElementById("statNotices").textContent = s.totalNotices || 0;
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
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No data available.</td></tr>`;
    }
  }

  // Check if Faculty role or HOD role viewing Faculty My Students
  const facSection = document.getElementById("facultyMyStudentsSection");
  if (facSection && (user.role === "Faculty" || user.faculty_id)) {
    facSection.classList.remove("d-none");
    await loadFacultyMyStudents();
  }

  // Check if Admin viewing Pending User Approvals
  const adminPendingSection = document.getElementById("adminPendingUsersSection");
  if (adminPendingSection && (user.role === "Administrator" || user.role === "Admin")) {
    adminPendingSection.classList.remove("d-none");
    await loadAdminPendingApprovals();
  }
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
