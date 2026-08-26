/**
 * Notices Module Controller with File Attachment Upload Support
 */
let allNotices = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadNoticesData();
  }
});

async function loadNoticesData() {
  const res = await fetchAPI("/api/notices");
  if (res.success && res.notices) {
    allNotices = res.notices;
    renderNoticesCards(allNotices);
  } else {
    renderNoticesCards([]);
  }
}

function renderNoticesCards(notices) {
  const container = document.getElementById("noticesCardsContainer");
  if (!container) return;

  if (notices.length === 0) {
    container.innerHTML = `<div class="col-12 text-center text-muted py-5"><i class="bi bi-megaphone fs-1 d-block mb-2 text-muted"></i> No data available.</div>`;
    return;
  }

  const user = getSession() || {};
  const canDelete = ["Administrator", "Admin", "HOD"].includes(user.role);

  container.innerHTML = notices.map(n => `
    <div class="col-md-6 col-lg-4">
      <div class="card shadow-sm h-100 position-relative">
        <div class="card-header bg-white d-flex justify-content-between align-items-center">
          <span class="badge ${n.priority === 'High' ? 'bg-danger' : n.priority === 'Medium' ? 'bg-warning' : 'bg-primary'}">${n.priority} Priority</span>
          <small class="text-muted"><i class="bi bi-calendar-event me-1"></i>${n.date}</small>
        </div>
        <div class="card-body">
          <h5 class="card-title fw-bold text-dark mb-2">${n.title}</h5>
          <div class="mb-2">
            <span class="badge bg-secondary me-1"><i class="bi bi-building me-1"></i>${n.department}</span>
            <span class="badge bg-light text-dark border"><i class="bi bi-people me-1"></i>Target: ${n.target_role || 'All'}</span>
          </div>
          <p class="card-text text-muted small mt-2 leading-relaxed" style="white-space: pre-line;">${n.description}</p>
          
          ${n.attachment ? `
            <div class="mt-3 pt-2 border-top">
              <a href="${n.attachment}" target="_blank" class="btn btn-sm btn-outline-primary w-100 fw-semibold">
                <i class="bi bi-paperclip me-1"></i> Download / View Attachment
              </a>
            </div>
          ` : ''}
        </div>
        <div class="card-footer bg-light d-flex justify-content-between align-items-center">
          <small class="text-muted">By: <strong>${n.author || 'Administration'}</strong></small>
          ${canDelete ? `
            <button class="btn btn-sm btn-outline-danger" onclick="deleteNotice('${n.id}')" title="Delete Notice"><i class="bi bi-trash"></i></button>
          ` : ''}
        </div>
      </div>
    </div>
  `).join("");
}

async function saveNoticeForm(e) {
  e.preventDefault();
  
  let attachmentUrl = "";
  const fileInput = document.getElementById("noticeFileInput");
  if (fileInput && fileInput.files.length > 0) {
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    const uploadRes = await fetchAPI("/api/upload", {
      method: "POST",
      body: formData
    });

    if (uploadRes.success && uploadRes.filePath) {
      attachmentUrl = uploadRes.filePath;
    } else {
      showToast("File upload failed, publishing notice without attachment.", "warning");
    }
  }

  const payload = {
    title: document.getElementById("noticeTitle").value.trim(),
    department: document.getElementById("noticeDepartment").value,
    targetRole: document.getElementById("noticeTargetRole").value,
    priority: document.getElementById("noticePriority").value,
    description: document.getElementById("noticeDescription").value.trim(),
    attachment: attachmentUrl,
    date: new Date().toISOString().split("T")[0]
  };

  const res = await fetchAPI("/api/notices", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    showToast(res.message || "Notice published successfully!", "success");
    closeModal("publishNoticeModal");
    loadNoticesData();
  } else {
    showToast(res.message || "Failed to publish notice", "danger");
  }
}

async function deleteNotice(id) {
  if (!confirm("Are you sure you want to delete this notice?")) return;

  const res = await fetchAPI(`/api/notices?id=${encodeURIComponent(id)}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Notice deleted", "success");
    loadNoticesData();
  } else {
    showToast(res.message || "Failed to delete notice", "danger");
  }
}
