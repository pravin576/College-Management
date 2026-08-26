/**
 * Document Vault Controller
 */
let allDocuments = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadDocumentData();
  }
});

async function loadDocumentData() {
  const res = await fetchAPI("/api/documents");
  if (res.success && res.documents) {
    allDocuments = res.documents;
    filterDocTable();
  } else {
    allDocuments = [];
    renderDocTable([]);
  }
}

function filterDocTable() {
  const q = document.getElementById("searchDocInput").value.toLowerCase().trim();
  const category = document.getElementById("filterDocCategory").value;
  const dept = document.getElementById("filterDocDept").value;

  const filtered = allDocuments.filter(d => {
    const matchQ = !q || (d.title && d.title.toLowerCase().includes(q)) || (d.subject && d.subject.toLowerCase().includes(q));
    const matchCat = category === "All" || d.category === category;
    const matchDept = dept === "All" || d.department === "All" || d.department === dept;
    return matchQ && matchCat && matchDept;
  });

  renderDocTable(filtered);
}

function renderDocTable(docs) {
  const tbody = document.getElementById("docTableBody");
  const countBadge = document.getElementById("docCountBadge");
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${docs.length} Documents`;

  if (docs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No documents available.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const canManage = ["Administrator", "Admin", "HOD", "Faculty"].includes(user.role);

  tbody.innerHTML = docs.map(d => {
    const fp = (d.file_path || '').toLowerCase();
    const isPdf = fp.endsWith('.pdf');
    const isDoc = fp.endsWith('.doc') || fp.endsWith('.docx');
    const isImg = fp.endsWith('.png') || fp.endsWith('.jpg') || fp.endsWith('.jpeg') || fp.endsWith('.gif') || fp.endsWith('.webp');
    const isXls = fp.endsWith('.xls') || fp.endsWith('.xlsx') || fp.endsWith('.csv');
    const icon = isPdf ? 'bi-file-earmark-pdf text-danger' : isDoc ? 'bi-file-earmark-word text-primary' : isImg ? 'bi-file-earmark-image text-success' : isXls ? 'bi-file-earmark-excel text-success' : 'bi-file-earmark-text text-info';

    return `
    <tr>
      <td class="fw-bold text-dark"><i class="bi ${icon} me-2 fs-5"></i>${d.title}</td>
      <td><span class="badge bg-info text-dark">${d.category || 'Notes'}</span></td>
      <td><span class="badge bg-secondary">${d.department || 'All'}</span></td>
      <td>${d.semester || 'All'}</td>
      <td>${d.subject || 'All'}</td>
      <td>${d.uploaded_by || 'Staff'}</td>
      <td class="small text-muted">${d.upload_date ? d.upload_date.split(' ')[0] : 'N/A'}</td>
      <td>
        <a href="${d.file_path || '#'}" target="_blank" class="btn btn-sm btn-outline-primary me-1" title="View/Download"><i class="bi bi-download"></i></a>
        ${canManage ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteDocument('${d.id}')" title="Delete"><i class="bi bi-trash"></i></button>` : ''}
      </td>
    </tr>
  `;
  }).join("");
}

async function saveDocumentForm(e) {
  e.preventDefault();
  const fileInput = document.getElementById("modalDocFileInput");
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast("Please select a file to upload!", "warning");
    return;
  }

  const submitBtn = e.target.querySelector("button[type='submit']");
  const originalText = submitBtn ? submitBtn.innerHTML : "Upload Document";
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Uploading...`;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  try {
    const uploadRes = await fetch("/api/upload", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${getSessionToken()}`,
        "X-Session-Token": getSessionToken()
      },
      body: formData
    });
    const uploadJson = await uploadRes.json();

    if (!uploadJson.success) {
      showToast(uploadJson.message || "File upload failed!", "danger");
      if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = originalText; }
      return;
    }

    const payload = {
      title: document.getElementById("modalDocTitle").value.trim(),
      category: document.getElementById("modalDocCategory").value,
      department: document.getElementById("modalDocDept").value,
      semester: document.getElementById("modalDocSemester").value,
      subject: document.getElementById("modalDocSubject").value.trim(),
      filePath: uploadJson.filePath
    };

    const res = await fetchAPI("/api/documents", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (res.success) {
      showToast("Document uploaded successfully!", "success");
      closeModal("addDocumentModal");
      document.getElementById("docModalForm").reset();
      loadDocumentData();
    } else {
      showToast(res.message || "Failed to save document record", "danger");
    }
  } catch (err) {
    showToast(err?.message || "Error uploading file to server", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalText;
    }
  }
}

async function deleteDocument(docId) {
  if (!confirm("Are you sure you want to delete this document?")) return;

  const res = await fetchAPI(`/api/documents?id=${encodeURIComponent(docId)}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Document deleted successfully!", "success");
    loadDocumentData();
  } else {
    showToast(res.message || "Failed to delete document", "danger");
  }
}
