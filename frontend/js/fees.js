/**
 * Fees Module Controller
 */
let allFees = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    loadFeesData();
  }
});

async function loadFeesData() {
  const res = await fetchAPI("/api/fees");
  if (res.success && res.fees) {
    allFees = res.fees;
    renderFeesTable(allFees);
    updateFeesStats(allFees);
  } else {
    renderFeesTable([]);
    updateFeesStats([]);
  }
}

function updateFeesStats(recs) {
  let paidSum = 0;
  let pendingSum = 0;
  recs.forEach(f => {
    paidSum += parseFloat(f.paid_fees || 0);
    pendingSum += parseFloat(f.pending_fees || 0);
  });

  if (document.getElementById("feeTotalPaid")) document.getElementById("feeTotalPaid").textContent = `₹${paidSum.toLocaleString()}`;
  if (document.getElementById("feeTotalPending")) document.getElementById("feeTotalPending").textContent = `₹${pendingSum.toLocaleString()}`;
  if (document.getElementById("feeRecordsCount")) document.getElementById("feeRecordsCount").textContent = recs.length;
}

function renderFeesTable(recs) {
  const tbody = document.getElementById("feesTableBody");
  if (!tbody) return;

  if (recs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No data available.</td></tr>`;
    return;
  }

  const user = getSession() || {};
  const isStudent = user.role === "Student";

  tbody.innerHTML = recs.map(f => `
    <tr>
      <td class="fw-bold">${f.student_id}</td>
      <td class="fw-semibold">${f.student_name}</td>
      <td><span class="badge bg-secondary">${f.department}</span></td>
      <td>₹${(f.total_fees || 0).toLocaleString()}</td>
      <td class="text-success fw-bold">₹${(f.paid_fees || 0).toLocaleString()}</td>
      <td class="text-danger fw-bold">₹${(f.pending_fees || 0).toLocaleString()}</td>
      <td>${f.payment_date || 'N/A'}</td>
      <td><span class="badge ${f.payment_status === 'Paid' ? 'bg-success' : f.payment_status === 'Partial' ? 'bg-warning' : 'bg-danger'}">${f.payment_status}</span></td>
      <td>
        <button class="btn btn-sm btn-outline-success me-1" onclick="viewFeeReceipt('${f.id}')" title="Print Receipt"><i class="bi bi-receipt"></i></button>
        ${!isStudent ? `
          <button class="btn btn-sm btn-outline-primary me-1" onclick="editFeeRecord(${f.id})" title="Edit"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-sm btn-outline-danger" onclick="deleteFeeRecord(${f.id})" title="Delete"><i class="bi bi-trash"></i></button>
        ` : ''}
      </td>
    </tr>
  `).join("");
}

function filterFeesTable() {
  const q = (document.getElementById("searchFeesInput")?.value || "").toLowerCase().trim();
  const statusVal = document.getElementById("filterFeeStatus")?.value || "All";

  const filtered = allFees.filter(f => {
    const matchesSearch = !q || (f.student_id || "").toLowerCase().includes(q) || (f.student_name || "").toLowerCase().includes(q);
    const matchesStatus = statusVal === "All" || f.payment_status === statusVal;
    return matchesSearch && matchesStatus;
  });

  renderFeesTable(filtered);
  updateFeesStats(filtered);
}

async function viewFeeReceipt(feeId) {
  const res = await fetchAPI(`/api/fees/receipt?id=${encodeURIComponent(feeId)}`);
  if (res.success && res.receipt) {
    const r = res.receipt;
    if (document.getElementById("recNumber")) document.getElementById("recNumber").textContent = r.receiptNumber;
    if (document.getElementById("recStudentId")) document.getElementById("recStudentId").textContent = r.studentId;
    if (document.getElementById("recDate")) document.getElementById("recDate").textContent = r.paymentDate;
    if (document.getElementById("recStudentName")) document.getElementById("recStudentName").textContent = r.studentName;
    if (document.getElementById("recDept")) document.getElementById("recDept").textContent = r.department;
    if (document.getElementById("recTotalFees")) document.getElementById("recTotalFees").textContent = `₹${(r.totalFees || 0).toLocaleString()}`;
    if (document.getElementById("recPaidFees")) document.getElementById("recPaidFees").textContent = `₹${(r.paidFees || 0).toLocaleString()}`;
    if (document.getElementById("recPendingFees")) document.getElementById("recPendingFees").textContent = `₹${(r.pendingFees || 0).toLocaleString()}`;
    if (document.getElementById("recStatus")) document.getElementById("recStatus").textContent = r.paymentStatus.toUpperCase();

    openModal("feeReceiptModal");
  } else {
    showToast(res.message || "Failed to load fee receipt", "danger");
  }
}

async function handlePayFeeSubmit(e) {
  e.preventDefault();
  const payAmount = parseFloat(document.getElementById("payFeeAmount").value || 0);
  if (payAmount <= 0) {
    showToast("Please enter a valid payment amount", "danger");
    return;
  }

  const res = await fetchAPI("/api/fees", {
    method: "POST",
    body: JSON.stringify({ payAmount })
  });

  if (res.success) {
    showToast(res.message || "Fee payment recorded successfully!", "success");
    closeModal("payFeeModal");
    loadFeesData();
    viewFeeReceipt(getSession()?.student_id || "");
  } else {
    showToast(res.message || "Payment failed", "danger");
  }
}

async function saveFeeRecordForm(e) {
  e.preventDefault();
  const payload = {
    id: document.getElementById("feeRecordDbId").value || null,
    studentId: document.getElementById("feeStudentId").value.trim(),
    studentName: document.getElementById("feeStudentName").value.trim(),
    department: document.getElementById("feeDepartment").value,
    totalFees: parseFloat(document.getElementById("feeTotal").value || 0),
    paidFees: parseFloat(document.getElementById("feePaid").value || 0)
  };

  const res = await fetchAPI("/api/fees", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    showToast(res.message || "Fee record updated", "success");
    closeModal("manageFeeModal");
    loadFeesData();
  } else {
    showToast(res.message || "Failed to update fee record", "danger");
  }
}

function editFeeRecord(id) {
  const f = allFees.find(item => item.id === id);
  if (!f) return;

  document.getElementById("feeRecordDbId").value = f.id;
  document.getElementById("feeStudentId").value = f.student_id;
  document.getElementById("feeStudentName").value = f.student_name;
  document.getElementById("feeDepartment").value = f.department || "Computer Engineering";
  document.getElementById("feeTotal").value = f.total_fees;
  document.getElementById("feePaid").value = f.paid_fees;

  openModal("manageFeeModal");
}

async function deleteFeeRecord(id) {
  if (!confirm("Are you sure you want to delete this fee record?")) return;

  const res = await fetchAPI(`/api/fees?id=${id}`, {
    method: "DELETE"
  });

  if (res.success) {
    showToast("Fee record deleted", "success");
    loadFeesData();
  } else {
    showToast(res.message || "Failed to delete fee record", "danger");
  }
}
