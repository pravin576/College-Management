/**
 * SimpleERP - Official Government Polytechnic Home Page Controller
 * Handles dynamic fetching for Departments, Notices, Ticker, and Public Contact Inquiries.
 */

document.addEventListener("DOMContentLoaded", () => {
  console.log("Government Polytechnic Portal Initialized.");
  loadPublicDepartments();
  loadPublicNotices();
});

/**
 * Fetch and render college departments from backend database API (/api/departments)
 */
async function loadPublicDepartments() {
  const container = document.getElementById("departmentsContainer");
  if (!container) return;

  try {
    const res = await fetchAPI("/api/departments");
    if (res && res.success && Array.isArray(res.departments) && res.departments.length > 0) {
      let html = `
        <div class="table-responsive">
          <table class="gov-table">
            <thead>
              <tr>
                <th>Department Code</th>
                <th>Department Name</th>
                <th>Description / Details</th>
              </tr>
            </thead>
            <tbody>
      `;
      res.departments.forEach(dept => {
        html += `
          <tr>
            <td><strong>${escapeHTML(dept.code || 'DEPT')}</strong></td>
            <td>${escapeHTML(dept.name || '')}</td>
            <td>${escapeHTML(dept.description || 'Polytechnic Engineering Department')}</td>
          </tr>
        `;
      });
      html += `
            </tbody>
          </table>
        </div>
      `;
      container.innerHTML = html;
    } else {
      container.innerHTML = `
        <div class="p-3 border rounded bg-light text-center">
          <i class="bi bi-info-circle text-muted fs-4 d-block mb-1"></i>
          <span class="text-muted fw-semibold">No data available.</span>
        </div>
      `;
    }
  } catch (err) {
    console.error("Error loading departments:", err);
    container.innerHTML = `
      <div class="p-3 border rounded bg-light text-center">
        <span class="text-muted fw-semibold">No data available.</span>
      </div>
    `;
  }
}

/**
 * Fetch and render official notices from backend database API (/api/public/notices)
 */
let cachedNotices = [];

async function loadPublicNotices() {
  const container = document.getElementById("noticesContainer");
  const ticker = document.getElementById("headerNoticeTicker");

  try {
    const res = await fetchAPI("/api/public/notices");
    if (res && res.success && Array.isArray(res.notices) && res.notices.length > 0) {
      cachedNotices = res.notices;

      // Update Top Notice Ticker with first notice title
      if (ticker) {
        const topNotice = res.notices[0];
        ticker.innerHTML = `
          <strong>[${escapeHTML(topNotice.date || '')}] ${escapeHTML(topNotice.title || '')}</strong>
          ${topNotice.department ? ` - ${escapeHTML(topNotice.department)}` : ''}
        `;
      }

      // Render Notices List
      let html = `<ul class="gov-list-group">`;
      res.notices.slice(0, 5).forEach(notice => {
        const priorityBadge = notice.priority === "High" ? `<span class="gov-notice-badge">IMPORTANT</span>` : '';
        html += `
          <li class="gov-list-item">
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
              <div>
                <h5>${escapeHTML(notice.title)} ${priorityBadge}</h5>
                <p>${escapeHTML(notice.description || 'Official college notice')}</p>
                <div class="mt-1 text-muted small">
                  <span><i class="bi bi-building me-1"></i> Dept: ${escapeHTML(notice.department || 'All')}</span> | 
                  <span><i class="bi bi-person me-1"></i> Issued by: ${escapeHTML(notice.author || 'Administration')}</span>
                </div>
              </div>
              <span class="gov-notice-date"><i class="bi bi-calendar-event me-1"></i> ${escapeHTML(notice.date || '')}</span>
            </div>
          </li>
        `;
      });
      html += `</ul>`;
      if (container) container.innerHTML = html;

    } else {
      cachedNotices = [];
      if (ticker) {
        ticker.textContent = "No urgent announcements at this time.";
      }
      if (container) {
        container.innerHTML = `
          <div class="p-3 border rounded bg-light text-center">
            <i class="bi bi-megaphone text-muted fs-4 d-block mb-1"></i>
            <span class="text-muted fw-semibold">No data available.</span>
          </div>
        `;
      }
    }
  } catch (err) {
    console.error("Error loading notices:", err);
    if (container) {
      container.innerHTML = `
        <div class="p-3 border rounded bg-light text-center">
          <span class="text-muted fw-semibold">No data available.</span>
        </div>
      `;
    }
  }
}

/**
 * Notice Modal Viewer for "View All Notices"
 */
function openAllNoticesModal() {
  const modal = document.getElementById("allNoticesModal");
  const modalList = document.getElementById("modalNoticesList");
  if (!modal || !modalList) return;

  if (cachedNotices.length === 0) {
    modalList.innerHTML = `<p class="text-center text-muted py-3">No data available.</p>`;
  } else {
    let html = `<div class="gov-list-group">`;
    cachedNotices.forEach(notice => {
      const priorityBadge = notice.priority === "High" ? `<span class="gov-notice-badge">IMPORTANT</span>` : '';
      html += `
        <div class="gov-list-item mb-2">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <h6 class="fw-bold m-0 text-primary">${escapeHTML(notice.title)} ${priorityBadge}</h6>
            <small class="text-muted">${escapeHTML(notice.date || '')}</small>
          </div>
          <p class="small text-muted my-1">${escapeHTML(notice.description || '')}</p>
          <div class="small text-muted">Dept: ${escapeHTML(notice.department || 'All')} | Author: ${escapeHTML(notice.author || 'Admin')}</div>
        </div>
      `;
    });
    html += `</div>`;
    modalList.innerHTML = html;
  }

  modal.style.display = "flex";
}

function closeAllNoticesModal() {
  const modal = document.getElementById("allNoticesModal");
  if (modal) modal.style.display = "none";
}

/**
 * Submit Public Inquiry Form to backend REST API (/api/contact)
 */
async function handlePublicContactSubmit(e) {
  e.preventDefault();
  const nameInput = document.getElementById('contactName');
  const emailInput = document.getElementById('contactEmail');
  const subjectInput = document.getElementById('contactSubject');
  const messageInput = document.getElementById('contactMessage');

  const name = nameInput ? nameInput.value.trim() : '';
  const email = emailInput ? emailInput.value.trim() : '';
  const subject = subjectInput ? subjectInput.value.trim() : '';
  const message = messageInput ? messageInput.value.trim() : '';

  if (!name || !email || !subject || !message) {
    if (typeof showToast === "function") showToast('Please fill out all required inquiry fields.', 'warning');
    return;
  }

  try {
    const res = await fetchAPI('/api/contact', {
      method: 'POST',
      body: JSON.stringify({ name, email, subject, message, recipientEmail: 'principal.gpawasari@dtemaharashtra.gov.in' })
    });

    if (res && res.success) {
      if (typeof showToast === "function") {
        showToast('Public inquiry message submitted successfully to college backend!', 'success');
      } else {
        alert('Public inquiry submitted successfully!');
      }
      document.getElementById('contactForm').reset();
    } else {
      if (typeof showToast === "function") {
        showToast(res.message || 'Failed to submit inquiry message', 'danger');
      } else {
        alert('Failed to submit inquiry: ' + (res.message || 'Error'));
      }
    }
  } catch (err) {
    console.error("Error submitting contact form:", err);
    if (typeof showToast === "function") {
      showToast('Error connecting to backend server', 'danger');
    }
  }
}

/**
 * Utility HTML String Escaper
 */
function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
