/**
 * Faculty Module Controller
 */
let allFaculty = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadFacultyData();
  }
});

async function loadFacultyData() {
  const res = await fetchAPI("/api/faculty");
  if (res.success && res.faculty) {
    allFaculty = res.faculty;
    renderFacultyTable(allFaculty);
  } else {
    renderFacultyTable([]);
  }
}

function renderFacultyTable(facultyList) {
  const tbody = document.getElementById("facultyTableBody");
  const badge = document.getElementById("facultyCountBadge");
  if (badge) badge.textContent = `${facultyList.length} Members`;

  if (!tbody) return;

  if (facultyList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No data available.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const canEdit = user.role === "HOD";

  tbody.innerHTML = facultyList.map(f => {
    const isPending = (f.status || "").toLowerCase() === "pending";
    const isInactive = (f.status || "").toLowerCase() === "inactive" || (f.status || "").toLowerCase() === "rejected";
    const statusBadge = isPending 
      ? `<span class="badge bg-warning text-dark fw-bold">PENDING</span>` 
      : isInactive 
        ? `<span class="badge bg-danger">${(f.status || 'INACTIVE').toUpperCase()}</span>` 
        : `<span class="badge bg-success">ACTIVE</span>`;

    return `
      <tr>
        <td class="fw-bold">${f.id}</td>
        <td class="fw-semibold">${f.name}</td>
        <td><span class="badge bg-secondary">${f.department}</span></td>
        <td>${f.designation}</td>
        <td>${f.email}</td>
        <td>${f.mobile}</td>
        <td>${f.experience || '1 Year'}</td>
        <td>${statusBadge}</td>
        <td>
          ${canEdit ? `
            ${isPending ? `
              <button class="btn btn-sm btn-success me-1" onclick="approveFacultyDirect('${f.user_id || f.id}', '${f.email}', '${f.id}')" title="Approve & Activate"><i class="bi bi-check-circle"></i> Approve</button>
            ` : ''}
            <button class="btn btn-sm btn-outline-primary me-1" onclick="editFaculty('${f.id}')" title="Edit"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteFaculty('${f.id}')" title="Delete"><i class="bi bi-trash"></i></button>
          ` : `<span class="text-muted small">View Only</span>`}
        </td>
      </tr>
    `;
  }).join("");
}

async function approveFacultyDirect(userId, email, facultyId) {
  const res = await fetchAPI("/api/admin/approve-user", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, id: userId, email: email, faculty_id: facultyId })
  });
  if (res.success) {
    showToast("Faculty account approved and activated successfully!", "success");
    loadFacultyData();
  } else {
    showToast(res.message || "Approval failed", "danger");
  }
}


function filterFacultyTable() {
  const q = (document.getElementById("searchFacultyInput")?.value || "").toLowerCase();
  const dept = document.getElementById("filterFacultyDept")?.value || "All";

  const filtered = allFaculty.filter(f => {
    const matchesSearch = (f.name || "").toLowerCase().includes(q) || (f.id || "").toLowerCase().includes(q) || (f.email || "").toLowerCase().includes(q) || (f.designation || "").toLowerCase().includes(q);
    const matchesDept = dept === "All" || f.department === dept;
    return matchesSearch && matchesDept;
  });

  renderFacultyTable(filtered);
}

async function saveFacultyForm(e) {
  e.preventDefault();
  const payload = {
    id: document.getElementById("modalFacultyId").value.trim(),
    name: document.getElementById("modalFacultyName").value.trim(),
    department: document.getElementById("modalFacultyDept").value,
    designation: document.getElementById("modalFacultyDesignation").value.trim(),
    email: document.getElementById("modalFacultyEmail").value.trim(),
    mobile: document.getElementById("modalFacultyMobile").value.trim(),
    experience: document.getElementById("modalFacultyExperience").value.trim(),
    status: document.getElementById("modalFacultyStatus").value,
    password: (document.getElementById("modalFacultyPassword")?.value || "").trim()
  };

  const res = await fetchAPI("/api/faculty", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    closeModal("addFacultyModal");
    loadFacultyData();
    if (res.credentials) {
      showCredentialModal(res.credentials);
    } else {
      showToast(res.message || "Faculty saved successfully!", "success");
    }
  } else {
    showToast(res.message || "Failed to save faculty record", "danger");
  }
}

function editFaculty(id) {
  const f = allFaculty.find(item => item.id === id);
  if (!f) return;

  document.getElementById("modalFacultyId").value = f.id;
  document.getElementById("modalFacultyName").value = f.name || "";
  document.getElementById("modalFacultyDept").value = f.department || "Computer Engineering";
  document.getElementById("modalFacultyDesignation").value = f.designation || "Assistant Professor";
  document.getElementById("modalFacultyEmail").value = f.email || "";
  document.getElementById("modalFacultyMobile").value = f.mobile || "";
  document.getElementById("modalFacultyExperience").value = f.experience || "1 Year";
  document.getElementById("modalFacultyStatus").value = f.status || "Active";

  openModal("addFacultyModal");
}

async function deleteFaculty(id) {
  if (!confirm(`Are you sure you want to delete faculty member '${id}'?`)) return;

  const res = await fetchAPI(`/api/faculty?id=${encodeURIComponent(id)}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Faculty member deleted", "success");
    loadFacultyData();
  } else {
    showToast(res.message || "Failed to delete faculty member", "danger");
  }
}
