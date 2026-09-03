/**
 * Timetable Module Controller
 */
let allTimetable = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadTimetableData();
  }
});

async function loadTimetableData() {
  const res = await fetchAPI("/api/timetable");
  if (res.success && res.timetable) {
    allTimetable = res.timetable;
    renderTimetableTable(allTimetable);
  } else {
    renderTimetableTable([]);
  }
}

function renderTimetableTable(recs) {
  const tbody = document.getElementById("timetableTableBody");
  if (!tbody) return;

  if (recs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No data available.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const canEdit = ["Administrator", "Admin", "HOD"].includes(user.role);

  tbody.innerHTML = recs.map(t => `
    <tr>
      <td class="fw-bold text-primary">${t.day}</td>
      <td>${t.time}</td>
      <td><span class="badge bg-secondary">${t.department}</span></td>
      <td>${t.semester} (${t.division})</td>
      <td class="fw-semibold">${t.subject}</td>
      <td>${t.faculty}</td>
      <td><span class="badge bg-light text-dark border">${t.room}</span></td>
      <td class="action-col">
        ${canEdit ? `
          <button class="btn btn-sm btn-outline-primary py-0 px-2 me-1" onclick="editTimetableSlot(${t.id})" title="Edit Slot"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteTimetableSlot(${t.id})" title="Delete"><i class="bi bi-trash"></i></button>
        ` : `<span class="text-muted small">View Only</span>`}
      </td>
    </tr>
  `).join("");

  if (!canEdit) {
    document.querySelectorAll(".action-col").forEach(el => el.style.display = "none");
  }
}

let editingTimetableId = null;

function editTimetableSlot(id) {
  const t = allTimetable.find(x => x.id == id);
  if (!t) return;
  editingTimetableId = id;

  const dayEl = document.getElementById("ttDay");
  const timeEl = document.getElementById("ttTime");
  const deptEl = document.getElementById("ttDepartment");
  const semEl = document.getElementById("ttSemester");
  const divEl = document.getElementById("ttDivision");
  const roomEl = document.getElementById("ttRoom");
  const subjEl = document.getElementById("ttSubject");
  const facEl = document.getElementById("ttFaculty");

  if (dayEl) dayEl.value = t.day || "Monday";
  if (timeEl) timeEl.value = t.time || "";
  if (deptEl) deptEl.value = t.department || "Computer Engineering";
  if (semEl) semEl.value = t.semester || "Semester 1";
  if (divEl) divEl.value = t.division || "A";
  if (roomEl) roomEl.value = t.room || "";
  if (subjEl) subjEl.value = t.subject || "";
  if (facEl) facEl.value = t.faculty || "";

  openModal("addTimetableModal");
}

function filterTimetableTable() {
  const q = (document.getElementById("searchTimetableInput")?.value || "").toLowerCase();
  const dayVal = document.getElementById("filterTimetableDay")?.value || "All";
  const semVal = document.getElementById("filterTimetableSem")?.value || "All";

  const filtered = allTimetable.filter(t => {
    const matchesSearch = (t.subject || "").toLowerCase().includes(q) || (t.faculty || "").toLowerCase().includes(q);
    const matchesDay = dayVal === "All" || t.day === dayVal;
    const matchesSem = semVal === "All" || t.semester === semVal;
    return matchesSearch && matchesDay && matchesSem;
  });

  renderTimetableTable(filtered);
}

async function saveTimetableForm(e) {
  e.preventDefault();
  const payload = {
    id: editingTimetableId,
    day: document.getElementById("ttDay").value,
    time: document.getElementById("ttTime").value.trim(),
    department: document.getElementById("ttDepartment").value,
    semester: document.getElementById("ttSemester").value,
    division: document.getElementById("ttDivision").value.trim(),
    room: document.getElementById("ttRoom").value.trim(),
    subject: document.getElementById("ttSubject").value.trim(),
    faculty: document.getElementById("ttFaculty").value.trim()
  };

  const res = await fetchAPI("/api/timetable", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    showToast(res.message || "Timetable slot saved!", "success");
    editingTimetableId = null;
    closeModal("addTimetableModal");
    loadTimetableData();
  } else {
    showToast(res.message || "Failed to save timetable slot", "danger");
  }
}

async function deleteTimetableSlot(id) {
  if (!confirm("Are you sure you want to delete this timetable slot?")) return;

  const res = await fetchAPI(`/api/timetable?id=${id}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Timetable slot deleted", "success");
    loadTimetableData();
  } else {
    showToast(res.message || "Failed to delete timetable slot", "danger");
  }
}
