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
        <span>${message}</span>
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
    if (window.location.pathname.endsWith("login.html")) {
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
  
  if (role === "Student") {
    document.querySelectorAll(".nav-admin-hod-fac, .nav-admin-hod, .action-add-student, .action-add-faculty, .action-add-hod, .action-publish-notice, .action-add-attendance, .action-add-result, .action-add-fee, .action-add-timetable").forEach(el => el.style.display = "none");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "inline-flex";
  } else if (role === "Faculty") {
    document.querySelectorAll(".nav-admin-hod, .action-add-faculty, .action-add-hod, .action-publish-notice, .action-add-fee").forEach(el => el.style.display = "none");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "none";
  } else if (role === "HOD") {
    document.querySelectorAll(".action-add-hod").forEach(el => el.style.display = "none");
    const payFeeBtn = document.getElementById("btnPayFee");
    if (payFeeBtn) payFeeBtn.style.display = "none";
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
    showToast("Registration Successful! Your account has been created successfully.", "success");
    showRegistrationSuccess(username);
  } else {
    showToast(data.message || "Student registration failed", "danger");
  }
}

async function handleFacultyRegisterSubmit(e) {
  e.preventDefault();
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
    showToast("Registration Successful! Your account has been created successfully.", "success");
    showRegistrationSuccess(username);
  } else {
    showToast(data.message || "Faculty registration failed", "danger");
  }
}

async function handleHodRegisterSubmit(e) {
  e.preventDefault();
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
    showToast("Registration Successful! Your account has been created successfully.", "success");
    showRegistrationSuccess(username);
  } else {
    showToast(data.message || "HOD registration failed", "danger");
  }
}

async function handleAdminRegisterSubmit(e) {
  e.preventDefault();
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
    showToast("Registration Successful! Your account has been created successfully.", "success");
    showRegistrationSuccess(username);
  } else {
    showToast(data.message || "Administrator registration failed", "danger");
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
}

async function handleForgotPasswordVerifySubmit(e) {
  e.preventDefault();
  const role = document.getElementById("forgotRole").value;
  const identifier = document.getElementById("forgotIdentifier").value.trim();

  if (!identifier) {
    showToast("Please enter Username, Email, Phone, or ID", "warning");
    return;
  }

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
    if (emailEl) emailEl.innerHTML = `<i class="bi bi-envelope me-1"></i> Masked Email: <strong>${user.maskedEmail || 'N/A'}</strong>`;
    if (mobileEl) mobileEl.innerHTML = `<i class="bi bi-phone me-1"></i> Masked Phone: <strong>${user.maskedMobile || 'N/A'}</strong>`;

    const step1 = document.getElementById("forgotStep1");
    const step2 = document.getElementById("forgotStep2");
    if (step1) step1.style.display = "none";
    if (step2) step2.style.display = "block";
    showToast("Account found! Please confirm your email/mobile and enter a new password.", "success");
  } else {
    showToast(data.message || "Account not found for the selected role and identifier.", "danger");
  }
}

async function handleForgotPasswordResetSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("verifiedUsername").value;
  const role = document.getElementById("verifiedRole").value;
  const verificationInput = document.getElementById("forgotVerInput").value.trim();
  const newPassword = document.getElementById("forgotNewPassword").value.trim();
  const confirmPassword = document.getElementById("forgotConfirmPassword").value.trim();

  if (!verificationInput) {
    showToast("Please enter your registered email or mobile number for verification", "warning");
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

  const data = await fetchAPI("/api/forgot-password", {
    method: "POST",
    body: JSON.stringify({
      action: "reset",
      username,
      role,
      verificationInput,
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
    showToast(data.message || "Failed to reset password. Please check your verification info.", "danger");
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
