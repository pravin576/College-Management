/**
 * Profile Module Controller
 */
document.addEventListener("DOMContentLoaded", async () => {
  const user = await checkAuth();
  if (user) {
    populateProfileData(user);
  }
});

function populateProfileData(user) {
  if (document.getElementById("profileFullName")) document.getElementById("profileFullName").textContent = user.name || user.username;
  if (document.getElementById("profileRoleBadge")) document.getElementById("profileRoleBadge").textContent = user.role;
  if (document.getElementById("profileDepartmentText")) document.getElementById("profileDepartmentText").textContent = `Department: ${user.department || 'Administration'}`;
  if (document.getElementById("profileBigAvatar")) document.getElementById("profileBigAvatar").textContent = (user.name || user.username || "U").charAt(0).toUpperCase();

  if (document.getElementById("profUsername")) document.getElementById("profUsername").value = user.username || "";
  if (document.getElementById("changeUserCurrentDisplay")) document.getElementById("changeUserCurrentDisplay").value = user.username || "";
  if (document.getElementById("profRole")) document.getElementById("profRole").value = user.role || "";
  if (document.getElementById("profName")) document.getElementById("profName").value = user.name || "";
  if (document.getElementById("profEmail")) document.getElementById("profEmail").value = user.email || "";
}

async function saveProfileForm(e) {
  e.preventDefault();
  const name = document.getElementById("profName").value.trim();
  const email = document.getElementById("profEmail").value.trim();

  if (!name || !email) {
    showToast("Full Name and Email Address are required", "danger");
    return;
  }

  const payload = { name, email };

  const res = await fetchAPI("/api/profile", {
    method: "POST",
    body: JSON.stringify(payload)
  });

  if (res.success) {
    const updatedUser = res.user || { ...(getSession() || {}), name, email };
    localStorage.setItem(SESSION_KEY, JSON.stringify(updatedUser));
    showToast(res.message || "Profile updated successfully!", "success");
    populateProfileData(updatedUser);
    updateSidebarUserUI(updatedUser);
  } else {
    showToast(res.message || "Failed to update profile", "danger");
  }
}

async function submitChangeUsername(e) {
  e.preventDefault();
  const newUsername = document.getElementById("changeUserNew").value.trim();
  const currentPassword = document.getElementById("changeUserPassword").value.trim();

  if (!newUsername) {
    showToast("New username cannot be empty.", "danger");
    return;
  }
  if (!currentPassword) {
    showToast("Current password is required to change username.", "danger");
    return;
  }

  const res = await fetchAPI("/api/profile/username", {
    method: "PUT",
    body: JSON.stringify({
      new_username: newUsername,
      current_password: currentPassword
    })
  });

  if (res.success) {
    showToast(res.message || "Username changed successfully.", "success");
    const user = getSession() || {};
    user.username = newUsername;
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
    populateProfileData(user);
    updateSidebarUserUI(user);
    document.getElementById("changeUserNew").value = "";
    document.getElementById("changeUserPassword").value = "";
  } else {
    showToast(res.message || "Failed to change username.", "danger");
  }
}

async function submitChangePassword(e) {
  e.preventDefault();
  const currentPassword = document.getElementById("changePassCurrent").value.trim();
  const newPassword = document.getElementById("changePassNew").value.trim();
  const confirmPassword = document.getElementById("changePassConfirm").value.trim();

  if (!currentPassword || !newPassword || !confirmPassword) {
    showToast("All password fields are required.", "danger");
    return;
  }

  if (newPassword !== confirmPassword) {
    showToast("New passwords do not match.", "danger");
    return;
  }

  if (newPassword.length < 6) {
    showToast("Password must be at least 6 characters long.", "danger");
    return;
  }

  const res = await fetchAPI("/api/profile/password", {
    method: "PUT",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword
    })
  });

  if (res.success) {
    showToast(res.message || "Password changed successfully.", "success");
    document.getElementById("changePassCurrent").value = "";
    document.getElementById("changePassNew").value = "";
    document.getElementById("changePassConfirm").value = "";
  } else {
    showToast(res.message || "Failed to change password.", "danger");
  }
}
