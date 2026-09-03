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
  if (document.getElementById("profRole")) document.getElementById("profRole").value = user.role || "";
  if (document.getElementById("profName")) document.getElementById("profName").value = user.name || "";
  if (document.getElementById("profEmail")) document.getElementById("profEmail").value = user.email || "";
}

async function saveProfileForm(e) {
  e.preventDefault();
  const name = document.getElementById("profName").value.trim();
  const email = document.getElementById("profEmail").value.trim();
  const password = document.getElementById("profPassword").value.trim();

  const payload = { name, email };
  if (password) payload.password = password;

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
    const pwdInput = document.getElementById("profPassword");
    if (pwdInput) pwdInput.value = "";
  } else {
    showToast(res.message || "Failed to update profile", "danger");
  }
}
