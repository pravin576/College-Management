/**
 * Contact Inquiries Module Controller
 */
document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadContactData();
  }
});

async function loadContactData() {
  const res = await fetchAPI("/api/contact");
  const tbody = document.getElementById("contactTableBody");
  if (!tbody) return;

  if (res.success && res.contacts && res.contacts.length > 0) {
    tbody.innerHTML = res.contacts.map(c => `
      <tr>
        <td class="small text-muted">${c.date}</td>
        <td class="fw-bold">${c.name}</td>
        <td><a href="mailto:${c.email}">${c.email}</a></td>
        <td class="fw-semibold">${c.subject}</td>
        <td class="small" style="max-width: 300px; white-space: pre-wrap;">${c.message}</td>
        <td>
          <button class="btn btn-sm btn-outline-danger" onclick="deleteContact('${c.id}')" title="Delete Inquiry"><i class="bi bi-trash"></i></button>
        </td>
      </tr>
    `).join("");
  } else {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No data available.</td></tr>`;
  }
}

async function deleteContact(id) {
  if (!confirm("Are you sure you want to delete this contact message?")) return;

  const res = await fetchAPI(`/api/contact?id=${encodeURIComponent(id)}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Contact message deleted", "success");
    loadContactData();
  } else {
    showToast(res.message || "Failed to delete message", "danger");
  }
}
