/**
 * Fees Module Controller
 */
let allFees = [];
let studentCache = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    if (user.role === "HOD" && user.department) {
      const deptFilter = document.getElementById("filterFeeDept");
      if (deptFilter) {
        deptFilter.value = user.department;
        deptFilter.disabled = true;
      }
    }
    loadFeesData();
    loadStudentLookupCache();
  }
});

async function loadStudentLookupCache() {
  const user = getSession() || {};
  if (user.role === "HOD") {
    try {
      const res = await fetchAPI("/api/students");
      if (res && res.success && res.students) {
        studentCache = res.students;
      }
    } catch (e) {
      console.warn("Student cache load failed", e);
    }
  }
}

function lookupStudentInfo() {
  const idInput = document.getElementById("feeStudentId");
  if (!idInput) return;
  const val = idInput.value.trim().toLowerCase();
  if (!val || studentCache.length === 0) return;

  const match = studentCache.find(s => (s.id && s.id.toLowerCase() === val) || (s.roll_number && s.roll_number.toLowerCase() === val));
  if (match) {
    const nameInput = document.getElementById("feeStudentName");
    const deptSelect = document.getElementById("feeDepartment");
    const user = getSession() || {};

    if (nameInput && (!nameInput.value || nameInput.value === "Student")) {
      nameInput.value = match.name || "";
    }
    if (deptSelect && user.role !== "HOD" && match.department) {
      deptSelect.value = match.department;
    }
    const helpEl = document.getElementById("feeStudentLookupHelp");
    if (helpEl) {
      helpEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle me-1"></i> Found: ${match.name} (${match.department})</span>`;
    }
  }
}

async function loadFeesData() {
  const res = await fetchAPI("/api/fees");
  if (res && res.success && res.fees) {
    allFees = res.fees;
    renderFeesTable(allFees);
    updateFeesStats(allFees);
  } else {
    allFees = [];
    renderFeesTable([]);
    updateFeesStats([]);
  }
}

function updateFeesStats(recs) {
  let paidSum = 0;
  let pendingSum = 0;
  (recs || []).forEach(f => {
    paidSum += parseFloat(f.paid_fees || 0);
    pendingSum += parseFloat(f.pending_fees || 0);
  });

  if (document.getElementById("feeTotalPaid")) document.getElementById("feeTotalPaid").textContent = `₹${paidSum.toLocaleString('en-IN')}`;
  if (document.getElementById("feeTotalPending")) document.getElementById("feeTotalPending").textContent = `₹${pendingSum.toLocaleString('en-IN')}`;
  if (document.getElementById("feeRecordsCount")) document.getElementById("feeRecordsCount").textContent = (recs || []).length;
}

function renderFeesTable(recs) {
  const tbody = document.getElementById("feesTableBody");
  if (!tbody) return;

  if (!recs || recs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4"><i class="bi bi-info-circle me-2"></i> No fee records found.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const isStudent = user.role === "Student";
  const canManage = user.role === "HOD";

  tbody.innerHTML = recs.map(f => {
    const total = parseFloat(f.total_fees || 0);
    const paid = parseFloat(f.paid_fees || 0);
    const pending = parseFloat(f.pending_fees || 0);
    const statusClass = f.payment_status === 'Paid' ? 'bg-success' : f.payment_status === 'Partial' ? 'bg-warning text-dark' : 'bg-danger';

    return `
      <tr>
        <td class="fw-bold">${f.student_id}</td>
        <td class="fw-semibold">${f.student_name}</td>
        <td><span class="badge bg-secondary">${f.department}</span></td>
        <td>₹${total.toLocaleString('en-IN')}</td>
        <td class="text-success fw-bold">₹${paid.toLocaleString('en-IN')}</td>
        <td class="text-danger fw-bold">₹${pending.toLocaleString('en-IN')}</td>
        <td>${f.payment_date || 'N/A'}</td>
        <td><span class="badge ${statusClass}">${f.payment_status}</span></td>
        <td>
          <button class="btn btn-sm btn-outline-success me-1" onclick="viewFeeReceipt(${f.id})" title="Print Official Receipt"><i class="bi bi-receipt"></i></button>
          ${canManage ? `
            <button class="btn btn-sm btn-outline-primary me-1" onclick="editFeeRecord(${f.id})" title="Edit Fee Record"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteFeeRecord(${f.id})" title="Delete Fee Record"><i class="bi bi-trash"></i></button>
          ` : ''}
        </td>
      </tr>
    `;
  }).join("");
}

function filterFeesTable() {
  const q = (document.getElementById("searchFeesInput")?.value || "").toLowerCase().trim();
  const deptVal = document.getElementById("filterFeeDept")?.value || "All";
  const statusVal = document.getElementById("filterFeeStatus")?.value || "All";

  const filtered = allFees.filter(f => {
    const matchesSearch = !q || (f.student_id || "").toLowerCase().includes(q) || (f.student_name || "").toLowerCase().includes(q);
    const matchesDept = deptVal === "All" || f.department === deptVal;
    const matchesStatus = statusVal === "All" || f.payment_status === statusVal;
    return matchesSearch && matchesDept && matchesStatus;
  });

  renderFeesTable(filtered);
  updateFeesStats(filtered);
}

function openPayFeeModal() {
  const user = getSession() || {};
  const myFee = allFees.find(f => f.student_id === user.student_id || f.student_id === user.username) || (allFees.length > 0 ? allFees[0] : null);

  const infoEl = document.getElementById("payFeeStudentInfo");
  const payInput = document.getElementById("payFeeAmount");
  const submitBtn = document.getElementById("btnConfirmFeePay");

  if (myFee) {
    const pending = Math.max(0, parseFloat(myFee.pending_fees || 0));
    const total = parseFloat(myFee.total_fees || 0);
    const paid = parseFloat(myFee.paid_fees || 0);

    if (infoEl) {
      infoEl.innerHTML = `
        <div class="card bg-light border-0 mb-3">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between mb-2">
              <span class="text-muted small">Student:</span>
              <span class="fw-bold">${myFee.student_name} (${myFee.student_id})</span>
            </div>
            <div class="d-flex justify-content-between mb-1 small">
              <span>Total Fees:</span>
              <span>₹${total.toLocaleString('en-IN')}</span>
            </div>
            <div class="d-flex justify-content-between mb-1 small">
              <span class="text-success">Paid to Date:</span>
              <span class="text-success fw-bold">₹${paid.toLocaleString('en-IN')}</span>
            </div>
            <div class="d-flex justify-content-between border-top pt-2">
              <span class="fw-bold text-danger">Pending Balance:</span>
              <span class="fw-bold text-danger fs-6">₹${pending.toLocaleString('en-IN')}</span>
            </div>
          </div>
        </div>
      `;
    }

    if (pending <= 0) {
      if (payInput) {
        payInput.value = "0";
        payInput.disabled = true;
      }
      if (submitBtn) submitBtn.disabled = true;
      showToast("All your fees are already fully paid. No pending balance remaining.", "info");
    } else {
      if (payInput) {
        payInput.value = pending;
        payInput.max = pending;
        payInput.min = 1;
        payInput.disabled = false;
      }
      if (submitBtn) submitBtn.disabled = false;
    }
  } else {
    if (infoEl) {
      infoEl.innerHTML = `<div class="alert alert-warning py-2 small mb-3">No active fee record found for your account. Please contact college administration.</div>`;
    }
    if (payInput) payInput.disabled = true;
    if (submitBtn) submitBtn.disabled = true;
  }

  openModal("payFeeModal");
}

async function handlePayFeeSubmit(e) {
  e.preventDefault();
  const payAmount = parseFloat(document.getElementById("payFeeAmount")?.value || 0);
  if (payAmount <= 0) {
    showToast("Please enter a valid payment amount", "danger");
    return;
  }

  const submitBtn = document.getElementById("btnConfirmFeePay");
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Processing...`;
  }

  try {
    const res = await fetchAPI("/api/fees", {
      method: "POST",
      body: JSON.stringify({ payAmount })
    });

    if (res && res.success) {
      showToast(res.message || "Fee payment recorded successfully!", "success");
      closeModal("payFeeModal");
      await loadFeesData();
      const user = getSession() || {};
      viewFeeReceipt(user.student_id || user.username || "");
    } else {
      showToast(res.message || "Payment processing failed", "danger");
    }
  } catch (err) {
    showToast("Payment failed due to connection error", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `Confirm Payment`;
    }
  }
}

function openAddFeeModal() {
  const user = getSession() || {};
  if (user.role !== "HOD") {
    showToast("Permission denied: Only HODs are authorized to manage student fee records", "danger");
    return;
  }

  const form = document.getElementById("manageFeeForm");
  if (form) form.reset();

  document.getElementById("feeRecordDbId").value = "";
  const stuInput = document.getElementById("feeStudentId");
  if (stuInput) {
    stuInput.value = "";
    stuInput.readOnly = false;
  }
  document.getElementById("feeStudentName").value = "";
  document.getElementById("feeTotal").value = "85000";
  document.getElementById("feePaid").value = "0";

  const deptSelect = document.getElementById("feeDepartment");
  if (deptSelect) {
    if (user.department) {
      deptSelect.value = user.department;
      deptSelect.disabled = true;
    } else {
      deptSelect.disabled = false;
    }
  }

  const helpEl = document.getElementById("feeStudentLookupHelp");
  if (helpEl) helpEl.innerHTML = `Enter student enrollment number or roll number.`;

  const titleEl = document.getElementById("manageFeeModalTitle");
  if (titleEl) titleEl.innerHTML = `<i class="bi bi-plus-circle me-2"></i> Add Student Fee Record`;

  openModal("manageFeeModal");
}

function editFeeRecord(id) {
  const user = getSession() || {};
  if (user.role !== "HOD") {
    showToast("Permission denied: Only HODs are authorized to edit student fee records", "danger");
    return;
  }

  const f = allFees.find(item => item.id === id);
  if (!f) return;

  document.getElementById("feeRecordDbId").value = f.id;
  const stuInput = document.getElementById("feeStudentId");
  if (stuInput) {
    stuInput.value = f.student_id;
    stuInput.readOnly = true;
  }
  document.getElementById("feeStudentName").value = f.student_name;

  const deptSelect = document.getElementById("feeDepartment");
  if (deptSelect) {
    deptSelect.value = f.department || user.department || "Computer Engineering";
    deptSelect.disabled = true;
  }

  document.getElementById("feeTotal").value = f.total_fees;
  document.getElementById("feePaid").value = f.paid_fees;

  const helpEl = document.getElementById("feeStudentLookupHelp");
  if (helpEl) helpEl.innerHTML = `<span class="text-muted">Editing fee structure for ${f.student_name}</span>`;

  const titleEl = document.getElementById("manageFeeModalTitle");
  if (titleEl) titleEl.innerHTML = `<i class="bi bi-pencil-square me-2"></i> Update Student Fee Record`;

  openModal("manageFeeModal");
}

async function saveFeeRecordForm(e) {
  e.preventDefault();
  const user = getSession() || {};
  const deptSelect = document.getElementById("feeDepartment");
  const department = (user.role === "HOD" && user.department) ? user.department : (deptSelect ? deptSelect.value : "Computer Engineering");

  const total = parseFloat(document.getElementById("feeTotal")?.value || 0);
  const paid = parseFloat(document.getElementById("feePaid")?.value || 0);

  if (paid > total) {
    showToast("Paid amount cannot exceed total fees", "warning");
    return;
  }

  const payload = {
    id: document.getElementById("feeRecordDbId")?.value ? parseInt(document.getElementById("feeRecordDbId").value) : null,
    studentId: (document.getElementById("feeStudentId")?.value || "").trim(),
    studentName: (document.getElementById("feeStudentName")?.value || "").trim(),
    department: department,
    totalFees: total,
    paidFees: paid
  };

  const res = await fetchAPI("/api/fees", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res && res.success) {
    showToast(res.message || "Fee record saved successfully", "success");
    closeModal("manageFeeModal");
    loadFeesData();
  } else {
    showToast(res?.message || "Failed to save fee record", "danger");
  }
}

async function deleteFeeRecord(id) {
  if (!confirm("Are you sure you want to permanently delete this fee record?")) return;

  const res = await fetchAPI(`/api/fees?id=${id}`, {
    method: "DELETE"
  });

  if (res && res.success) {
    showToast("Fee record deleted successfully", "success");
    loadFeesData();
  } else {
    showToast(res?.message || "Failed to delete fee record", "danger");
  }
}

async function viewFeeReceipt(feeId) {
  const user = getSession() || {};
  const queryId = feeId || user.student_id || user.username || "";

  const res = await fetchAPI(`/api/fees/receipt?id=${encodeURIComponent(queryId)}`);
  if (res && res.success && res.receipt) {
    const r = res.receipt;
    if (document.getElementById("recNumber")) document.getElementById("recNumber").textContent = r.receiptNumber || 'REC-2026-XXXX';
    if (document.getElementById("recStudentId")) document.getElementById("recStudentId").textContent = r.studentId || '-';
    if (document.getElementById("recDate")) document.getElementById("recDate").textContent = r.paymentDate || '-';
    if (document.getElementById("recStudentName")) document.getElementById("recStudentName").textContent = r.studentName || '-';
    if (document.getElementById("recDept")) document.getElementById("recDept").textContent = r.department || '-';
    if (document.getElementById("recTotalFees")) document.getElementById("recTotalFees").textContent = `₹${(r.totalFees || 0).toLocaleString('en-IN')}`;
    if (document.getElementById("recPaidFees")) document.getElementById("recPaidFees").textContent = `₹${(r.paidFees || 0).toLocaleString('en-IN')}`;
    if (document.getElementById("recPendingFees")) document.getElementById("recPendingFees").textContent = `₹${(r.pendingFees || 0).toLocaleString('en-IN')}`;

    const statusEl = document.getElementById("recStatus");
    if (statusEl) {
      statusEl.textContent = (r.paymentStatus || 'PENDING').toUpperCase();
      statusEl.className = `badge ${r.paymentStatus === 'Paid' ? 'bg-success' : r.paymentStatus === 'Partial' ? 'bg-warning text-dark' : 'bg-danger'}`;
    }

    openModal("feeReceiptModal");
  } else {
    showToast(res?.message || "Failed to load fee receipt", "danger");
  }
}
