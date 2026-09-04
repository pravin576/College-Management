/**
 * SimpleERP - College ERP Management System
 * Core JavaScript Engine (Python REST API Backend, Session Auth, Role Enforcement, Vanilla UI)
 */

// Storage Keys
const SESSION_KEY = "erp_session";
const TOKEN_KEY = "erp_token";
const THEME_KEY = "erp_theme";

// Helper to get session user
function getSession() {
  const session = localStorage.getItem(SESSION_KEY);
  return session ? JSON.parse(session) : null;
}

function getSessionToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

// Global Toast Notification Helper
function showToast(message, type = "success") {
  let toastContainer = document.getElementById("erpToastContainer");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "erpToastContainer";
    toastContainer.className = "toast-container";
    document.body.appendChild(toastContainer);
  }

  const toastId = `toast_${Date.now()}`;
  const bgClass = type === "success" ? "bg-success" : type === "danger" ? "bg-danger" : type === "warning" ? "bg-warning" : "bg-primary";
  const icon = type === "success" ? "bi-check-circle" : type === "danger" ? "bi-x-circle" : "bi-info-circle";

  const toastHTML = `
    <div id="${toastId}" class="toast ${bgClass}">
      <div class="d-flex align-items-center gap-2">
        <i class="bi ${icon} fs-5"></i>
        <span style="white-space: pre-line;">${message}</span>
      </div>
      <button type="button" class="btn-close text-white" onclick="document.getElementById('${toastId}').remove()">✕</button>
    </div>
  `;

  toastContainer.insertAdjacentHTML("beforeend", toastHTML);
  setTimeout(() => {
    const el = document.getElementById(toastId);
    if (el) el.remove();
  }, 4500);
}

// Vanilla Modal Controls
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("show");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("show");
    const form = modal.querySelector("form");
    if (form) form.reset();
  }
}

// Theme Controls
function applyTheme(theme) {
  if (theme === "dark") {
    document.body.classList.add("dark-mode");
    document.documentElement.setAttribute("data-bs-theme", "dark");
  } else {
    document.body.classList.remove("dark-mode");
    document.documentElement.setAttribute("data-bs-theme", "light");
  }
  localStorage.setItem(THEME_KEY, theme);
}

function toggleTheme() {
  const current = localStorage.getItem(THEME_KEY) || "light";
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);
  showToast(`Switched to ${next} mode`, "info");
}

function toggleSidebar() {
  const sb = document.getElementById("erpSidebar");
  if (sb) sb.classList.toggle("show");
}

/**
 * Centralized Asynchronous API Fetch Engine
 * Resolves relative URLs to the correct backend base URL.
 * - On the live deployment: uses window.location.origin (same domain)
 * - When opened as a local file (file://): falls back to http://localhost:8000
 */
async function fetchAPI(url, options = {}) {
  const token = getSessionToken();
  const headers = options.headers || {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
    headers["X-Session-Token"] = token;
  }
  if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  options.headers = headers;

  let targetUrl = url;
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    const cleanPath = url.startsWith("/") ? url : "/" + url;
    if (window.location.protocol === "file:") {
      // Opened directly as a local HTML file — target localhost dev server
      targetUrl = `http://127.0.0.1:8000${cleanPath}`;
    } else {
      // Served via HTTP(S) — use the same origin (works for both localhost and Render)
      targetUrl = `${window.location.origin}${cleanPath}`;
    }
  }

  try {
    const res = await fetch(targetUrl, options);
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }

    // Structured JSON response handling
    if (data && typeof data === "object") {
      // Manage session expiration for protected pages
      if (res.status === 401 && !url.includes("/api/login") && !url.includes("/api/register") && !url.includes("/api/contact")) {
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(TOKEN_KEY);
        if (!window.location.pathname.endsWith("login.html") && !window.location.pathname.endsWith("index.html") && window.location.pathname !== "/") {
          window.location.href = "login.html";
        }
      }
      return data;
    }

    // Non-JSON HTTP Error Status Handling
    if (!res.ok) {
      return { success: false, message: `HTTP Error ${res.status}: ${res.statusText}` };
    }

    return { success: true };
  } catch (err) {
    console.error("API Connection Error:", err);
    const isLocal = window.location.protocol === "file:" || window.location.hostname === "localhost";
    return {
      success: false,
      message: isLocal
        ? "Backend connection error. Please ensure Python server is running (`python app.py` at http://localhost:8000)."
        : "Backend connection error. The server may be unavailable. Please try again later."
    };
  }
}

// Global Auth Check for Protected Pages
async function checkAuth() {
  const isPublicPage = window.location.pathname.endsWith("index.html") || window.location.pathname.endsWith("login.html") || window.location.pathname === "/";
  
  const data = await fetchAPI("/api/auth/me");
  if (data.success && data.user) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(data.user));
    updateSidebarUserUI(data.user);
    applyRoleVisibility(data.user);

    if (data.must_change_password || data.user.must_change_password) {
      showFirstLoginPasswordModal(data.user);
    } else if (window.location.pathname.endsWith("login.html")) {
      window.location.href = "dashboard.html";
    }
    return data.user;
  } else {
    if (!isPublicPage) {
      window.location.href = "login.html";
    }
    return null;
  }
}

function updateSidebarUserUI(user) {
  const nameEl = document.getElementById("sidebarUserName");
  const roleEl = document.getElementById("sidebarUserRole");
  const avatarEl = document.getElementById("sidebarAvatar");
  const topUserEl = document.getElementById("topHeaderUser");
  const topRoleEl = document.getElementById("topHeaderRole");

  if (nameEl) nameEl.textContent = user.name || user.username;
  if (roleEl) roleEl.textContent = user.role;
  if (avatarEl) avatarEl.textContent = (user.name || user.username || "U").charAt(0).toUpperCase();

  if (topUserEl) topUserEl.textContent = user.name || user.username;
  if (topRoleEl) topRoleEl.textContent = user.role;
}

function applyRoleVisibility(user) {
  const role = user.role;
  const dept = user.department;
  
  const linkDash = document.querySelector('a.erp-nav-link[href="dashboard.html"]');
  const linkStudents = document.querySelector('a.erp-nav-link[href="students.html"]');
  const linkFaculty = document.querySelector('a.erp-nav-link[href="faculty.html"]');
  const linkHod = document.querySelector('a.erp-nav-link[href="hod.html"]');
  const linkAtt = document.querySelector('a.erp-nav-link[href="attendance.html"]');
  const linkRes = document.querySelector('a.erp-nav-link[href="results.html"]');
  const linkFees = document.querySelector('a.erp-nav-link[href="fees.html"]');
  const linkTime = document.querySelector('a.erp-nav-link[href="timetable.html"]');
  const linkProf = document.querySelector('a.erp-nav-link[href="profile.html"]');

  if (role === "Student") {
    document.querySelectorAll(".nav-admin-hod-fac, .nav-admin-hod, .nav-admin-only, .role-admin-only, .role-hod-only, .action-add-student, .action-add-faculty, .action-add-hod, .action-publish-notice, .action-add-attendance, .action-add-result, .action-add-fee, .action-add-timetable, .section-faculty-student-assignment, #facultyStudentAssignmentCard, .action-assign-student, .action-remove-assignment").forEach(el => el.style.display = "none");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "inline-flex";

    if (linkDash) linkDash.innerHTML = `<i class="bi bi-grid-1x2-fill"></i> Student Dashboard`;
    if (linkAtt) linkAtt.innerHTML = `<i class="bi bi-calendar-check-fill"></i> My Attendance`;
    if (linkRes) linkRes.innerHTML = `<i class="bi bi-journal-bookmark-fill"></i> My Results`;
    if (linkFees) linkFees.innerHTML = `<i class="bi bi-credit-card-fill"></i> My Fees`;
    if (linkTime) linkTime.innerHTML = `<i class="bi bi-clock-fill"></i> My Timetable`;
    if (linkProf) linkProf.innerHTML = `<i class="bi bi-person-circle"></i> My Profile`;

  } else if (role === "Faculty") {
    document.querySelectorAll(".nav-admin-hod, .nav-admin-only, .role-admin-only, .role-hod-only, .action-add-faculty, .action-add-hod, .action-publish-notice, .action-add-fee, .section-faculty-student-assignment, #facultyStudentAssignmentCard, .action-assign-student, .action-remove-assignment").forEach(el => el.style.display = "none");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "none";

    if (linkDash) linkDash.innerHTML = `<i class="bi bi-grid-1x2-fill"></i> Faculty Dashboard`;
    if (linkStudents) linkStudents.innerHTML = `<i class="bi bi-mortarboard-fill"></i> Assigned Students`;

  } else if (role === "HOD") {
    // HOD: Daily department-level operations, student & faculty management for own dept, faculty-student assignment
    document.querySelectorAll(".action-add-hod, .action-edit-hod, .nav-admin-only, .role-admin-only, .section-database-controls, .admin-only-control").forEach(el => el.style.display = "none");
    document.querySelectorAll(".role-hod-only, .section-faculty-student-assignment, #facultyStudentAssignmentCard, .action-add-student, .action-add-faculty, .action-add-attendance, .action-add-result, .action-add-timetable, .action-assign-student, .action-remove-assignment").forEach(el => el.style.display = "");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "none";

    if (linkDash) linkDash.innerHTML = `<i class="bi bi-grid-1x2-fill"></i> HOD Dashboard`;
    if (linkHod) linkHod.innerHTML = `<i class="bi bi-person-check-fill"></i> HOD Portal`;

    // Strict frontend UI lock: Prevent HOD from selecting other departments
    if (dept) {
      document.querySelectorAll("select#departmentFilter, select#deptFilter, select#filterDepartment, select#modalDepartment, select#modalFacultyDept, select#modalStudentDepartment, select#modalAttendanceDepartment, select#reportDeptFilter, select#modalNoticeDepartment").forEach(select => {
        select.value = dept;
        select.disabled = true;
        select.title = `Department strictly restricted to ${dept}`;
      });
    }

  } else if (["Administrator", "Admin", "Principal"].includes(role)) {
    // Administrative / Principal: Institutional monitoring & authority, HOD management, reports, notices, database controls. NO daily student/faculty data-entry or faculty-student assignment.
    document.querySelectorAll(".role-hod-only, .section-faculty-student-assignment, #facultyStudentAssignmentCard, .action-assign-student, .action-remove-assignment, .action-assign-faculty-students, .action-add-student, .action-add-faculty, .action-add-attendance, .action-add-result, .action-add-timetable").forEach(el => el.style.display = "none");
    document.querySelectorAll(".nav-admin-only, .role-admin-only, .action-add-hod, .action-edit-hod, .action-publish-notice, .section-database-controls, .admin-only-control").forEach(el => el.style.display = "");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "none";

    if (linkDash) linkDash.innerHTML = `<i class="bi bi-grid-1x2-fill"></i> Admin Dashboard`;
    if (linkHod) linkHod.innerHTML = `<i class="bi bi-person-badge-fill"></i> HOD Management`;
    if (linkStudents) linkStudents.innerHTML = `<i class="bi bi-mortarboard-fill"></i> Students`;
    if (linkFaculty) linkFaculty.innerHTML = `<i class="bi bi-person-video3"></i> Faculty`;
  }
}

// Password Visibility Toggle & Password Strength Helpers
function togglePasswordVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  if (btnEl) {
    const icon = btnEl.querySelector("i");
    if (icon) {
      icon.className = isPassword ? "bi bi-eye-slash" : "bi bi-eye";
    }
  }
}

function checkPasswordStrength(password, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!password) {
    container.classList.add("d-none");
    return;
  }
  container.classList.remove("d-none");

  const badge = container.querySelector(".strength-badge");
  const bar = container.querySelector(".strength-bar");

  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[@#$%^&*!~?_=-]/.test(password)) score += 1;

  if (score <= 2) {
    if (badge) { badge.textContent = "Weak"; badge.className = "badge bg-danger strength-badge"; }
    if (bar) { bar.style.width = "33%"; bar.className = "progress-bar bg-danger strength-bar"; }
  } else if (score <= 4) {
    if (badge) { badge.textContent = "Medium"; badge.className = "badge bg-warning text-dark strength-badge"; }
    if (bar) { bar.style.width = "66%"; bar.className = "progress-bar bg-warning strength-bar"; }
  } else {
    if (badge) { badge.textContent = "Strong"; badge.className = "badge bg-success strength-badge"; }
    if (bar) { bar.style.width = "100%"; bar.className = "progress-bar bg-success strength-bar"; }
  }
}

function showRegistrationSuccess(username) {
  const box = document.getElementById("registrationSuccessBox");
  const formsContainer = document.getElementById("registrationFormsContainer");
  const usernameEl = document.getElementById("regSuccessUsername");

  if (usernameEl) usernameEl.textContent = username || "Registered User";
  if (formsContainer) formsContainer.style.display = "none";
  if (box) box.classList.remove("d-none");
}

function showLoginTabWithUsername() {
  const usernameEl = document.getElementById("regSuccessUsername");
  const registeredUser = usernameEl ? usernameEl.textContent : "";
  const loginUserEl = document.getElementById("loginUsername");
  if (loginUserEl && registeredUser) {
    loginUserEl.value = registeredUser;
  }
  if (typeof switchAuthTab === "function") {
    switchAuthTab("signin");
  }
  const box = document.getElementById("registrationSuccessBox");
  const formsContainer = document.getElementById("registrationFormsContainer");
  if (box) box.classList.add("d-none");
  if (formsContainer) formsContainer.style.display = "block";
}

// Authentication Handlers
async function handleLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value.trim();
  const roleEl = document.getElementById("loginRole");
  const role = roleEl ? roleEl.value : "All";
  const rememberMe = document.getElementById("rememberMe");

  if (!username || !password) {
    showToast("Please enter both username/email and password", "warning");
    return;
  }

  if (rememberMe && rememberMe.checked) {
    localStorage.setItem("remembered_username", username);
  } else {
    localStorage.removeItem("remembered_username");
  }

  const data = await fetchAPI("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password, role })
  });

  if (data.success && data.user) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(data.user));
    localStorage.setItem(TOKEN_KEY, data.token || "");

    if (data.must_change_password || data.user.must_change_password) {
      showFirstLoginPasswordModal(data.user);
      return;
    }

    showToast("Login successful! Redirecting to dashboard...", "success");
    setTimeout(() => { window.location.href = "dashboard.html"; }, 500);
  } else {
    showToast(data.message || "Invalid username or password credentials", "danger");
  }
}

function switchRegistrationRole(role) {
  const studentForm = document.getElementById("studentRegisterForm");
  const facultyForm = document.getElementById("facultyRegisterForm");
  const hodForm = document.getElementById("hodRegisterForm");
  const adminForm = document.getElementById("adminRegisterForm");

  if (studentForm) studentForm.style.display = role === "Student" ? "block" : "none";
  if (facultyForm) facultyForm.style.display = role === "Faculty" ? "block" : "none";
  if (hodForm) hodForm.style.display = role === "HOD" ? "block" : "none";
  if (adminForm) adminForm.style.display = role === "Administrator" ? "block" : "none";
}

async function handleStudentRegisterSubmit(e) {
  e.preventDefault();
  const submitBtn = e.target.querySelector('button[type="submit"]');
  if (submitBtn) {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Registering...';
  }

  try {
    const name = document.getElementById("regStudentName").value.trim();
    const year = document.getElementById("regStudentYear").value;
    const email = document.getElementById("regStudentEmail").value.trim();
    const mobile = document.getElementById("regStudentPhone").value.trim();
    const studentId = document.getElementById("regStudentId").value.trim();
    const rollNumber = document.getElementById("regStudentRollNumber").value.trim();
    const department = document.getElementById("regStudentDepartment").value;
    const username = document.getElementById("regStudentUsername").value.trim();
    const password = document.getElementById("regStudentPassword").value.trim();
    const confirmPassword = document.getElementById("regStudentConfirmPassword").value.trim();

    if (password !== confirmPassword) {
      showToast("Password and Confirm Password do not match!", "danger");
      return;
    }

    const payload = {
      role: "Student",
      name,
      year,
      email,
      mobile,
      studentId,
      rollNumber,
      department,
      username,
      password,
      confirmPassword
    };

    const data = await fetchAPI("/api/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (data.success && data.user) {
      showToast(data.message || "Registration Successful! Your account has been created.", "success");
      showRegistrationSuccess(username);
    } else {
      showToast(data.message || "Student registration failed", "danger");
    }
  } catch (err) {
    showToast("Registration failed due to a server/database error. Please check the server console.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="bi bi-person-check-fill me-2"></i>Register Student Account';
    }
  }
}

async function handleFacultyRegisterSubmit(e) {
  e.preventDefault();
  const submitBtn = e.target.querySelector('button[type="submit"]');
  if (submitBtn) {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Registering...';
  }

  try {
    const name = document.getElementById("regFacultyName").value.trim();
    const mobile = (document.getElementById("regFacultyPhone")?.value || "").trim();
    const email = (document.getElementById("regFacultyEmail")?.value || "").trim();
    const department = document.getElementById("regFacultyDepartment").value;
    const username = document.getElementById("regFacultyUsername").value.trim();
    const password = document.getElementById("regFacultyPassword").value.trim();
    const confirmPassword = document.getElementById("regFacultyConfirmPassword").value.trim();

    if (password !== confirmPassword) {
      showToast("Password and Confirm Password do not match!", "danger");
      return;
    }

    const payload = {
      role: "Faculty",
      name,
      mobile,
      email,
      department,
      username,
      password,
      confirmPassword
    };

    const data = await fetchAPI("/api/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (data.success && data.user) {
      showToast(data.message || "Registration Successful! Your account has been created.", "success");
      showRegistrationSuccess(username);
    } else {
      showToast(data.message || "Faculty registration failed", "danger");
    }
  } catch (err) {
    showToast("Registration failed due to a server/database error. Please check the server console.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="bi bi-person-badge-fill me-2"></i>Register Faculty Account';
    }
  }
}

async function handleHodRegisterSubmit(e) {
  e.preventDefault();
  const submitBtn = e.target.querySelector('button[type="submit"]');
  if (submitBtn) {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Registering...';
  }

  try {
    const name = document.getElementById("regHodName").value.trim();
    const department = document.getElementById("regHodDepartment").value;
    const qualification = document.getElementById("regHodQualification").value.trim();
    const mobile = (document.getElementById("regHodPhone")?.value || "").trim();
    const experience = document.getElementById("regHodExperience").value.trim();
    const email = document.getElementById("regHodEmail").value.trim();
    const username = document.getElementById("regHodUsername").value.trim();
    const password = document.getElementById("regHodPassword").value.trim();
    const confirmPassword = document.getElementById("regHodConfirmPassword").value.trim();

    if (password !== confirmPassword) {
      showToast("Password and Confirm Password do not match!", "danger");
      return;
    }

    const payload = {
      role: "HOD",
      name,
      department,
      qualification,
      mobile,
      experience,
      email,
      username,
      password,
      confirmPassword
    };

    const data = await fetchAPI("/api/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (data.success && data.user) {
      showToast(data.message || "Registration Successful! Your account has been created.", "success");
      showRegistrationSuccess(username);
    } else {
      showToast(data.message || "HOD registration failed", "danger");
    }
  } catch (err) {
    showToast("Registration failed due to a server/database error. Please check the server console.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="bi bi-person-workspace me-2"></i>Register HOD Account';
    }
  }
}

async function handleAdminRegisterSubmit(e) {
  e.preventDefault();
  const submitBtn = e.target.querySelector('button[type="submit"]');
  if (submitBtn) {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Registering...';
  }

  try {
    const name = document.getElementById("regAdminName").value.trim();
    const mobile = (document.getElementById("regAdminPhone")?.value || "").trim();
    const email = document.getElementById("regAdminEmail").value.trim();
    const username = document.getElementById("regAdminUsername").value.trim();
    const password = document.getElementById("regAdminPassword").value.trim();
    const confirmPassword = document.getElementById("regAdminConfirmPassword").value.trim();

    if (password !== confirmPassword) {
      showToast("Password and Confirm Password do not match!", "danger");
      return;
    }

    const payload = {
      role: "Administrator",
      name,
      mobile,
      email,
      username,
      password,
      confirmPassword
    };

    const data = await fetchAPI("/api/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (data.success && data.user) {
      showToast(data.message || "Registration Successful! Your account has been created.", "success");
      showRegistrationSuccess(username);
    } else {
      showToast(data.message || "Administrator registration failed", "danger");
    }
  } catch (err) {
    showToast("Registration failed due to a server/database error. Please check the server console.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="bi bi-shield-lock-fill me-2"></i>Register Administrator Account';
    }
  }
}

// Forgot Password Flow Handlers
function resetForgotPasswordStep() {
  const step1 = document.getElementById("forgotStep1");
  const step2 = document.getElementById("forgotStep2");
  const stepSuccess = document.getElementById("forgotStepSuccess");
  if (step1) step1.style.display = "block";
  if (step2) step2.style.display = "none";
  if (stepSuccess) stepSuccess.style.display = "none";

  const verInput = document.getElementById("forgotVerInput");
  const newPass = document.getElementById("forgotNewPassword");
  const confPass = document.getElementById("forgotConfirmPassword");
  if (verInput) verInput.value = "";
  if (newPass) newPass.value = "";
  if (confPass) confPass.value = "";
}

async function handleForgotPasswordVerifySubmit(e) {
  e.preventDefault();
  const role = document.getElementById("forgotRole").value;
  const identifier = document.getElementById("forgotIdentifier").value.trim();
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!identifier) {
    showToast("Please enter Username, Email, Phone, or ID", "warning");
    return;
  }

  const originalBtnContent = submitBtn ? submitBtn.innerHTML : "";
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Searching Account...';
  }

  try {
    const data = await fetchAPI("/api/forgot-password", {
      method: "POST",
      body: JSON.stringify({ action: "verify", role, identifier })
    });

    if (data.success && data.user) {
      const user = data.user;
      const uNameEl = document.getElementById("verifiedUsername");
      const uRoleEl = document.getElementById("verifiedRole");
      if (uNameEl) uNameEl.value = user.username;
      if (uRoleEl) uRoleEl.value = user.role;
      
      const nameEl = document.getElementById("verifiedAccountName");
      const metaEl = document.getElementById("verifiedAccountMeta");
      const emailEl = document.getElementById("verifiedAccountEmail");
      const mobileEl = document.getElementById("verifiedAccountMobile");

      if (nameEl) nameEl.textContent = user.name || user.username;
      if (metaEl) metaEl.textContent = `Role: ${user.role} ${user.department ? '| Dept: ' + user.department : ''}`;
      if (emailEl) emailEl.innerHTML = `<i class="bi bi-envelope me-1"></i> Registered Email: <strong>${user.maskedEmail || 'N/A'}</strong>`;
      if (mobileEl) mobileEl.innerHTML = `<i class="bi bi-phone me-1"></i> Registered Phone: <strong>${user.maskedMobile || 'N/A'}</strong>`;

      const verInput = document.getElementById("forgotVerInput");
      if (verInput) {
        verInput.value = "";
        if (user.role === "Student") {
          verInput.placeholder = "Enter full email, phone number, or Date of Birth (YYYY-MM-DD)";
        } else {
          verInput.placeholder = "Enter full registered email address or mobile number";
        }
      }

      const step1 = document.getElementById("forgotStep1");
      const step2 = document.getElementById("forgotStep2");
      if (step1) step1.style.display = "none";
      if (step2) step2.style.display = "block";
      showToast("Account found! Please verify your identity and set a new password.", "success");
    } else {
      showToast(data.message || "Account not found for the selected role and identifier.", "danger");
    }
  } catch (err) {
    showToast("Error connecting to server. Please try again.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnContent;
    }
  }
}

async function handleForgotPasswordResetSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("verifiedUsername").value;
  const role = document.getElementById("verifiedRole").value;
  const verificationInput = document.getElementById("forgotVerInput").value.trim();
  const newPassword = document.getElementById("forgotNewPassword").value.trim();
  const confirmPassword = document.getElementById("forgotConfirmPassword").value.trim();
  const submitBtn = e.target.querySelector('button[type="submit"]');

  if (!verificationInput) {
    showToast("Please enter your registered email, mobile, or DOB for verification", "warning");
    return;
  }
  if (newPassword !== confirmPassword) {
    showToast("New Password and Confirm Password do not match!", "danger");
    return;
  }
  if (newPassword.length < 6) {
    showToast("Password must be at least 6 characters long", "warning");
    return;
  }

  const originalBtnContent = submitBtn ? submitBtn.innerHTML : "";
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Resetting Password...';
  }

  try {
    const data = await fetchAPI("/api/forgot-password", {
      method: "POST",
      body: JSON.stringify({
        action: "reset",
        username,
        role,
        verificationInput,
        verificationValue: verificationInput,
        newPassword,
        confirmPassword
      })
    });

    if (data.success) {
      const step2 = document.getElementById("forgotStep2");
      const stepSuccess = document.getElementById("forgotStepSuccess");
      if (step2) step2.style.display = "none";
      if (stepSuccess) stepSuccess.style.display = "block";
      showToast("Password reset successfully! You can now sign in.", "success");
    } else {
      showToast(data.message || "Failed to reset password. Please check your verification details.", "danger");
    }
  } catch (err) {
    showToast("Network error while resetting password.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnContent;
    }
  }
}

function showLoginTabWithForgotUsername() {
  const username = document.getElementById("verifiedUsername").value;
  const role = document.getElementById("verifiedRole").value;
  if (username) {
    const loginUserEl = document.getElementById("loginUsername");
    if (loginUserEl) loginUserEl.value = username;
  }
  if (role) {
    const loginRoleEl = document.getElementById("loginRole");
    if (loginRoleEl) loginRoleEl.value = role;
  }
  if (typeof switchAuthTab === "function") {
    switchAuthTab("signin");
  }
  resetForgotPasswordStep();
  const passEl = document.getElementById("loginPassword");
  if (passEl) {
    passEl.value = "";
    passEl.focus();
  }
}

async function logoutUser() {
  await fetchAPI("/api/logout", { method: "POST" });
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(TOKEN_KEY);
  showToast("Logged out successfully", "info");
  setTimeout(() => { window.location.href = "login.html"; }, 300);
}

// Module Global Initializer
document.addEventListener("DOMContentLoaded", () => {
  const user = getSession();
  const path = window.location.pathname;

  // Pre-fill remembered username on login form if exists
  const rememberedUser = localStorage.getItem("remembered_username");
  const loginUsernameInput = document.getElementById("loginUsername");
  const rememberMeCheckbox = document.getElementById("rememberMe");
  if (rememberedUser && loginUsernameInput) {
    loginUsernameInput.value = rememberedUser;
    if (rememberMeCheckbox) rememberMeCheckbox.checked = true;
  } 
  
  const savedTheme = localStorage.getItem(THEME_KEY) || "light";
  applyTheme(savedTheme);

  if (!window.location.pathname.endsWith("index.html") && !window.location.pathname.endsWith("login.html") && window.location.pathname !== "/") {
    checkAuth();
  }
});

// ----------------------------------------------------------------------------
// CREDENTIAL DELIVERY MODAL & HELPERS
// ----------------------------------------------------------------------------
function showCredentialModal(cred) {
  if (!cred) return;

  let modalEl = document.getElementById("credentialDeliveryModal");
  if (!modalEl) {
    const modalHTML = `
      <div class="modal fade" id="credentialDeliveryModal" tabindex="-1" style="background: rgba(0,0,0,0.65); z-index: 1060;">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content shadow-lg border-0 rounded-4">
            <div class="modal-header bg-primary text-white py-3">
              <h5 class="modal-title fw-bold mb-0"><i class="bi bi-shield-lock-fill me-2"></i> Account Created & Credentials</h5>
              <button type="button" class="btn-close btn-close-white" onclick="closeCredentialModal()"></button>
            </div>
            <div class="modal-body p-4">
              <div class="alert alert-info py-2 px-3 small d-flex align-items-center mb-3">
                <i class="bi bi-info-circle-fill fs-5 me-2 text-primary"></i>
                <span>Login credentials have been securely provisioned. Provide these to the user.</span>
              </div>
              
              <div class="card bg-light border p-3 mb-3 shadow-none" id="credentialPrintArea">
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <span class="text-muted small">Account Role:</span>
                  <span class="badge bg-primary" id="credRole">Role</span>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <span class="text-muted small">Full Name:</span>
                  <span class="fw-bold text-dark" id="credName">-</span>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2" id="credDeptRow">
                  <span class="text-muted small">Department:</span>
                  <span class="fw-semibold text-secondary" id="credDept">-</span>
                </div>
                <hr class="my-2 text-muted">
                <div class="d-flex justify-content-between align-items-center mb-2">
                  <span class="text-muted small fw-bold">Login Username:</span>
                  <div class="d-flex align-items-center gap-2">
                    <code class="fs-6 fw-bold text-dark px-2 py-1 bg-white border rounded" id="credUsername">-</code>
                    <button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="copyCredField('credUsername', this)" title="Copy Username"><i class="bi bi-clipboard"></i></button>
                  </div>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="text-muted small fw-bold">Temporary Password:</span>
                  <div class="d-flex align-items-center gap-2">
                    <code class="fs-6 fw-bold text-danger px-2 py-1 bg-white border rounded" id="credPassword">-</code>
                    <button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="copyCredField('credPassword', this)" title="Copy Password"><i class="bi bi-clipboard"></i></button>
                  </div>
                </div>
              </div>

              <div class="alert alert-warning py-2 px-3 small mb-3 border-warning">
                <i class="bi bi-exclamation-triangle-fill me-1 text-warning"></i>
                <strong>Mandatory Password Change:</strong> This temporary password must be changed during first login.
              </div>

              <div class="d-flex gap-2 justify-content-between flex-wrap">
                <button class="btn btn-outline-primary btn-sm flex-fill fw-bold" onclick="copyAllCredentials(this)"><i class="bi bi-clipboard-check me-1"></i> Copy All</button>
                <button class="btn btn-outline-secondary btn-sm flex-fill fw-bold" onclick="printCredentials()"><i class="bi bi-printer me-1"></i> Print Slip</button>
              </div>
            </div>
            <div class="modal-footer bg-light py-2">
              <button type="button" class="btn btn-primary px-4 fw-bold" onclick="closeCredentialModal()">Done</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHTML);
    modalEl = document.getElementById("credentialDeliveryModal");
  }

  const roleBadge = document.getElementById("credRole");
  const nameEl = document.getElementById("credName");
  const deptEl = document.getElementById("credDept");
  const userEl = document.getElementById("credUsername");
  const passEl = document.getElementById("credPassword");

  if (roleBadge) roleBadge.textContent = cred.role || "User";
  if (nameEl) nameEl.textContent = cred.name || "User";
  if (deptEl) deptEl.textContent = cred.department || "General";
  if (userEl) userEl.textContent = cred.username || cred.enrollmentNumber || cred.facultyId || "-";
  if (passEl) passEl.textContent = cred.temporaryPassword || "-";

  modalEl.style.display = "block";
  modalEl.classList.add("show");
}

function closeCredentialModal() {
  const modalEl = document.getElementById("credentialDeliveryModal");
  if (modalEl) {
    modalEl.style.display = "none";
    modalEl.classList.remove("show");
  }
}

function copyCredField(elemId, btnEl) {
  const el = document.getElementById(elemId);
  if (!el) return;
  const text = el.textContent.trim();
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copied to clipboard!", "success");
    if (btnEl) {
      const orig = btnEl.innerHTML;
      btnEl.innerHTML = '<i class="bi bi-check2"></i>';
      setTimeout(() => { btnEl.innerHTML = orig; }, 1500);
    }
  });
}

function copyAllCredentials(btnEl) {
  const name = document.getElementById("credName")?.textContent || "";
  const role = document.getElementById("credRole")?.textContent || "";
  const dept = document.getElementById("credDept")?.textContent || "";
  const username = document.getElementById("credUsername")?.textContent || "";
  const password = document.getElementById("credPassword")?.textContent || "";

  const text = `College Management ERP Login Credentials\n---------------------------------------\nRole: ${role}\nName: ${name}\nDepartment: ${dept}\nLogin Username: ${username}\nTemporary Password: ${password}\n---------------------------------------\nNote: You will be prompted to change this temporary password upon your first login.`;

  navigator.clipboard.writeText(text).then(() => {
    showToast("All credentials copied to clipboard!", "success");
    if (btnEl) {
      const orig = btnEl.innerHTML;
      btnEl.innerHTML = '<i class="bi bi-check2 me-1"></i> Copied!';
      setTimeout(() => { btnEl.innerHTML = orig; }, 1800);
    }
  });
}

function printCredentials() {
  const printContent = document.getElementById("credentialPrintArea");
  if (!printContent) return;

  const printWindow = window.open("", "_blank", "width=600,height=500");
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
      <head>
        <title>Account Login Slip</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
          body { font-family: sans-serif; padding: 25px; }
          .slip-box { border: 2px dashed #0d6efd; padding: 20px; border-radius: 8px; max-width: 450px; margin: auto; }
          @media print { .no-print { display: none; } }
        </style>
      </head>
      <body>
        <div class="slip-box">
          <h4 class="text-center fw-bold text-primary mb-1">College Management ERP</h4>
          <p class="text-center text-muted small mb-3">Official User Credential Slip</p>
          ${printContent.innerHTML}
          <div class="alert alert-warning mt-3 py-2 small">
            <strong>Important:</strong> Please sign in and update your password on first login.
          </div>
          <div class="text-center mt-3 no-print">
            <button class="btn btn-primary btn-sm px-4" onclick="window.print()">Print</button>
            <button class="btn btn-secondary btn-sm ms-2" onclick="window.close()">Close</button>
          </div>
        </div>
      </body>
    </html>
  `);
  printWindow.document.close();
}

// ----------------------------------------------------------------------------
// MANDATORY FIRST-LOGIN PASSWORD CHANGE MODAL
// ----------------------------------------------------------------------------
function showFirstLoginPasswordModal(user) {
  let modalEl = document.getElementById("firstLoginPasswordModal");
  if (!modalEl) {
    const modalHTML = `
      <div class="modal fade" id="firstLoginPasswordModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false" style="background: rgba(0,0,0,0.85); z-index: 1070;">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content shadow-lg border-0 rounded-4">
            <div class="modal-header bg-danger text-white py-3">
              <h5 class="modal-title fw-bold mb-0"><i class="bi bi-key-fill me-2"></i> Mandatory First-Login Password Change</h5>
            </div>
            <form id="firstLoginChangePassForm" onsubmit="submitFirstLoginPasswordChange(event)">
              <div class="modal-body p-4">
                <div class="alert alert-warning py-2 px-3 small mb-3">
                  <i class="bi bi-shield-exclamation me-1"></i>
                  <strong>First-Time Sign In:</strong> Your account was provisioned with a temporary password. You must set a new personal password before accessing your dashboard.
                </div>

                <div id="firstLoginPassAlert" class="alert alert-danger py-2 px-3 small d-none mb-3"></div>

                <div class="mb-3">
                  <label class="form-label small fw-bold">Current / Temporary Password *</label>
                  <div class="input-group">
                    <input type="password" id="firstLoginCurrentPass" class="form-control" required placeholder="Enter temporary password">
                    <button class="btn btn-outline-secondary" type="button" onclick="togglePasswordVisibility('firstLoginCurrentPass', this)"><i class="bi bi-eye"></i></button>
                  </div>
                </div>

                <div class="mb-3">
                  <label class="form-label small fw-bold">New Password *</label>
                  <div class="input-group mb-1">
                    <input type="password" id="firstLoginNewPass" class="form-control" required minlength="6" placeholder="At least 6 characters" oninput="checkPasswordStrength(this.value, 'firstLoginStrengthBox')">
                    <button class="btn btn-outline-secondary" type="button" onclick="togglePasswordVisibility('firstLoginNewPass', this)"><i class="bi bi-eye"></i></button>
                  </div>
                  <div id="firstLoginStrengthBox" class="mt-1 d-none">
                    <div class="progress" style="height: 5px;">
                      <div class="progress-bar strength-bar" style="width: 0%;"></div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-1">
                      <span class="text-muted" style="font-size: 11px;">Password Strength:</span>
                      <span class="badge strength-badge" style="font-size: 10px;">Weak</span>
                    </div>
                  </div>
                </div>

                <div class="mb-3">
                  <label class="form-label small fw-bold">Confirm New Password *</label>
                  <div class="input-group">
                    <input type="password" id="firstLoginConfirmPass" class="form-control" required minlength="6" placeholder="Re-enter new password">
                    <button class="btn btn-outline-secondary" type="button" onclick="togglePasswordVisibility('firstLoginConfirmPass', this)"><i class="bi bi-eye"></i></button>
                  </div>
                </div>
              </div>
              <div class="modal-footer bg-light py-2">
                <button type="submit" class="btn btn-danger w-100 fw-bold py-2"><i class="bi bi-check-circle me-1"></i> Update Password & Proceed to Dashboard</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", modalHTML);
    modalEl = document.getElementById("firstLoginPasswordModal");
  }
  modalEl.style.display = "block";
  modalEl.classList.add("show");
}

async function submitFirstLoginPasswordChange(e) {
  e.preventDefault();
  const alertEl = document.getElementById("firstLoginPassAlert");
  if (alertEl) alertEl.classList.add("d-none");

  const currentPassword = document.getElementById("firstLoginCurrentPass").value.trim();
  const newPassword = document.getElementById("firstLoginNewPass").value.trim();
  const confirmPassword = document.getElementById("firstLoginConfirmPass").value.trim();

  if (newPassword !== confirmPassword) {
    if (alertEl) {
      alertEl.textContent = "New password and Confirm password do not match!";
      alertEl.classList.remove("d-none");
    }
    return;
  }

  if (currentPassword === newPassword) {
    if (alertEl) {
      alertEl.textContent = "New password must be different from your current temporary password!";
      alertEl.classList.remove("d-none");
    }
    return;
  }

  const res = await fetchAPI("/api/auth/first-login-change-password", {
    method: "POST",
    body: JSON.stringify({ currentPassword, newPassword, confirmPassword })
  });

  if (res.success) {
    const user = getSession() || {};
    user.must_change_password = false;
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
    
    const modalEl = document.getElementById("firstLoginPasswordModal");
    if (modalEl) {
      modalEl.style.display = "none";
      modalEl.classList.remove("show");
    }
    showToast("Password updated successfully! Welcome to your dashboard.", "success");
    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 400);
  } else {
    if (alertEl) {
      alertEl.textContent = res.message || "Failed to update password. Please verify current password.";
      alertEl.classList.remove("d-none");
    } else {
      showToast(res.message || "Failed to update password", "danger");
    }
  }
}

// ----------------------------------------------------------------------------
// FIRST-TIME ADMINISTRATOR SETUP SYSTEM
// ----------------------------------------------------------------------------
async function checkAdminSetupStatus() {
  const bannerEl = document.getElementById("firstTimeSetupBanner");
  const linkEl = document.getElementById("firstTimeSetupLink");
  if (!bannerEl && !linkEl) return;

  try {
    const res = await fetchAPI("/api/setup/status");
    if (res && res.success && res.setup_required) {
      if (bannerEl) bannerEl.classList.remove("d-none");
      if (linkEl) linkEl.classList.remove("d-none");
    } else {
      if (bannerEl) bannerEl.classList.add("d-none");
      if (linkEl) linkEl.classList.add("d-none");
    }
  } catch (err) {
    console.error("Error checking admin setup status:", err);
  }
}

async function handleAdminSetupSubmit(e) {
  e.preventDefault();
  const submitBtn = e.target.querySelector('button[type="submit"]') || document.querySelector('#adminSetupForm button[type="submit"]');
  const originalHtml = submitBtn ? submitBtn.innerHTML : "";

  const name = (document.getElementById("setupAdminName")?.value || "").trim();
  const email = (document.getElementById("setupAdminEmail")?.value || "").trim();
  const phone = (document.getElementById("setupAdminPhone")?.value || "").trim();
  const username = (document.getElementById("setupAdminUsername")?.value || "").trim();
  const password = (document.getElementById("setupAdminPassword")?.value || "").trim();
  const confirmPassword = (document.getElementById("setupAdminConfirmPassword")?.value || "").trim();

  if (!name || !email || !username || !password) {
    showToast("Please fill in all required fields.", "danger");
    return;
  }

  if (password !== confirmPassword) {
    showToast("Password and Confirm Password do not match!", "danger");
    return;
  }

  if (password.length < 6) {
    showToast("Password must be at least 6 characters long.", "danger");
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Creating Account...';
  }

  try {
    const res = await fetchAPI("/api/setup/admin", {
      method: "POST",
      body: JSON.stringify({
        name,
        email,
        phone,
        username,
        password,
        confirmPassword
      })
    });

    if (res && res.success) {
      showToast(res.message || "Administrator account created successfully!", "success");
      
      // Update UI status immediately
      checkAdminSetupStatus();

      // Pre-fill username into Sign In form
      const loginUsernameEl = document.getElementById("loginUsername");
      if (loginUsernameEl) loginUsernameEl.value = username;
      const loginRoleEl = document.getElementById("loginRole");
      if (loginRoleEl) loginRoleEl.value = "Administrator";

      setTimeout(() => {
        if (typeof switchAuthTab === "function") {
          switchAuthTab("signin");
        }
      }, 700);
    } else {
      showToast(res?.message || "Failed to create Administrator account.", "danger");
    }
  } catch (err) {
    showToast("Network error during Administrator setup. Please try again.", "danger");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalHtml;
    }
  }
}

// Auto-check setup status on login page load
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("firstTimeSetupBanner") || document.getElementById("adminSetupForm")) {
    checkAdminSetupStatus();
  }
});

