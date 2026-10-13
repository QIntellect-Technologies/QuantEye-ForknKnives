
    // ========================================================
    // ADMIN CONFIGURATION PROTECTION — CLIENT SIDE LOGIC
    // All password verification is STRICTLY server-side.
    // This JS only manages UI state based on server responses.
    // ========================================================

    // In-memory state (synced with server session on every relevant action)
    let _adminUnlocked = false;
    let _enrollmentEnabled = false;

    /**
     * Fetch current admin session state from server and update UI accordingly.
     * Called on page load and after any state change.
     */
    async function syncAdminState() {
      try {
        const res = await fetch('/api/admin/status', { credentials: 'same-origin' });
        if (!res.ok) return;
        const data = await res.json();
        _adminUnlocked = data.admin_unlocked === true;
        _enrollmentEnabled = data.enrollment_enabled === true;
        applyAdminStateToUI();
      } catch (e) {
        // Silently fail — default state is locked
      }
    }

    /**
     * Apply current admin state to all UI elements:
     * - Enrollment sidebar item visibility
     * - Admin controls panel visibility
     * - Enrollment badge/button state
     */
    function applyAdminStateToUI() {
      const enrollItem = document.getElementById('enrollMenuSidebarItem');
      const adminPanel = document.getElementById('adminControlsPanel');
      const badge = document.getElementById('enrollmentStatusBadge');
      const icon = document.getElementById('enrollmentToggleIcon');
      const btnText = document.getElementById('enrollmentToggleBtnText');

      // Sidebar enrollment item
      if (enrollItem) {
        enrollItem.style.display = _enrollmentEnabled ? '' : 'none';
      }

      // Admin controls panel (only shown when unlocked)
      if (adminPanel) {
        adminPanel.style.display = _adminUnlocked ? 'block' : 'none';
      }

      // Enrollment badge + button
      if (badge) {
        if (_enrollmentEnabled) {
          badge.style.background = '#064e3b';
          badge.style.color = '#34d399';
          badge.style.border = '1px solid #065f46';
          badge.textContent = 'Enabled';
        } else {
          badge.style.background = '#1e3a5f';
          badge.style.color = '#93c5fd';
          badge.style.border = '1px solid #2d4a6a';
          badge.textContent = 'Disabled';
        }
      }
      if (icon) {
        icon.className = _enrollmentEnabled ? 'fa-solid fa-toggle-on' : 'fa-solid fa-toggle-off';
      }
      if (btnText) {
        btnText.textContent = _enrollmentEnabled ? 'Disable Staff Enrollment' : 'Enable Staff Enrollment';
      }
    }

    /**
     * Intercept Settings sidebar click.
     * If already unlocked → go directly to settings.
     * If locked → show password modal.
     */
    function openSettingsWithAuth(element) {
      if (_adminUnlocked) {
        switchTab('settings-view', element);
      } else {
        _pendingSettingsElement = element;
        showAdminPasswordModal();
      }
    }
    let _pendingSettingsElement = null;

    function showAdminPasswordModal() {
      const modal = document.getElementById('adminPasswordModal');
      modal.style.display = 'flex';
      document.getElementById('adminPasswordInput').value = '';
      const errDiv = document.getElementById('adminPasswordError');
      if (errDiv) errDiv.style.display = 'none';
      document.getElementById('adminUnlockBtn').disabled = false;
      document.getElementById('adminUnlockBtn').innerHTML = '<i class="fa-solid fa-unlock-keyhole"></i> Unlock Configuration';
      setTimeout(() => document.getElementById('adminPasswordInput').focus(), 100);
    }

    function closeAdminPasswordModal() {
      document.getElementById('adminPasswordModal').style.display = 'none';
      document.getElementById('adminPasswordInput').value = '';
      _pendingSettingsElement = null;
    }

    function toggleAdminPasswordVisibility() {
      const input = document.getElementById('adminPasswordInput');
      const icon = document.getElementById('adminPwdEyeIcon');
      if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fa-solid fa-eye-slash';
      } else {
        input.type = 'password';
        icon.className = 'fa-solid fa-eye';
      }
    }

    async function submitAdminPassword() {
      const input = document.getElementById('adminPasswordInput');
      const btn = document.getElementById('adminUnlockBtn');
      const errDiv = document.getElementById('adminPasswordError');
      const errText = document.getElementById('adminPasswordErrorText');
      const password = input.value;

      if (!password) {
        showAdminPwdError('Please enter the admin password.');
        return;
      }

      // Show loading state
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verifying...';
      if (errDiv) errDiv.style.display = 'none';

      try {
        const res = await fetch('/api/admin/verify-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ password })
        });
        const data = await res.json();

        if (res.ok && data.success) {
          // Success
          btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Access Granted!';
          btn.style.background = 'linear-gradient(135deg,#065f46,#059669)';
          input.value = '';
          _adminUnlocked = true;
          applyAdminStateToUI();

          setTimeout(() => {
            closeAdminPasswordModal();
            // Navigate to settings
            const el = _pendingSettingsElement || document.getElementById('settingsMenuSidebarItem');
            switchTab('settings-view', el);
            _pendingSettingsElement = null;
          }, 600);
        } else {
          showAdminPwdError(data.message || 'Incorrect password. Please try again.');
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-unlock-keyhole"></i> Unlock Configuration';
        }
      } catch (e) {
        showAdminPwdError('Connection error. Please try again.');
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-unlock-keyhole"></i> Unlock Configuration';
      }
    }

    function showAdminPwdError(msg) {
      const errDiv = document.getElementById('adminPasswordError');
      const errText = document.getElementById('adminPasswordErrorText');
      if (errDiv) { errDiv.style.display = 'flex'; }
      if (errText) errText.textContent = msg;
      // Shake animation
      const input = document.getElementById('adminPasswordInput');
      input.style.borderColor = '#ef4444';
      input.style.animation = 'none';
      setTimeout(() => {
        input.style.animation = 'pwdShake 0.4s ease';
        setTimeout(() => { input.style.animation = ''; input.style.borderColor = '#2d4a6a'; }, 400);
      }, 10);
    }

    /**
     * Toggle staff enrollment on/off.
     * Shows a real 2-3 second processing state while the server updates the session.
     */
    async function adminToggleEnrollment() {
      const btn = document.getElementById('enrollmentToggleBtn');
      const msgDiv = document.getElementById('enrollmentToggleMsg');
      const willEnable = !_enrollmentEnabled;
      const endpoint = willEnable ? '/api/admin/enable-enrollment' : '/api/admin/disable-enrollment';

      // Processing state
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
      if (msgDiv) { msgDiv.style.display = 'none'; }

      try {
        const res = await fetch(endpoint, { method: 'POST', credentials: 'same-origin' });
        const data = await res.json();

        if (res.ok && data.success) {
          _enrollmentEnabled = willEnable;
          applyAdminStateToUI();
          // Show success message
          if (msgDiv) {
            msgDiv.style.display = 'block';
            msgDiv.innerHTML = `<div style="padding:10px 14px; background:${willEnable ? '#064e3b' : '#1e293b'}; border:1px solid ${willEnable ? '#065f46' : '#2d4a6a'}; border-radius:8px; color:${willEnable ? '#34d399' : '#93c5fd'}; font-size:0.85em; display:flex; align-items:center; gap:8px;"><i class="fa-solid fa-circle-check"></i> ${data.message || (willEnable ? 'Staff Enrollment enabled successfully' : 'Staff Enrollment disabled')}</div>`;
            setTimeout(() => { if (msgDiv) msgDiv.style.display = 'none'; }, 4000);
          }
        } else {
          if (msgDiv) {
            msgDiv.style.display = 'block';
            msgDiv.innerHTML = `<div style="padding:10px 14px; background:#450a0a; border:1px solid #7f1d1d; border-radius:8px; color:#fca5a5; font-size:0.85em;"><i class="fa-solid fa-circle-xmark"></i> ${data.message || 'Operation failed'}</div>`;
          }
        }
      } catch (e) {
        if (msgDiv) {
          msgDiv.style.display = 'block';
          msgDiv.innerHTML = `<div style="padding:10px 14px; background:#450a0a; border:1px solid #7f1d1d; border-radius:8px; color:#fca5a5; font-size:0.85em;"><i class="fa-solid fa-circle-xmark"></i> Connection error. Please try again.</div>`;
        }
      } finally {
        btn.disabled = false;
        // Button text already updated by applyAdminStateToUI
      }
    }

    /**
     * Lock configuration — clears server session, hides enrollment, re-locks settings.
     */
    async function adminLockConfiguration() {
      try {
        await fetch('/api/admin/lock', { method: 'POST', credentials: 'same-origin' });
      } catch (e) { /* best-effort */ }
      _adminUnlocked = false;
      _enrollmentEnabled = false;
      applyAdminStateToUI();
      // Switch away from settings-view to reports-view
      const reportsBtn = document.querySelector('.menu-item[title="Attendance Reports"]');
      switchTab('reports-view', reportsBtn);
    }

    // Close modal when clicking backdrop
    document.getElementById('adminPasswordModal').addEventListener('click', function(e) {
      if (e.target === this) closeAdminPasswordModal();
    });

    // CSS for shake animation
    const _adminStyle = document.createElement('style');
    _adminStyle.textContent = `
      @keyframes pwdShake {
        0%,100% { transform:translateX(0); }
        20%      { transform:translateX(-8px); }
        40%      { transform:translateX(8px); }
        60%      { transform:translateX(-5px); }
        80%      { transform:translateX(5px); }
      }
    `;
    document.head.appendChild(_adminStyle);

    // ============================================
    // LEAVE & HOLIDAY MANAGEMENT MODULE JS
    // ============================================
    let _allLeaveRequests = [];

    function switchLeaveSubTab(subtab) {
      document.getElementById('subtab-leave-requests').style.display = subtab === 'requests' ? 'block' : 'none';
      document.getElementById('subtab-leave-balances').style.display = subtab === 'balances' ? 'block' : 'none';
      document.getElementById('subtab-leave-types').style.display = subtab === 'types' ? 'block' : 'none';
      document.getElementById('subtab-company-holidays').style.display = subtab === 'holidays' ? 'block' : 'none';

      document.getElementById('leaveTabReq').className = subtab === 'requests' ? 'btn btn-sm btn-teal' : 'btn btn-sm btn-outline-secondary';
      document.getElementById('leaveTabBal').className = subtab === 'balances' ? 'btn btn-sm btn-teal' : 'btn btn-sm btn-outline-secondary';
      document.getElementById('leaveTabTypes').className = subtab === 'types' ? 'btn btn-sm btn-teal' : 'btn btn-sm btn-outline-secondary';
      document.getElementById('leaveTabHolidays').className = subtab === 'holidays' ? 'btn btn-sm btn-teal' : 'btn btn-sm btn-outline-secondary';

      if (subtab === 'requests') loadLeaveRequests();
      else if (subtab === 'balances') loadLeaveBalances();
      else if (subtab === 'types') loadLeaveTypes();
      else if (subtab === 'holidays') loadCompanyHolidays();
    }

    async function loadLeaveRequests() {
      const tbody = document.getElementById('leaveRequestsTableBody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin"></i> Loading leave requests...</td></tr>';
      try {
        const res = await fetch('/api/leaves');
        const data = await res.json();
        _allLeaveRequests = Array.isArray(data) ? data : [];
        filterLeavesTable();
      } catch (e) {
        console.error("Load leave requests error:", e);
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-danger p-4"><i class="fa-solid fa-circle-exclamation"></i> Error loading leave requests.</td></tr>';
      }
    }

    function filterLeavesTable() {
      const tbody = document.getElementById('leaveRequestsTableBody');
      if (!tbody) return;
      const search = (document.getElementById('leaveSearch')?.value || '').toLowerCase();
      const statusFilter = document.getElementById('leaveStatusFilter')?.value || 'all';

      const filtered = _allLeaveRequests.filter(req => {
        const nameMatch = (req.user_name || '').toLowerCase().includes(search);
        const statusMatch = statusFilter === 'all' || (req.status || '').toLowerCase() === statusFilter.toLowerCase();
        return nameMatch && statusMatch;
      });

      if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted p-4">No leave requests found matching filters.</td></tr>';
        return;
      }

      tbody.innerHTML = filtered.map(req => {
        const start = req.start_date || '--';
        const end = req.end_date || '--';
        let numDays = 1;
        try {
          if (req.start_date && req.end_date) {
            const d1 = new Date(req.start_date);
            const d2 = new Date(req.end_date);
            numDays = Math.max(1, Math.round((d2 - d1) / (1000 * 60 * 60 * 24)) + 1);
          }
        } catch (e) {}

        let statusBadge = '<span class="badge bg-warning-subtle text-warning-emphasis">Pending</span>';
        if (req.status === 'approved') statusBadge = '<span class="badge bg-success-subtle text-success">Approved</span>';
        else if (req.status === 'rejected') statusBadge = '<span class="badge bg-danger-subtle text-danger">Rejected</span>';

        let actionBtns = '';
        if (req.status === 'pending') {
          actionBtns = `
            <button class="btn btn-sm btn-success py-0 px-2" onclick="updateLeaveStatus(${req.id}, 'approved')" title="Approve Leave"><i class="fa-solid fa-check"></i></button>
            <button class="btn btn-sm btn-danger py-0 px-2" onclick="updateLeaveStatus(${req.id}, 'rejected')" title="Reject Leave"><i class="fa-solid fa-xmark"></i></button>
          `;
        }
        actionBtns += ` <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteLeaveRequest(${req.id})" title="Delete Request"><i class="fa-solid fa-trash"></i></button>`;

        return `
          <tr>
            <td style="font-weight:700; color:#64748b;">#${req.id}</td>
            <td style="font-weight:700; color:#173042;">${escapeHtml(req.user_name || 'User ' + req.user_id)}</td>
            <td><span class="badge bg-light text-dark border" style="text-transform:capitalize;">${escapeHtml(req.leave_type || 'annual')}</span></td>
            <td><small style="font-weight:600; color:#475569;">${start} to ${end}</small></td>
            <td style="font-weight:700; color:#0d9488;">${numDays} day(s)</td>
            <td style="max-width:200px; font-size:0.85em; color:#64748b;" title="${escapeHtml(req.reason || '')}">${escapeHtml(req.reason || '--')}</td>
            <td>${statusBadge}</td>
            <td><small style="color:#64748b;">${escapeHtml(req.approved_by || '--')}</small></td>
            <td>${actionBtns}</td>
          </tr>
        `;
      }).join('');
    }

    async function updateLeaveStatus(leaveId, status) {
      if (!confirm(`Are you sure you want to set leave #${leaveId} to ${status.toUpperCase()}?`)) return;
      try {
        const res = await fetch(`/api/leaves/${leaveId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: status, approved_by: 'Admin' })
        });
        const data = await res.json();
        if (data.success) {
          loadLeaveRequests();
        } else {
          alert("Failed to update status.");
        }
      } catch (e) {
        alert("Network error updating status.");
      }
    }

    async function deleteLeaveRequest(leaveId) {
      if (!confirm(`Permanently delete leave request #${leaveId}?`)) return;
      try {
        const res = await fetch(`/api/leaves/${leaveId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) loadLeaveRequests();
      } catch (e) {
        alert("Error deleting leave request.");
      }
    }

    async function loadLeaveBalances() {
      const tbody = document.getElementById('leaveBalancesTableBody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin"></i> Loading balances...</td></tr>';
      try {
        const res = await fetch('/api/leaves/balances?year=2026');
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-4">No employee balances found.</td></tr>';
          return;
        }

        tbody.innerHTML = data.map(b => {
          const casual = b.balances['casual'] || { allocated: 10, used: 0, remaining: 10 };
          const sick = b.balances['sick'] || { allocated: 8, used: 0, remaining: 8 };
          const annual = b.balances['annual'] || { allocated: 14, used: 0, remaining: 14 };
          const unpaid = b.balances['unpaid'] || { used: 0 };

          return `
            <tr>
              <td style="font-weight:700; color:#173042;">${escapeHtml(b.user_name)}</td>
              <td><span class="badge bg-light text-dark border">${escapeHtml(b.department || 'General')}</span></td>
              <td><span class="text-success font-weight-bold">${casual.used}</span> / ${casual.allocated} <small class="text-muted">(${casual.remaining} rem)</small></td>
              <td><span class="text-info font-weight-bold">${sick.used}</span> / ${sick.allocated} <small class="text-muted">(${sick.remaining} rem)</small></td>
              <td><span class="text-teal font-weight-bold" style="color:#0d9488;">${annual.used}</span> / ${annual.allocated} <small class="text-muted">(${annual.remaining} rem)</small></td>
              <td><span class="text-danger font-weight-bold">${unpaid.used}</span> days</td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        console.error("Load balances error:", e);
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger p-4"><i class="fa-solid fa-circle-exclamation"></i> Error loading balances.</td></tr>';
      }
    }

    async function loadLeaveTypes() {
      const tbody = document.getElementById('leaveTypesTableBody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin"></i> Loading leave types...</td></tr>';
      try {
        const res = await fetch('/api/leave-types');
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-4">No leave types configured.</td></tr>';
          return;
        }

        tbody.innerHTML = data.map(lt => `
          <tr>
            <td style="font-weight:700; color:#173042;">${escapeHtml(lt.name)}</td>
            <td><code>${escapeHtml(lt.code)}</code></td>
            <td style="font-weight:700; color:#0d9488;">${lt.yearly_allowance} days / yr</td>
            <td>${lt.is_paid ? '<span class="badge bg-success-subtle text-success">Paid Leave</span>' : '<span class="badge bg-danger-subtle text-danger">Unpaid (LWP)</span>'}</td>
            <td style="font-size:0.85em; color:#64748b;">${escapeHtml(lt.description || '--')}</td>
            <td>
              <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteLeaveType(${lt.id})" title="Delete Type"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        console.error("Load leave types error:", e);
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger p-4">Error loading leave types.</td></tr>';
      }
    }

    async function loadCompanyHolidays() {
      const tbody = document.getElementById('companyHolidaysTableBody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin"></i> Loading holidays...</td></tr>';
      try {
        const res = await fetch('/api/holidays');
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-4">No public holidays added yet.</td></tr>';
          return;
        }

        tbody.innerHTML = data.map(h => `
          <tr>
            <td style="font-weight:700; color:#173042;"><i class="fa-solid fa-calendar-day" style="color:#0d9488; margin-right:6px;"></i> ${escapeHtml(h.name)}</td>
            <td style="font-weight:700; color:#0f172a;">${h.holiday_date}</td>
            <td style="font-size:0.85em; color:#64748b;">${escapeHtml(h.description || '--')}</td>
            <td>${h.is_recurring ? '<span class="badge bg-info-subtle text-info">Annual</span>' : '<span class="badge bg-secondary-subtle text-secondary">One-time</span>'}</td>
            <td>
              <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteCompanyHoliday(${h.id})" title="Delete Holiday"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        console.error("Load holidays error:", e);
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger p-4">Error loading holidays.</td></tr>';
      }
    }

    async function openFileLeaveModal() {
      const modal = document.getElementById('fileLeaveModal');
      const select = document.getElementById('modalLeaveUserSelect');
      if (!modal || !select) return;
      
      select.innerHTML = '<option value="">Loading active staff...</option>';
      modal.style.display = 'flex';
      
      try {
        const res = await fetch('/api/users');
        const data = await res.json();
        const users = data.users || [];
        select.innerHTML = '<option value="">Select Employee...</option>' + 
          users.map(u => `<option value="${u.id}">${escapeHtml(u.name)} (${escapeHtml(u.department || 'Staff')})</option>`).join('');
      } catch (e) {
        select.innerHTML = '<option value="">Failed to load employees</option>';
      }
    }

    function closeFileLeaveModal() {
      document.getElementById('fileLeaveModal').style.display = 'none';
    }

    async function submitLeaveRequest() {
      const userId = document.getElementById('modalLeaveUserSelect').value;
      const leaveType = document.getElementById('modalLeaveTypeSelect').value;
      const startDate = document.getElementById('modalLeaveStartDate').value;
      const endDate = document.getElementById('modalLeaveEndDate').value;
      const reason = document.getElementById('modalLeaveReason').value;

      if (!userId || !startDate || !endDate) {
        alert("Please select employee, start date, and end date.");
        return;
      }

      try {
        const res = await fetch('/api/leaves', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: parseInt(userId),
            leave_type: leaveType,
            start_date: startDate,
            end_date: endDate,
            reason: reason
          })
        });
        const data = await res.json();
        if (data.success) {
          closeFileLeaveModal();
          loadLeaveRequests();
        } else {
          alert("Failed to submit leave application: " + (data.message || 'Error'));
        }
      } catch (e) {
        alert("Network error submitting leave request.");
      }
    }

    function openAddLeaveTypeModal() {
      document.getElementById('leaveTypeModal').style.display = 'flex';
    }
    function closeLeaveTypeModal() {
      document.getElementById('leaveTypeModal').style.display = 'none';
    }

    async function submitLeaveType() {
      const name = document.getElementById('modalLeaveTypeName').value.trim();
      const days = parseFloat(document.getElementById('modalLeaveTypeDays').value) || 12.0;
      const isPaid = parseInt(document.getElementById('modalLeaveTypeIsPaid').value);
      const desc = document.getElementById('modalLeaveTypeDesc').value.trim();
      const code = name.toLowerCase().replace(/[^a-z0-9]/g, '_');

      if (!name) {
        alert("Please enter a policy name.");
        return;
      }

      try {
        const res = await fetch('/api/leave-types', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, code: code, yearly_allowance: days, is_paid: isPaid, description: desc })
        });
        const data = await res.json();
        if (data.success) {
          closeLeaveTypeModal();
          loadLeaveTypes();
        } else {
          alert("Failed to add leave type: " + (data.message || 'Error'));
        }
      } catch (e) {
        alert("Error adding leave type.");
      }
    }

    async function deleteLeaveType(typeId) {
      if (!confirm("Delete this leave category?")) return;
      try {
        const res = await fetch(`/api/leave-types/${typeId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) loadLeaveTypes();
      } catch (e) {
        alert("Error deleting leave type.");
      }
    }

    function openAddHolidayModal() {
      document.getElementById('companyHolidayModal').style.display = 'flex';
    }
    function closeAddHolidayModal() {
      document.getElementById('companyHolidayModal').style.display = 'none';
    }

    async function submitCompanyHoliday() {
      const name = document.getElementById('modalHolidayName').value.trim();
      const hdate = document.getElementById('modalHolidayDate').value;
      const desc = document.getElementById('modalHolidayDesc').value.trim();

      if (!name || !hdate) {
        alert("Please enter holiday name and date.");
        return;
      }

      try {
        const res = await fetch('/api/holidays', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name, holiday_date: hdate, description: desc })
        });
        const data = await res.json();
        if (data.success) {
          closeAddHolidayModal();
          loadCompanyHolidays();
        } else {
          alert("Failed to add holiday.");
        }
      } catch (e) {
        alert("Error adding holiday.");
      }
    }

    async function deleteCompanyHoliday(holidayId) {
      if (!confirm("Delete this public holiday?")) return;
      try {
        const res = await fetch(`/api/holidays/${holidayId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) loadCompanyHolidays();
      } catch (e) {
        alert("Error deleting holiday.");
      }
    }

    // On page load: sync admin session state from server
    window.addEventListener('load', function() {
      syncAdminState();
    });
  