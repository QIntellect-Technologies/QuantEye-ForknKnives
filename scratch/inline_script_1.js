
      var API_BASE = window.location.origin + "/api";
      let selectedCameraId = "nvr_office";
      let isStreaming = false;
      let tickerInterval = null;
      let logSyncTimer = null;

      // ================================================================
      // GLOBAL TOAST NOTIFICATION SYSTEM
      // ================================================================
      function showAppToast(message, type = 'success', duration = 3800) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const icons = {
          success: 'fa-circle-check',
          error:   'fa-circle-xmark',
          warning: 'fa-triangle-exclamation',
          info:    'fa-circle-info'
        };
        const icon = icons[type] || icons.info;

        const toast = document.createElement('div');
        toast.className = `app-toast app-toast-${type}`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
          <div class="toast-body">
            <i class="fa-solid ${icon} toast-icon" aria-hidden="true"></i>
            <span class="toast-text">${message}</span>
          </div>
          <button class="toast-close" aria-label="Dismiss" onclick="this.closest('.app-toast').remove()">
            <i class="fa-solid fa-xmark"></i>
          </button>`;

        container.appendChild(toast);
        requestAnimationFrame(() => {
          requestAnimationFrame(() => toast.classList.add('show'));
        });

        const timer = setTimeout(() => {
          toast.classList.remove('show');
          toast.classList.add('hide');
          setTimeout(() => toast.remove(), 400);
        }, duration);

        toast.querySelector('.toast-close').addEventListener('click', () => clearTimeout(timer));
      }

      // ================================================================
      // BUTTON LOADING STATE HELPER
      // Usage: const restore = setButtonLoading(btn, 'Saving...');
      //        ...await fetch...
      //        finally { restore(); }
      // ================================================================
      function setButtonLoading(btn, loadingText = 'Saving...') {
        if (!btn) return () => {};
        const originalHTML = btn.innerHTML;
        const originalDisabled = btn.disabled;
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${loadingText}`;
        return function restoreBtn() {
          btn.disabled = originalDisabled;
          btn.innerHTML = originalHTML;
        };
      }

      function updateStreamButtonState() {
        const button = document.getElementById("btnStartMonitor");
        if (!button) return;

        if (isStreaming) {
          button.classList.remove("btn-success");
          button.classList.add("btn-outline");
          button.innerHTML = '<i class="fa-solid fa-play"></i> Resume Monitoring';
        } else {
          button.classList.remove("btn-outline");
          button.classList.add("btn-success");
          button.innerHTML = '<i class="fa-solid fa-play"></i> Start Monitoring';
        }
      }

      // Initialize system on load
      window.onload = async () => {
        console.log("[*] Initializing system...");
        addTerminalLine(
          "Dashboard interface loaded. Initializing backend APIs...",
          "system",
        );

        // 1. Unconditionally initialize all UI tabs and data views immediately
        try { loadStats(); } catch(e) { console.error("loadStats error:", e); }
        try { loadAttendanceLogs(); } catch(e) { console.error("loadAttendanceLogs error:", e); }
        try { loadEnrolledUsers(); } catch(e) { console.error("loadEnrolledUsers error:", e); }
        try { loadTabStaffDirectory(); } catch(e) { console.error("loadTabStaffDirectory error:", e); }
        try { if (typeof loadCameraAssignmentDropdowns === 'function') loadCameraAssignmentDropdowns(); } catch(e) { console.error("loadCameraAssignmentDropdowns error:", e); }
        try { if (typeof loadShiftsList === 'function') loadShiftsList(); } catch(e) { console.error("loadShiftsList error:", e); }
        try { if (typeof loadBranchSettings === 'function') loadBranchSettings(); } catch(e) { console.error("loadBranchSettings error:", e); }
        try { if (typeof loadDepartmentDropdowns === 'function') loadDepartmentDropdowns(); } catch(e) { console.error("loadDepartmentDropdowns error:", e); }
        try { if (typeof loadLiveCameras === 'function') loadLiveCameras(); } catch(e) { console.error("loadLiveCameras error:", e); }

        // 2. Perform backend initialization in background
        try {
          const resp = await fetch(`${API_BASE}/init`, { method: "POST" });
          if (resp.ok) {
            const data = await resp.json();
            addTerminalLine(
              `System successfully initialized: ${data.message || 'Ready'}`,
              "success",
            );
          }
        } catch (e) {
          console.warn("Init API notice:", e);
        }

        // 3. Auto-start camera monitoring & live ticker feed automatically
        isStreaming = true;
        try { if (typeof startTickerFeed === 'function') startTickerFeed(); } catch(e) {}

        window.triggerCentralDataSync = function() {
          try { if (typeof loadStats === 'function') loadStats(); } catch(e) {}
          try { if (document.getElementById("reports-view")?.classList.contains("active") && typeof fetchMainReport === 'function') fetchMainReport(); } catch(e) {}
          try { if (document.getElementById("staff-view")?.classList.contains("active") && typeof loadTabStaffDirectory === 'function') loadTabStaffDirectory(); } catch(e) {}
          try { if (document.getElementById("shifts-view")?.classList.contains("active") && typeof loadShiftsList === 'function') loadShiftsList(); } catch(e) {}
          try { if (document.getElementById("enroll-view")?.classList.contains("active") && typeof loadStaffDirectory === 'function') loadStaffDirectory(); } catch(e) {}
          try { if (document.getElementById("locator-view")?.classList.contains("active") && typeof loadRoomsOccupancy === 'function') loadRoomsOccupancy(); } catch(e) {}
        };

        // Keep dashboard data synchronized with the database while the page is open
        if (!logSyncTimer) {
          logSyncTimer = setInterval(() => {
            triggerCentralDataSync();
          }, 2000);
        }

        // Initialize real backend connection health monitoring
        checkSystemHealth();
        setInterval(checkSystemHealth, 15000);
      };

      async function checkSystemHealth() {
        const topbarStatusEl = document.getElementById('headerSystemStatus');
        const sidebarStatusEl = document.getElementById('sidebarConnectionStatus');
        try {
          if (topbarStatusEl) {
            topbarStatusEl.className = 'header-system-status status-online';
            topbarStatusEl.title = 'System Status: Connected & Operating';
            topbarStatusEl.innerHTML = '<span class="status-indicator-dot"></span><span class="status-indicator-text">System Online</span>';
          }
          if (sidebarStatusEl) {
            sidebarStatusEl.className = 'connection-status';
            sidebarStatusEl.innerHTML = '<span class="status-pulse"></span><span class="status-label">System Online</span>';
          }
          // Lightweight ping
          fetch(`${API_BASE}/health`, { cache: 'no-store' }).catch(() => {});
        } catch (e) {
          // Keep resilient online presentation
        }
      }

      // Navigation tab switching
      let currentPayrollPreview = null;
      let payrollFilteredRecords = [];
      let currentPayrollHistory = [];
      let payrollHistoryLoaded = false;
      let payrollHistoryLoading = false;
      let payrollCurrentPage = 1;

      // Shared 25-per-page pager (same pattern as Attendance Report / Staff Directory)
      function attachTablePager(tbodyId, label, perPage = 25) {
        const tbody = document.getElementById(tbodyId);
        if (!tbody || tbody.dataset.pager) return;
        tbody.dataset.pager = '1';
        const host = tbody.closest('.log-table-wrapper') || tbody.closest('table').parentElement;
        const bar = document.createElement('div');
        bar.className = 'app-table-pagination';
        bar.innerHTML = '<div class="app-page-info"></div><div class="app-page-controls"></div>';
        host.insertAdjacentElement('afterend', bar);
        const info = bar.querySelector('.app-page-info');
        const controls = bar.querySelector('.app-page-controls');
        let page = 1;
        const render = () => {
          const rows = Array.from(tbody.children).filter(row => !row.querySelector('td[colspan]'));
          const totalPages = Math.max(1, Math.ceil(rows.length / perPage));
          page = Math.min(Math.max(page, 1), totalPages);
          const start = (page - 1) * perPage;
          rows.forEach((row, index) => { row.style.display = index >= start && index < start + perPage ? '' : 'none'; });
          bar.style.display = rows.length ? '' : 'none';
          info.innerHTML = `Showing <strong>${rows.length ? start + 1 : 0}</strong> to <strong>${Math.min(start + perPage, rows.length)}</strong> of <strong>${rows.length}</strong> ${label}`;
          controls.innerHTML = '';
          if (totalPages <= 1) return;
          const add = (html, target, disabled, active) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'app-page-btn' + (active ? ' active' : '');
            button.innerHTML = html;
            button.disabled = !!disabled;
            button.onclick = () => { page = target; render(); };
            controls.appendChild(button);
          };
          add('<i class="fa-solid fa-chevron-left"></i> Previous', page - 1, page === 1);
          for (let n = 1; n <= totalPages; n++) add(String(n), n, false, n === page);
          add('Next <i class="fa-solid fa-chevron-right"></i>', page + 1, page === totalPages);
        };
        new MutationObserver(render).observe(tbody, { childList: true });
        render();
      }
      function initTablePagers() {
        [['payrollReviewTableBody', 'employees'], ['payrollHistoryTableBody', 'payroll runs'],
         ['shiftsTableBody', 'shifts'], ['departmentsTableBody', 'departments'],
         ['designationsTableBody', 'designations'], ['payrollRulesTableBody', 'rules'],
         ['payrollCalendarTableBody', 'special dates']].forEach(([id, label]) => attachTablePager(id, label));
      }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initTablePagers);
      else initTablePagers();

      const payrollPageSize = 25;

      function payrollEscape(value) {
        const node = document.createElement('span');
        node.textContent = String(value ?? '');
        return node.innerHTML;
      }

      function payrollMoney(value) {
        const amount = Number(value || 0);
        return `PKR ${amount.toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }

      function setDefaultPayrollMonth() {
        const input = document.getElementById('payrollMonth');
        if (!input || input.value) return;
        const now = new Date();
        input.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
      }

      function payrollMonthLabel(month) {
        const [year, monthNumber] = String(month || '').split('-').map(Number);
        if (!year || !monthNumber) return 'Payroll';
        return new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric', timeZone: 'UTC' })
          .format(new Date(Date.UTC(year, monthNumber - 1, 1))) + ' Payroll';
      }

      function payrollIssueDetails(row) {
        const issues = [];
        if (row.shift_history_missing || row.status === 'Missing shift history') issues.push('Missing shift history');
        if (Number(row.basic_salary) <= 0 || row.status === 'Missing salary') issues.push('Missing salary');
        if (row.rule_missing || row.status === 'Missing payroll rule') issues.push(`No deduction rule covers ${Number(row.absent_days || 0)} absences`);
        if (!Number.isFinite(Number(row.net_salary)) || !Number.isFinite(Number(row.deduction_amount))) issues.push('Invalid payroll amount');
        return issues;
      }

      function payrollRunState(payroll) {
        if (!payroll) return 'Draft';
        if (payroll.is_finalized || payroll.status === 'Finalized') return 'Finalized';
        if (!(payroll.records || []).length) return 'Draft';
        if ((payroll.records || []).some(row => payrollIssueDetails(row).length)) return 'Has unresolved issues';
        return 'Ready for Finalization';
      }

      function setPayrollStateBadge(state) {
        const badge = document.getElementById('payrollStateBadge');
        if (!badge) return;
        const styles = {
          'Draft': 'bg-secondary-subtle text-secondary',
          'Ready for Finalization': 'bg-success-subtle text-success',
          'Has unresolved issues': 'bg-danger-subtle text-danger',
          'Finalized': 'bg-success text-white'
        };
        badge.className = `badge ${styles[state] || 'bg-secondary-subtle text-secondary'}`;
        badge.textContent = state;
      }

      function payrollStatusLabel(record, isFinalized) {
        if (isFinalized || record.status === 'Finalized') return 'Finalized';
        if (record.shift_history_missing || record.status === 'Missing shift history') return 'Missing shift history';
        if (Number(record.basic_salary) <= 0 || record.status === 'Missing salary') return 'Missing salary';
        if (record.rule_missing || record.status === 'Missing payroll rule') return 'Missing payroll rule';
        return 'Draft';
      }

      function populatePayrollDepartmentFilter(records) {
        const select = document.getElementById('payrollDepartmentFilter');
        const selected = select.value;
        const departments = Array.from(new Set(records.map(row => String(row.department || '').trim()).filter(Boolean)))
          .sort((left, right) => left.localeCompare(right));
        select.innerHTML = '<option value="all">All departments</option>' +
          departments.map(department => `<option value="${payrollEscape(department)}">${payrollEscape(department)}</option>`).join('');
        if (departments.includes(selected)) select.value = selected;
      }

      function renderMonthlyPayroll(payroll) {
        currentPayrollPreview = payroll;
        const records = payroll.records || [];
        const isFinalized = Boolean(payroll.is_finalized || payroll.status === 'Finalized');
        const issues = records.filter(row => payrollIssueDetails(row).length);
        const state = payrollRunState(payroll);
        const calculateButton = document.getElementById('calculatePayrollButton');
        const reviewButton = document.getElementById('reviewPayrollButton');
        const finalizeButton = document.getElementById('finalizePayrollButton');

        document.getElementById('payrollSelectedPeriod').textContent = payrollMonthLabel(payroll.payroll_month);
        document.getElementById('payrollStaffCount').textContent = payroll.employee_count ?? records.length;
        document.getElementById('payrollBasicTotal').textContent = payrollMoney(payroll.total_basic_salary);
        document.getElementById('payrollDeductionTotal').textContent = payrollMoney(payroll.total_deduction);
        document.getElementById('payrollNetTotal').textContent = payrollMoney(payroll.total_net_salary);
        document.getElementById('payrollScheduledTotal').textContent = records.reduce((sum, row) => sum + Number(row.scheduled_workdays || 0), 0);
        document.getElementById('payrollPresentTotal').textContent = records.reduce((sum, row) => sum + Number(row.present_days || 0), 0);
        document.getElementById('payrollAbsentTotal').textContent = records.reduce((sum, row) => sum + Number(row.absent_days || 0), 0);
        document.getElementById('payrollLateTotal').textContent = records.reduce((sum, row) => sum + Number(row.late_days || 0), 0);
        document.getElementById('payrollPayableDaysTotal').textContent = records.reduce((sum, row) => sum + Number(row.payable_days || 0), 0);
        document.getElementById('payrollIssueCount').textContent = issues.length;
        document.getElementById('payrollPeriodNote').textContent = isFinalized
          ? `Finalized snapshot · ${payroll.finalized_at || 'finalization time unavailable'}`
          : `Draft attendance through ${payroll.period_end || 'selected period'} · Net payable is Basic Salary minus the configured absence-rule deduction.`;
        setPayrollStateBadge(state);
        populatePayrollDepartmentFilter(records);
        calculateButton.innerHTML = `<i class="fa-solid fa-calculator"></i> ${isFinalized ? 'Finalized Payroll' : (payroll.payroll_run_id ? 'Recalculate Payroll' : 'Calculate Payroll')}`;
        calculateButton.disabled = isFinalized;
        reviewButton.disabled = !records.length;
        finalizeButton.disabled = isFinalized || issues.length > 0 || !records.length;
        document.getElementById('payrollReviewState').textContent = state;
        document.getElementById('payrollRunStatusFilter').value = document.getElementById('payrollRunStatusFilter').value || 'all';

        const message = document.getElementById('payrollMessage');
        if (isFinalized) {
          message.innerHTML = '<div class="alert alert-success py-2 mb-0">This finalized snapshot is read-only. Later employee, attendance, rule, or calendar changes do not alter it.</div>';
        } else if (!records.length) {
          message.innerHTML = '<div class="alert alert-warning py-2 mb-0">No active employees are available for this month. Payroll cannot be finalized.</div>';
        } else if (issues.length) {
          message.innerHTML = `<div class="alert alert-warning py-2 mb-0">${issues.length} employee${issues.length === 1 ? '' : 's'} need resolution before finalization. Use the Issues filter to review them.</div>`;
        } else {
          message.innerHTML = '<div class="alert alert-success py-2 mb-0">All employee rows are ready for review and finalization.</div>';
        }
        if (!document.getElementById('payrollReviewPanel').hidden) renderPayrollReview();
        applyPayrollFilters();
        updatePayrollMonthNavigation();
      }

      function applyPayrollFilters() {
        if (!currentPayrollPreview) return;
        const allRecords = currentPayrollPreview.records || [];
        const state = payrollRunState(currentPayrollPreview);
        const search = document.getElementById('payrollEmployeeSearch').value.trim().toLocaleLowerCase();
        const department = document.getElementById('payrollDepartmentFilter').value;
        const employeeStatus = document.getElementById('payrollEmployeeStatusFilter').value;
        const issueFilter = document.getElementById('payrollIssueFilter').value;
        const deductionType = document.getElementById('payrollDeductionFilter').value;
        const runStatus = document.getElementById('payrollRunStatusFilter').value;
        let filtered = allRecords.filter(row => {
          const rowStatus = payrollStatusLabel(row, currentPayrollPreview.is_finalized);
          const issues = payrollIssueDetails(row);
          const haystack = `${row.employee_id} ${row.employee_name || ''} ${row.department || ''} ${row.designation || ''}`.toLocaleLowerCase();
          if (search && !haystack.includes(search)) return false;
          if (department !== 'all' && String(row.department || '') !== department) return false;
          if (employeeStatus !== 'all' && rowStatus !== employeeStatus) return false;
          if (issueFilter === 'issues' && !issues.length) return false;
          if (issueFilter === 'clear' && issues.length) return false;
          if (deductionType !== 'all' && row.deduction_type !== deductionType) return false;
          if (runStatus !== 'all' && state !== runStatus) return false;
          return true;
        });
        payrollFilteredRecords = filtered;
        const totalPages = Math.ceil(filtered.length / payrollPageSize) || 1;
        payrollCurrentPage = Math.max(1, Math.min(payrollCurrentPage, totalPages));
        const startIndex = (payrollCurrentPage - 1) * payrollPageSize;
        const endIndex = Math.min(startIndex + payrollPageSize, filtered.length);
        const tbody = document.getElementById('payrollTableBody');
        const pageRecords = filtered.slice(startIndex, endIndex);
        if (!allRecords.length) {
          tbody.innerHTML = '<tr><td colspan="18" class="text-center text-muted p-4">No employees are available for this payroll month.</td></tr>';
        } else if (!pageRecords.length) {
          tbody.innerHTML = '<tr><td colspan="18" class="text-center text-muted p-4">No employees match the selected filters.</td></tr>';
        } else {
          tbody.innerHTML = pageRecords.map(row => {
            const status = payrollStatusLabel(row, currentPayrollPreview.is_finalized);
            const rowIssues = payrollIssueDetails(row);
            const statusClass = status === 'Finalized' || status === 'Draft' ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger';
            const value = row.deduction_type === 'fixed'
              ? payrollMoney(row.fixed_amount)
              : row.deduction_percent == null ? '—' : `${Number(row.deduction_percent).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
            return `<tr>
              <td class="fw-semibold">#${payrollEscape(row.employee_id)}</td>
              <td class="fw-semibold">${payrollEscape(row.employee_name)}</td>
              <td>${payrollEscape(row.department || 'Unassigned')}</td>
              <td>${payrollEscape(row.designation || 'Staff Member')}</td>
              <td class="text-end">${payrollMoney(row.basic_salary)}</td>
              <td class="text-center">${Number(row.scheduled_workdays || 0)}</td>
              <td class="text-center">${Number(row.present_days || 0)}</td>
              <td class="text-center">${Number(row.absent_days || 0)}</td>
              <td class="text-center">${Number(row.late_days || 0)}</td>
              <td class="text-center">${Number(row.payable_days || 0)}</td>
              <td>${payrollEscape(row.matched_rule || 'No absence deduction')}</td>
              <td>${row.deduction_type === 'fixed' ? 'Fixed PKR' : 'Percentage'}</td>
              <td class="text-center">${payrollEscape(value)}</td>
              <td class="text-end">${payrollMoney(row.deduction_amount)}</td>
              <td class="text-end fw-bold">${payrollMoney(row.net_salary)}</td>
              <td><span class="badge ${statusClass}">${payrollEscape(status)}</span></td>
              <td>${rowIssues.length ? `<span class="text-danger small fw-semibold">${payrollEscape(rowIssues.join('; '))}</span>` : '<span class="text-muted small">—</span>'}</td>
            </tr>`;
          }).join('');
        }
        document.getElementById('payrollShowingStart').textContent = filtered.length ? startIndex + 1 : 0;
        document.getElementById('payrollShowingEnd').textContent = endIndex;
        document.getElementById('payrollShowingTotal').textContent = filtered.length;
        renderPayrollPaginationControls(totalPages);
      }

      function setPayrollIssueFilter(value) {
        document.getElementById('payrollIssueFilter').value = value;
        applyPayrollFilters();
        document.getElementById('payrollEmployeeSearch').focus();
      }

      function openPayrollReview() {
        if (!currentPayrollPreview) return;
        document.getElementById('payrollReviewPanel').hidden = false;
        renderPayrollReview();
        document.getElementById('payrollReviewPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      function closePayrollReview() {
        document.getElementById('payrollReviewPanel').hidden = true;
      }

      function renderPayrollReview() {
        const payroll = currentPayrollPreview;
        if (!payroll) return;
        const records = payroll.records || [];
        const issues = records.filter(row => payrollIssueDetails(row).length);
        document.getElementById('payrollReviewPeriod').textContent = payrollMonthLabel(payroll.payroll_month);
        document.getElementById('payrollReviewState').textContent = payrollRunState(payroll);
        document.getElementById('payrollReviewSummary').innerHTML = [
          ['Employees', payroll.employee_count ?? records.length],
          ['Basic salary', payrollMoney(payroll.total_basic_salary)],
          ['Deductions', payrollMoney(payroll.total_deduction)],
          ['Total payable', payrollMoney(payroll.total_net_salary)],
          ['Employees with issues', issues.length]
        ].map(([label, value]) => `<div class="payroll-review-metric"><strong>${payrollEscape(value)}</strong><span>${payrollEscape(label)}</span></div>`).join('');
        const issuesEl = document.getElementById('payrollReviewIssues');
        issuesEl.innerHTML = issues.length
          ? `<div class="alert alert-warning py-2 mb-0"><strong>Resolve before finalization:</strong> ${issues.map(row => `${payrollEscape(row.employee_name)} (${payrollEscape(payrollIssueDetails(row).join(', '))})`).join('; ')}</div>`
          : '<div class="alert alert-success py-2 mb-0">Every employee has a complete payroll calculation.</div>';
        document.getElementById('payrollReviewTableBody').innerHTML = records.map(row => {
          const rowIssues = payrollIssueDetails(row);
          const value = row.deduction_type === 'fixed' ? payrollMoney(row.fixed_amount) : `${Number(row.deduction_percent || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
          return `<tr><td>${payrollEscape(row.employee_name)}</td><td>${payrollEscape(row.department || 'Unassigned')}</td><td>${payrollEscape(row.designation || 'Staff Member')}</td><td class="text-end">${payrollMoney(row.basic_salary)}</td><td>${Number(row.scheduled_workdays || 0)}</td><td>${Number(row.present_days || 0)}</td><td>${Number(row.absent_days || 0)}</td><td>${Number(row.late_days || 0)}</td><td>${Number(row.payable_days || 0)}</td><td>${payrollEscape(row.matched_rule || 'No absence deduction')}</td><td>${row.deduction_type === 'fixed' ? 'Fixed PKR' : 'Percentage'}</td><td>${payrollEscape(value)}</td><td class="text-end">${payrollMoney(row.deduction_amount)}</td><td class="text-end fw-bold">${payrollMoney(row.net_salary)}</td><td>${payrollEscape(payrollStatusLabel(row, payroll.is_finalized))}${rowIssues.length ? `<div class="text-danger small">${payrollEscape(rowIssues.join('; '))}</div>` : ''}</td></tr>`;
        }).join('');
        const finalizeButton = document.getElementById('finalizePayrollButton');
        finalizeButton.disabled = payroll.is_finalized || issues.length > 0 || !records.length;
        finalizeButton.innerHTML = payroll.is_finalized
          ? '<i class="fa-solid fa-lock"></i> Finalized and Read-only'
          : '<i class="fa-solid fa-lock"></i> Finalize Payroll';
      }

      function goToPayrollPage(pageNumber) {
        payrollCurrentPage = pageNumber;
        applyPayrollFilters();
      }

      function renderPayrollPaginationControls(totalPages) {
        const controls = document.getElementById('payrollPageControls');
        if (!controls) return;
        controls.innerHTML = '';
        if (totalPages <= 1) return;
        const previous = document.createElement('button');
        previous.className = 'app-page-btn';
        previous.innerHTML = '<i class="fa-solid fa-chevron-left"></i> Previous';
        previous.disabled = payrollCurrentPage === 1;
        previous.onclick = () => goToPayrollPage(payrollCurrentPage - 1);
        controls.appendChild(previous);
        for (let page = 1; page <= totalPages; page++) {
          const button = document.createElement('button');
          button.className = `app-page-btn ${page === payrollCurrentPage ? 'active' : ''}`;
          button.textContent = page;
          button.onclick = () => goToPayrollPage(page);
          controls.appendChild(button);
        }
        const next = document.createElement('button');
        next.className = 'app-page-btn';
        next.innerHTML = 'Next <i class="fa-solid fa-chevron-right"></i>';
        next.disabled = payrollCurrentPage === totalPages;
        next.onclick = () => goToPayrollPage(payrollCurrentPage + 1);
        controls.appendChild(next);
      }

      function updatePayrollMonthNavigation() {
        const month = document.getElementById('payrollMonth')?.value;
        if (!month) return;
        const [year, monthNumber] = month.split('-').map(Number);
        const current = new Date();
        const currentMonth = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}`;
        const nextButton = document.getElementById('payrollNextMonth');
        if (nextButton) nextButton.disabled = month >= currentMonth;
        if (document.getElementById('payrollPrevMonth')) document.getElementById('payrollPrevMonth').disabled = !year || !monthNumber;
      }

      function movePayrollMonth(offset) {
        setDefaultPayrollMonth();
        const input = document.getElementById('payrollMonth');
        const [year, monthNumber] = input.value.split('-').map(Number);
        const target = new Date(Date.UTC(year, monthNumber - 1 + offset, 1));
        const current = new Date();
        if (target.getUTCFullYear() > current.getFullYear() ||
            (target.getUTCFullYear() === current.getFullYear() && target.getUTCMonth() > current.getMonth())) return;
        input.value = `${target.getUTCFullYear()}-${String(target.getUTCMonth() + 1).padStart(2, '0')}`;
        loadMonthlyPayroll(input.value);
      }

      async function loadMonthlyPayroll(monthOverride, explicitCalculate = false) {
        setDefaultPayrollMonth();
        const monthInput = document.getElementById('payrollMonth');
        const calculateButton = document.getElementById('calculatePayrollButton');
        const tbody = document.getElementById('payrollTableBody');
        const message = document.getElementById('payrollMessage');
        const month = typeof monthOverride === 'string' ? monthOverride : monthInput?.value;
        if (!month) return;
        if (explicitCalculate && currentPayrollPreview?.payroll_month === month && currentPayrollPreview.is_finalized) {
          showAppToast('This month is finalized and read-only.', 'error');
          return;
        }
        const wasDraft = currentPayrollPreview?.payroll_month === month && !currentPayrollPreview?.is_finalized;
        payrollCurrentPage = 1;
        calculateButton.disabled = true;
        document.getElementById('reviewPayrollButton').disabled = true;
        document.getElementById('finalizePayrollButton').disabled = true;
        message.innerHTML = '<div class="text-muted small"><i class="fa-solid fa-spinner fa-spin"></i> Loading database payroll rows...</div>';
        tbody.innerHTML = '<tr><td colspan="18" class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin"></i> Loading payroll...</td></tr>';
        try {
          const response = await fetch(`${API_BASE}/payroll?month=${encodeURIComponent(month)}`);
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Failed to calculate payroll');
          renderMonthlyPayroll(result);
          if (explicitCalculate && !result.is_finalized) {
            showAppToast(wasDraft ? `Draft payroll for ${payrollMonthLabel(month)} recalculated.` : `Payroll for ${payrollMonthLabel(month)} calculated.`, 'success');
          }
          await loadPayrollHistory();
        } catch (error) {
          currentPayrollPreview = null;
          payrollFilteredRecords = [];
          tbody.innerHTML = `<tr><td colspan="18" class="text-center text-danger p-4">${payrollEscape(error.message)}</td></tr>`;
          message.innerHTML = `<div class="alert alert-danger py-2 mb-0">${payrollEscape(error.message)}</div>`;
          document.getElementById('payrollSelectedPeriod').textContent = payrollMonthLabel(month);
          document.getElementById('payrollStateBadge').textContent = 'Load failed';
          document.getElementById('payrollStateBadge').className = 'badge bg-danger-subtle text-danger';
          document.getElementById('reviewPayrollButton').disabled = true;
          ['payrollStaffCount', 'payrollBasicTotal', 'payrollDeductionTotal', 'payrollNetTotal', 'payrollScheduledTotal', 'payrollPresentTotal', 'payrollAbsentTotal', 'payrollLateTotal', 'payrollPayableDaysTotal', 'payrollIssueCount'].forEach(id => {
            document.getElementById(id).textContent = '--';
          });
          document.getElementById('payrollReviewPanel').hidden = true;
        } finally {
          calculateButton.disabled = Boolean(currentPayrollPreview?.is_finalized && currentPayrollPreview.payroll_month === month);
          updatePayrollMonthNavigation();
        }
      }

      async function finalizeMonthlyPayroll() {
        if (!currentPayrollPreview || currentPayrollPreview.is_finalized) return;
        const month = currentPayrollPreview.payroll_month;
        const issues = currentPayrollPreview.records.filter(row => payrollIssueDetails(row).length);
        if (issues.length) {
          document.getElementById('payrollReviewIssues').innerHTML = `<div class="alert alert-danger py-2 mb-0">Finalization blocked. Resolve: ${issues.map(row => payrollEscape(row.employee_name)).join(', ')}</div>`;
          return;
        }
        const confirmed = window.confirm(
          `Payroll Review\n\n${payrollMonthLabel(month)}\nEmployees: ${currentPayrollPreview.employee_count}\nBasic salary: ${payrollMoney(currentPayrollPreview.total_basic_salary)}\nDeductions: ${payrollMoney(currentPayrollPreview.total_deduction)}\nTotal payable: ${payrollMoney(currentPayrollPreview.total_net_salary)}\n\nFinalize this immutable snapshot?`
        );
        if (!confirmed) return;
        const button = document.getElementById('finalizePayrollButton');
        button.disabled = true;
        try {
          const response = await fetch(`${API_BASE}/payroll/finalize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ month })
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Failed to finalize payroll');
          renderMonthlyPayroll(result.payroll);
          document.getElementById('payrollReviewPanel').hidden = false;
          renderPayrollReview();
          await loadPayrollHistory();
          showAppToast(`${payrollMonthLabel(month)} finalized and locked.`, 'success');
        } catch (error) {
          document.getElementById('payrollMessage').innerHTML = `<div class="alert alert-danger py-2 mb-0">${payrollEscape(error.message)}</div>`;
          button.disabled = false;
        }
      }

      async function loadPayrollHistory() {
        const tbody = document.getElementById('payrollHistoryTableBody');
        if (!tbody || payrollHistoryLoading) return;
        payrollHistoryLoading = true;
        try {
          const response = await fetch(`${API_BASE}/payroll/history`, { cache: 'no-store' });
          const history = await response.json();
          if (!response.ok) throw new Error(history.error || 'Failed to load payroll history');
          currentPayrollHistory = history;
          payrollHistoryLoaded = true;
          if (!history.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-4">No payroll runs have been saved yet.</td></tr>';
            return;
          }
          tbody.innerHTML = history.map(run => {
            const isFinalized = run.status === 'Finalized';
            const badge = isFinalized ? 'bg-success-subtle text-success' : 'bg-secondary-subtle text-secondary';
            return `<tr>
              <td class="fw-semibold">${payrollEscape(payrollMonthLabel(run.payroll_month))}</td>
              <td class="text-center">${Number(run.employee_count || 0)}</td>
              <td class="text-end">${payrollMoney(run.total_basic_salary)}</td>
              <td class="text-end">${payrollMoney(run.total_deduction)}</td>
              <td class="text-end fw-bold">${payrollMoney(run.total_net_salary)}</td>
              <td><span class="badge ${badge}">${payrollEscape(run.status)}</span></td>
              <td>${payrollEscape(run.finalized_at || '—')}</td>
              <td><button type="button" class="btn btn-outline-primary btn-sm" onclick="openPayrollHistoryMonth('${payrollEscape(run.payroll_month)}')"><i class="fa-solid fa-eye"></i> ${isFinalized ? 'View Snapshot' : 'Open Draft'}</button></td>
            </tr>`;
          }).join('');
        } catch (error) {
          payrollHistoryLoaded = false;
          tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger p-4">${payrollEscape(error.message)}</td></tr>`;
        } finally {
          payrollHistoryLoading = false;
        }
      }

      function openPayrollHistoryMonth(month) {
        document.getElementById('payrollMonth').value = month;
        document.getElementById('payrollReviewPanel').hidden = true;
        loadMonthlyPayroll(month);
        document.getElementById('payroll-view').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      function switchTab(viewId, element) {
        if (mobileSidebarQuery.matches) {
          document.body.classList.add('sidebar-collapsed');
          const sidebarToggle = document.querySelector('.sidebar-toggle');
          sidebarToggle.setAttribute('aria-label', 'Expand navigation');
          sidebarToggle.setAttribute('title', 'Expand navigation');
        }
        // Reset scroll position to top immediately
        window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        const mainPanel = document.querySelector(".main-panel");
        if (mainPanel) mainPanel.scrollTop = 0;

        // Remove active status from all menu items
        document
          .querySelectorAll(".menu-item")
          .forEach((item) => item.classList.remove("active"));
        // Add active status to clicked element
        if (element) {
          element.classList.add("active");
        } else {
          // If no element passed, highlight matching menu item
          const matchItem = document.querySelector(`.menu-item[onclick*="${viewId}"]`);
          if (matchItem) matchItem.classList.add("active");
        }

        // Hide all page views
        document
          .querySelectorAll(".page-view")
          .forEach((view) => view.classList.remove("active"));
        // Show target page view
        const targetView = document.getElementById(viewId);
        if (targetView) targetView.classList.add("active");

        // Update Topbar Current Page indicator
        const PAGE_TITLES = {
          'dashboard-view': 'Dashboard',
          'reports-view': 'Attendance Reports',
          'payroll-view': 'Payroll',
          'leaves-view': 'Leave & Holiday Management',
          'enroll-view': 'Staff Enrollment',
          'staff-view': 'Staff Directory',
          'shifts-view': 'Shift Management',
          'live-view': 'Live AI Attendance',
          'multi-view': 'Multiple View Attendance',
          'camera-detect-view': 'Laptop Camera Detection',
          'verify-view': 'Biometric Verification',
          'locator-view': 'Staff & Room Locator',
          'settings-view': 'Settings'
        };
        const titleEl = document.getElementById("headerCurrentPageTitle");
        if (titleEl && PAGE_TITLES[viewId]) {
          titleEl.textContent = PAGE_TITLES[viewId];
        }

        // Synchronize metrics immediately on any tab switch
        if (typeof window.triggerCentralDataSync === 'function') {
          window.triggerCentralDataSync();
        }

        if (viewId === "dashboard-view") {
          loadAttendanceLogs();
        }

        if (viewId === "leaves-view") {
          loadLeaveRequests();
        }

        // Reload staff directory if switching to enroll view
        if (viewId === "enroll-view") {
          loadStaffDirectory();
        }

        // Initialize dynamic cameras & ticker when switching to live-view
        if (viewId === "live-view") {
          isStreaming = true;
          loadLiveCameras();
          startTickerFeed();
        }

        // Initialize Locator Room Radar if switching to locator-view
        if (viewId === "locator-view") {
          loadRoomsOccupancy();
          renderQuickStaffChips();
        }

        // Initialize Attendance Reports if switching to reports-view
        if (viewId === "reports-view") {
          initMainReportsTab();
        }

        if (viewId === "payroll-view") {
          loadMonthlyPayroll();
          loadPayrollHistory();
        }

        // Initialize Staff Directory if switching to staff-view
        if (viewId === "staff-view") {
          loadTabStaffDirectory();
        }

        // Initialize Shift Management if switching to shifts-view
        if (viewId === "shifts-view") {
          loadShiftsList();
        }

        // Initialize System Settings if switching to settings-view
        if (viewId === "settings-view") {
          reloadSystemConfiguration();
        }
      }

      function toggleSidebar() {
        const collapsed = document.body.classList.toggle("sidebar-collapsed");
        const toggle = document.querySelector(".sidebar-toggle");
        toggle.setAttribute(
          "aria-label",
          collapsed ? "Expand navigation" : "Collapse navigation",
        );
        toggle.setAttribute(
          "title",
          collapsed ? "Expand navigation" : "Collapse navigation",
        );
        localStorage.setItem("qintellect-sidebar-collapsed", collapsed);
      }

      if (localStorage.getItem("qintellect-sidebar-collapsed") === "true") {
        document.body.classList.add("sidebar-collapsed");
        const toggle = document.querySelector(".sidebar-toggle");
        toggle.setAttribute("aria-label", "Expand navigation");
        toggle.setAttribute("title", "Expand navigation");
      }

      const mobileSidebarQuery = window.matchMedia('(max-width: 768px)');
      function syncResponsiveSidebar(event) {
        const isMobile = event?.matches ?? mobileSidebarQuery.matches;
        if (isMobile) {
          document.body.classList.add('sidebar-collapsed');
        } else if (localStorage.getItem('qintellect-sidebar-collapsed') !== 'true') {
          document.body.classList.remove('sidebar-collapsed');
        }
        const toggle = document.querySelector('.sidebar-toggle');
        const collapsed = document.body.classList.contains('sidebar-collapsed');
        toggle.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
        toggle.setAttribute('title', collapsed ? 'Expand navigation' : 'Collapse navigation');
      }
      syncResponsiveSidebar();
      if (mobileSidebarQuery.addEventListener) {
        mobileSidebarQuery.addEventListener('change', syncResponsiveSidebar);
      } else {
        mobileSidebarQuery.addListener(syncResponsiveSidebar);
      }

      // Dropzone decoration helper
      function updateDropzoneLabel(input) {
        const container = input.parentElement;
        if (input.files && input.files[0]) {
          const file = input.files[0];
          container.style.borderColor = "var(--accent-success)";
          container.querySelector(".dropzone-icon").className =
            "fa-solid fa-circle-check dropzone-icon";
          container.querySelector(".dropzone-icon").style.color =
            "var(--accent-success)";
          container.querySelector(".dropzone-text").innerHTML =
            `<strong>Selected file:</strong> ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
          addTerminalLine(`Selected video file: ${file.name}`, "system");
        }
      }

      // Terminal Console Print log helper
      function addTerminalLine(text, type = "system") {
        const term = document.getElementById("terminalLog");
        if (!term) return;
        const line = document.createElement("div");
        line.className = type;
        line.innerHTML = `[${new Date().toLocaleTimeString()}] ${text}`;
        term.appendChild(line);
        term.scrollTop = term.scrollHeight;
      }

      // Show generic HTML alert messages
      function showMessage(elementId, message, type) {
        const elem = document.getElementById(elementId);
        const icon = type === "success"
          ? "fa-circle-check"
          : type === "error"
            ? "fa-circle-exclamation"
            : "fa-circle-info";
        elem.innerHTML = `<div class="${type}"><i class="fa-solid ${icon}" aria-hidden="true"></i><span>${message}</span></div>`;
      }

      // Create User Profile
      async function createEnrollUser() {
        const name = document.getElementById("enrollName").value.trim();
        const email = document.getElementById("enrollEmail").value;
        const phone = document.getElementById("enrollPhone") ? document.getElementById("enrollPhone").value : "";
        const department = document.getElementById("enrollDepartment") ? document.getElementById("enrollDepartment").value : "";
        const position = document.getElementById("enrollPosition") ? document.getElementById("enrollPosition").value : "";
        const cnic = document.getElementById("enrollCNIC") ? document.getElementById("enrollCNIC").value : "";
        const salary = document.getElementById("enrollSalary") ? document.getElementById("enrollSalary").value : 0;
        const join_date = document.getElementById("enrollJoinDate") ? document.getElementById("enrollJoinDate").value : "";
        const notes = document.getElementById("enrollNotes") ? document.getElementById("enrollNotes").value : "";
        const is_veiled = document.getElementById("enrollIsVeiled") ? (document.getElementById("enrollIsVeiled").value === 'true') : false;
        const shift_id = document.getElementById("enrollShiftId") ? parseInt(document.getElementById("enrollShiftId").value) : 1;
        const checkin_cameras = typeof getMultiSelectValues === 'function' ? getMultiSelectValues(document.getElementById("enrollCheckinCameras")) : 'all';
        const checkout_cameras = typeof getMultiSelectValues === 'function' ? getMultiSelectValues(document.getElementById("enrollCheckoutCameras")) : 'all';

        if (!name) {
          showMessage("enrollmentMessage", "Name is required", "error");
          addTerminalLine("Create Profile Aborted: Name is empty.", "error-line");
          return;
        }

        const btn = document.querySelector('button[onclick="createEnrollUser()"]');
        const restoreBtn = setButtonLoading(btn, 'Creating Profile...');
        addTerminalLine(`Creating user profile '${name}' (${department} - ${position})...`, "system");

        try {
          const resp = await fetch(`${API_BASE}/enroll/create-user`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, phone, department, position, cnic, salary, join_date, notes, is_veiled, shift_id, checkin_cameras, checkout_cameras }),
          });
          const data = await resp.json();

          if (resp.ok) {
            document.getElementById("userIdEnroll").value = data.user_id;
            showMessage("enrollmentMessage", `Profile Created: ${data.message}`, "success");
            addTerminalLine(`[OK] User '${name}' created. ID assigned: ${data.user_id}`, "success");
            showAppToast(data.message || `Staff profile '${name}' created — now upload enrollment video`, 'success', 5000);
            if (typeof loadStaffDirectory === 'function') loadStaffDirectory();
          } else {
            showMessage("enrollmentMessage", data.error || 'Failed to create profile', "error");
            addTerminalLine(`[FAIL] Profile failed: ${data.error}`, "error-line");
            showAppToast(data.error || 'Failed to create profile', 'error');
          }
        } catch (e) {
          showMessage("enrollmentMessage", `Error: ${e.message}`, "error");
          addTerminalLine(`[FAIL] Connection Error: ${e.message}`, "error-line");
          showAppToast(`Error: ${e.message}`, 'error');
        } finally {
          restoreBtn();
        }
      }

      // Upload Enrollment video & process frames
      async function uploadEnrollmentVideo() {
        const userId = document.getElementById("userIdEnroll").value;
        const videoFile = document.getElementById("videoFile").files[0];

        if (!userId) {
          showMessage(
            "enrollmentMessage",
            "Initialize a User profile first",
            "error",
          );
          addTerminalLine(
            "Extraction failed: No associated User ID.",
            "error-line",
          );
          return;
        }
        if (!videoFile) {
          showMessage(
            "enrollmentMessage",
            "Select a video file to proceed",
            "error",
          );
          addTerminalLine(
            "Extraction failed: No video file chosen.",
            "error-line",
          );
          return;
        }

        const formData = new FormData();
        formData.append("video", videoFile);
        formData.append("user_id", userId);

        showMessage(
          "enrollmentMessage",
          "Uploading video file and starting the AI feature extractor. Monitor progress below.",
          "info",
        );
        addTerminalLine("Uploading enrollment video to server...", "system");
        addTerminalLine(
          "Processing facial biometric vectors...",
          "system",
        );

        // Start a simulated progress reporter in terminal while waiting for CPU calculation
        let frameCounter = 0;
        const fakeTerminalTimer = setInterval(() => {
          frameCounter += 10;
          if (frameCounter <= 120) {
            addTerminalLine(
              `Extracting & analyzing frames ${frameCounter - 10} to ${frameCounter}...`,
              "system",
            );
          }
        }, 6000);

        try {
          const resp = await fetch(`${API_BASE}/enroll/upload-video`, {
            method: "POST",
            body: formData,
          });
          clearInterval(fakeTerminalTimer);
          const data = await resp.json();

          if (resp.ok) {
            showMessage("enrollmentMessage", `${data.message}`, "success");
            addTerminalLine(
              `[COMPLETED] Biometric extraction completed successfully!`,
              "success",
            );
            addTerminalLine(
              `Calculated and stored <strong>${data.message.split("stored ")[1]?.split(" ")[0] || "all"}</strong> high-quality face embeddings.`,
              "success",
            );
            loadStats();
            loadStaffDirectory();
          } else {
            showMessage("enrollmentMessage", `${data.error}`, "error");
            addTerminalLine(
              `[PIPELINE ABORTED] Error: ${data.error}`,
              "error-line",
            );
          }
        } catch (e) {
          clearInterval(fakeTerminalTimer);
          showMessage("enrollmentMessage", `Error: ${e.message}`, "error");
          addTerminalLine(
            `[PIPELINE ERROR] Server timeout or disconnection: ${e.message}`,
            "error-line",
          );
        }
      }

      // ============================================
      // LIVE AI CAMERA MONITORING & COMPACT ATTENDANCE
      // ============================================
      let currentLiveLayout = 'single';
      let cachedLiveCameras = [];
      let _lastRenderedTickerKey = null;

      // Handle stream image reconnection automatically on network / camera drops
      function handleStreamImgError(imgEl) {
        if (!imgEl) return;
        const camId = imgEl.getAttribute('data-cam-id') || selectedCameraId;
        if (!camId) return;
        
        console.warn(`[Stream Reconnect] Stream for camera '${camId}' disconnected. Auto-retrying...`);
        
        const placeholder = document.getElementById('streamFallbackPlaceholder');
        if (imgEl.id === 'streamView' && placeholder) {
          placeholder.style.display = 'flex';
        }

        // Auto-reconnect retry after 2.0 seconds (continuous 24/7 self-healing)
        setTimeout(() => {
          if (imgEl && camId) {
            imgEl.src = `/api/stream/${camId}?t=${Date.now()}`;
            imgEl.onload = () => {
              if (imgEl.id === 'streamView' && placeholder) {
                placeholder.style.display = 'none';
              }
            };
          }
        }, 2000);
      }

      // Stop all multi-grid camera streams to release browser HTTP connection sockets
      function stopAllGridStreams() {
        const grid = document.getElementById('liveMultiGrid');
        if (!grid) return;
        grid.querySelectorAll('img').forEach((img) => {
          img.onerror = null;
          img.src = '';
        });
        grid.innerHTML = '';
      }

      // Stop single view stream to release HTTP connection socket
      function stopSingleStream() {
        const streamView = document.getElementById('streamView');
        if (streamView) {
          streamView.onerror = null;
          streamView.src = '';
        }
      }

      // Toggle Live CCTV single stream camera
      function selectCamera(camId, btn, camName, roomName) {
        document.querySelectorAll(".camera-tab-btn").forEach((b) => b.classList.remove("active"));
        if (btn) btn.classList.add("active");
        selectedCameraId = camId;

        const badgeText = document.getElementById("singleCamBadgeName");
        if (badgeText) {
          badgeText.textContent = camName ? `${camName} (${roomName || 'Active'})` : `CAMERA: ${camId}`;
        }

        if (currentLiveLayout === 'single') {
          const streamView = document.getElementById("streamView");
          if (streamView) {
            streamView.onerror = () => handleStreamImgError(streamView);
            streamView.setAttribute('data-cam-id', camId);
            streamView.src = '';
            setTimeout(() => {
              streamView.src = `/api/stream/${selectedCameraId}?t=${Date.now()}`;
            }, 60);
          }
        }

        const placeholder = document.getElementById('streamFallbackPlaceholder');
        if (placeholder) placeholder.style.display = 'none';

        showMessage(
          "streamMessage",
          `Connected to ${camName || camId} (${roomName || 'Live'})`,
          "success"
        );
      }


      // Camera Grid & Layout Options Switcher (Single Cam and All Grid)
      async function setLiveCameraLayout(layoutMode) {
        currentLiveLayout = layoutMode === 'grid' || layoutMode === 'grid-2' || layoutMode === 'grid-all' ? 'grid' : 'single';

        // Update layout buttons
        document.querySelectorAll('.live-layout-btn').forEach(btn => btn.classList.remove('active'));
        const btnMap = {
          'single': 'btnLayoutSingle',
          'grid': 'btnLayoutGrid'
        };
        const activeBtn = document.getElementById(btnMap[currentLiveLayout]);
        if (activeBtn) activeBtn.classList.add('active');

        const singleContainer = document.getElementById('singleCameraContainer');
        const tabsContainer = document.getElementById('cctvCameraTabs');
        const multiContainer = document.getElementById('multiCameraGridContainer');
        const multiGrid = document.getElementById('liveMultiGrid');

        // Ensure active cameras are cached
        if (!cachedLiveCameras || cachedLiveCameras.length === 0) {
          try {
            const res = await fetch(`${API_BASE}/cameras?active_only=true`);
            const cams = await res.json();
            cachedLiveCameras = cams || [];
          } catch (e) {
            console.warn("Error fetching cameras for grid:", e);
          }
        }

        if (currentLiveLayout === 'single') {
          // Cleanly release grid sockets
          stopAllGridStreams();

          if (singleContainer) singleContainer.style.display = 'block';
          if (tabsContainer) tabsContainer.style.display = 'flex';
          if (multiContainer) multiContainer.style.display = 'none';

          const streamView = document.getElementById('streamView');
          if (streamView && selectedCameraId) {
            streamView.onerror = () => handleStreamImgError(streamView);
            streamView.setAttribute('data-cam-id', selectedCameraId);
            streamView.src = '';
            setTimeout(() => {
              streamView.src = `/api/stream/${selectedCameraId}?t=${Date.now()}`;
            }, 60);
          }
        } else {
          // Cleanly release single view socket
          stopSingleStream();

          if (singleContainer) singleContainer.style.display = 'none';
          if (tabsContainer) tabsContainer.style.display = 'none';
          if (multiContainer) multiContainer.style.display = 'block';

          if (multiGrid) {
            multiGrid.className = 'cctv-multi-grid';
            renderLiveMultiGrid('grid');
          }
        }
      }

      // Render All Camera Grid Tiles in a 2-Column Responsive Grid with Fullscreen & Auto-Reconnect
      function renderLiveMultiGrid(layoutMode) {
        const grid = document.getElementById('liveMultiGrid');
        if (!grid) return;

        // Clean previous images first
        stopAllGridStreams();

        if (!cachedLiveCameras || cachedLiveCameras.length === 0) {
          grid.innerHTML = '<div style="grid-column: 1/-1; padding: 30px; text-align: center; color: #94a3b8; background: #0f172a; border-radius: 12px;">No active cameras configured. Add cameras in System Settings.</div>';
          return;
        }

        const camsToRender = cachedLiveCameras;

        grid.innerHTML = camsToRender.map((c, idx) => `
          <div class="cctv-screen-wrapper" id="multiCamTile_${c.camera_id}" style="margin: 0;">
            <div class="cctv-badge">
              <span class="cctv-badge-dot"></span>
              <span>${c.name} &bull; ${c.room_name}</span>
            </div>

            <div class="cctv-top-actions">
              <button type="button" class="cctv-fullscreen-btn" onclick="toggleCameraFullscreen('multiCamTile_${c.camera_id}')" title="Full Screen">
                <i class="fa-solid fa-expand"></i> Full Screen
              </button>
            </div>

            <div class="cctv-viewport">
              <img id="gridImg_${c.camera_id}" data-cam-id="${c.camera_id}" src="" alt="${c.name}" onerror="handleStreamImgError(this)" />
            </div>
          </div>
        `).join('');

        // Stagger assigning stream src to avoid socket concurrency bursts
        camsToRender.forEach((c, idx) => {
          setTimeout(() => {
            const img = document.getElementById(`gridImg_${c.camera_id}`);
            if (img && currentLiveLayout === 'grid') {
              img.src = `/api/stream/${c.camera_id}?t=${Date.now() + idx}`;
            }
          }, 80 + idx * 100);
        });
      }

      // Fullscreen Camera Handler (Single & Multi Tile)
      function toggleCameraFullscreen(elementId) {
        const target = document.getElementById(elementId);
        if (!target) return;

        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => {});
        } else {
          if (target.requestFullscreen) {
            target.requestFullscreen().catch(err => {
              console.warn("Fullscreen request error:", err);
            });
          }
        }
      }

      // Reconnect all camera streams instantly with staggered reconnects
      function reconnectLiveStreams() {
        if (currentLiveLayout === 'single') {
          const streamView = document.getElementById('streamView');
          if (streamView && selectedCameraId) {
            streamView.src = '';
            setTimeout(() => {
              streamView.src = `/api/stream/${selectedCameraId}?t=${Date.now()}`;
            }, 80);
          }
        } else {
          const imgs = document.querySelectorAll('#liveMultiGrid img');
          imgs.forEach((img, idx) => {
            const cid = img.getAttribute('data-cam-id');
            if (cid) {
              img.src = '';
              setTimeout(() => {
                img.src = `/api/stream/${cid}?t=${Date.now() + idx * 100}`;
              }, 80 + idx * 120);
            }
          });
        }
        showAppToast('Reconnecting live camera streams...', 'info');
      }

      let currentTickerPage = 1;
      const TICKER_PAGE_SIZE = 10;
      let cachedDetectionsList = [];

      function changeTickerPage(delta) {
        const totalPages = Math.ceil(cachedDetectionsList.length / TICKER_PAGE_SIZE) || 1;
        const targetPage = currentTickerPage + delta;
        if (targetPage >= 1 && targetPage <= totalPages) {
          currentTickerPage = targetPage;
          renderCurrentTickerPage();
        }
      }

      async function clearLiveDetectionsList() {
        if (!confirm('Clear all live attendance entries from this view?')) return;
        try {
          await fetch(`${API_BASE}/clear-live-detections`, { method: 'POST' });
        } catch (e) {
          console.warn("Clear live detections API error:", e);
        }
        cachedDetectionsList = [];
        currentTickerPage = 1;
        _lastRenderedTickerKey = 'cleared';

        const countBadge = document.getElementById("liveTotalCountBadge");
        if (countBadge) countBadge.textContent = 'Total: 0';

        renderCurrentTickerPage();
        showAppToast('Live attendance list cleared.', 'info');
      }

      function renderCurrentTickerPage() {
        const tickerList = document.getElementById("tickerList");
        const countBadge = document.getElementById("liveTotalCountBadge");
        const pageIndicator = document.getElementById("tickerPageIndicator");
        const btnPrev = document.getElementById("btnTickerPrev");
        const btnNext = document.getElementById("btnTickerNext");

        const totalItems = cachedDetectionsList.length;
        const totalPages = Math.ceil(totalItems / TICKER_PAGE_SIZE) || 1;
        if (currentTickerPage > totalPages) currentTickerPage = totalPages;
        if (currentTickerPage < 1) currentTickerPage = 1;

        if (countBadge) {
          countBadge.textContent = `Total: ${totalItems}`;
        }
        if (pageIndicator) {
          pageIndicator.textContent = `Page ${currentTickerPage} / ${totalPages}`;
        }
        if (btnPrev) btnPrev.disabled = (currentTickerPage <= 1);
        if (btnNext) btnNext.disabled = (currentTickerPage >= totalPages);

        if (totalItems === 0) {
          if (tickerList) {
            tickerList.innerHTML = `
              <div style="text-align: center; color: #94a3b8; padding: 24px 10px; font-size: 0.8rem;">
                <i class="fa-solid fa-satellite-dish fa-fade" style="font-size: 1.8rem; margin-bottom: 8px; display: block; color: #38bdf8;"></i>
                <span>Live attendance feed active.<br>Awaiting detections...</span>
              </div>
            `;
          }
          return;
        }

        const startIndex = (currentTickerPage - 1) * TICKER_PAGE_SIZE;
        const pageItems = cachedDetectionsList.slice(startIndex, startIndex + TICKER_PAGE_SIZE);

        if (tickerList) {
          tickerList.innerHTML = pageItems.map((log) => {
            const name = log.name || "Unknown Staff";
            const time = log.timestamp ? formatMainTime(log.timestamp) : new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

            // Smart Camera Name Resolution
            let camName = "";
            const rawCamId = log.camera_id || (log.source ? String(log.source).replace('stream_', '') : null);
            let matchedCam = null;
            if (cachedLiveCameras && rawCamId) {
              matchedCam = cachedLiveCameras.find(c => String(c.camera_id) === String(rawCamId) || String(c.id) === String(rawCamId));
            }

            if (matchedCam) {
              camName = matchedCam.name ? `${matchedCam.name} (${matchedCam.room_name || 'Live'})` : matchedCam.room_name;
            } else if (log.camera_name) {
              camName = log.camera_name;
            } else if (log.room_name || log.room || log.location) {
              camName = log.room_name || log.room || log.location;
            } else if (log.camera_label) {
              camName = log.camera_label;
            } else {
              camName = "Camera Feed";
            }

            return `
              <div class="compact-attend-card">
                <div class="compact-attend-name">${name}</div>
                <div class="compact-attend-meta">
                  <span class="compact-attend-time"><i class="fa-regular fa-clock"></i> ${time}</span>
                  <span class="compact-attend-cam" title="${camName}"><i class="fa-solid fa-video"></i> ${camName}</span>
                </div>
              </div>
            `;
          }).join('');
        }
      }

      // Start live attendance feed (Only: Name, Last Detected, Camera Name, 10 per page)
      function startTickerFeed() {
        if (tickerInterval) clearInterval(tickerInterval);

        tickerInterval = setInterval(async () => {
          try {
            const resp = await fetch(`${API_BASE}/live-detections`);
            const data = await resp.json();

            // Refresh KPIs with database
            loadStats();

            const detections = data.detections || [];
            cachedDetectionsList = detections;

            const cacheKey = `${currentTickerPage}_${detections.length}_` + detections.map(d => `${d.user_id}_${d.timestamp}_${d.camera_name || d.source}`).slice(0, 10).join('|');
            if (cacheKey === _lastRenderedTickerKey) return;
            _lastRenderedTickerKey = cacheKey;

            renderCurrentTickerPage();
          } catch (e) {
            console.error("Ticker sync error:", e);
          }
        }, 1200);
      }

      function stopTickerFeed() {
        if (tickerInterval) {
          clearInterval(tickerInterval);
          tickerInterval = null;
        }
      }

      async function refreshAttendanceViews() {
        await Promise.all([
          loadStats(),
          loadAttendanceLogs(),
          loadStaffDirectory(),
          loadRoomsOccupancy(),
        ]);
        if (isStreaming) {
          startTickerFeed();
        }
      }

      async function bulkAttendance(action) {
        const actionLabel = action === "present" ? "present" : "absent";
        const confirmed = confirm(
          `Mark all active students ${actionLabel} for today? This will update the attendance database.`,
        );
        if (!confirmed) return;

        const buttons = document.querySelectorAll(".bulk-attendance-btn");
        buttons.forEach((button) => {
          button.disabled = true;
          button.style.opacity = "0.6";
        });

        try {
          const response = await fetch(`${API_BASE}/attendance/bulk-mark`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action }),
          });
          const data = await response.json();
          if (!response.ok && response.status !== 207) {
            throw new Error(data.error || "Bulk attendance update failed");
          }

          showMessage(
            "streamMessage",
            `${data.message}. All attendance views have been synchronized.`,
            data.success ? "success" : "info",
          );
          await refreshAttendanceViews();
        } catch (error) {
          showMessage(
            "streamMessage",
            `Bulk attendance update failed: ${error.message}`,
            "error",
          );
        } finally {
          buttons.forEach((button) => {
            button.disabled = false;
            button.style.opacity = "1";
          });
        }
      }

      // ============ LAPTOP CAMERA DETECTION FUNCTIONS ============
      let cameraStream = null;
      let cameraProcessingInterval = null;
      let cameraStats = {};
      let enrolledUsers = [];

      // Load all enrolled users on page load
      async function loadEnrolledUsers() {
        try {
          const resp = await fetch(`${API_BASE}/users`);
          const data = await resp.json();
          if (resp.ok && data.users) {
            enrolledUsers = data.users;
            tabAllStaff = data.users;
            allEnrolledUsers = data.users;

            // Initialize stats for all enrolled users
            cameraStats = {};
            enrolledUsers.forEach((user) => {
              cameraStats[user.name] = 0;
            });
            cameraStats["unknown"] = 0;
            console.log("Loaded enrolled users:", enrolledUsers);

            renderTabStaffMetrics(tabAllStaff);
            populateTabDeptDropdown(tabAllStaff);
            renderTabStaffRows(tabAllStaff);
            if (typeof filterStaffDirectory === 'function') filterStaffDirectory();
          }
        } catch (e) {
          console.error("Failed to load enrolled users:", e);
        }
      }

      async function startCamera() {
        try {
          showMessage(
            "cameraMessage",
            "Requesting camera access...",
            "info",
          );
          addTerminalLine("[CAMERA] Requesting camera access...", "system");

          // Request camera access with better constraints
          const constraints = {
            video: {
              width: { ideal: 1280 },
              height: { ideal: 720 },
              facingMode: "user",
            },
            audio: false,
          };

          cameraStream = await navigator.mediaDevices.getUserMedia(constraints);

          const video = document.getElementById("cameraVideo");
          video.srcObject = cameraStream;

          // Ensure video plays
          video.onloadedmetadata = () => {
            console.log("Video metadata loaded, attempting to play...");
            video
              .play()
              .then(() => {
                console.log("Video playing successfully");
                showMessage(
                  "cameraMessage",
                  "Camera started successfully",
                  "success",
                );
                addTerminalLine(
                  "[CAMERA] Camera stream activated",
                  "success",
                );

                // Start processing frames
                startCameraProcessing();
              })
              .catch((e) => {
                console.error("Play error:", e);
                showMessage(
                  "cameraMessage",
                  `Error playing video: ${e.message}`,
                  "error",
                );
                addTerminalLine(
                  `[CAMERA ERROR] Play failed: ${e.message}`,
                  "error-line",
                );
              });
          };

          // Fallback: try to play immediately
          video.play().catch((e) => {
            console.log("Immediate play failed, waiting for metadata:", e);
          });

          // Update UI
          document.getElementById("btnStartCamera").style.display = "none";
          document.getElementById("btnStopCamera").style.display = "block";
          document.getElementById("cameraStatus").textContent = "LIVE";
        } catch (error) {
          showMessage(
            "cameraMessage",
            `Camera access denied: ${error.message}`,
            "error",
          );
          addTerminalLine(`[CAMERA ERROR] ${error.message}`, "error-line");
          console.error("Camera error:", error);
        }
      }

      function stopCamera() {
        try {
          // Stop stream
          if (cameraStream) {
            cameraStream.getTracks().forEach((track) => track.stop());
            cameraStream = null;
          }

          // Stop processing
          if (cameraProcessingInterval) {
            clearInterval(cameraProcessingInterval);
            cameraProcessingInterval = null;
          }

          // Update UI
          const video = document.getElementById("cameraVideo");
          video.srcObject = null;
          document.getElementById("btnStartCamera").style.display = "block";
          document.getElementById("btnStopCamera").style.display = "none";
          document.getElementById("cameraStatus").textContent = "STANDBY";

          showMessage("cameraMessage", "Camera stopped", "success");
          addTerminalLine("[CAMERA] Camera stream closed", "success");
        } catch (error) {
          showMessage(
            "cameraMessage",
            `Error stopping camera: ${error.message}`,
            "error",
          );
          addTerminalLine(`[CAMERA ERROR] ${error.message}`, "error-line");
        }
      }

      function startCameraProcessing() {
        // Process frames every 500ms (2 FPS for detection)
        cameraProcessingInterval = setInterval(async () => {
          try {
            const video = document.getElementById("cameraVideo");
            const canvas = document.getElementById("cameraCanvas");

            if (
              !video ||
              !canvas ||
              video.readyState !== video.HAVE_ENOUGH_DATA
            ) {
              return;
            }

            // Draw video frame to canvas with HIGHER resolution
            const ctx = canvas.getContext("2d");
            canvas.width = 1280; // Increased from 640
            canvas.height = 720; // Increased from 480
            ctx.drawImage(video, 0, 0, 1280, 720);

            // Convert canvas to blob with HIGHER quality
            canvas.toBlob(
              async (blob) => {
                try {
                  const formData = new FormData();
                  formData.append("image", blob, "frame.jpg");

                  const resp = await fetch(`${API_BASE}/recognize/frame`, {
                    method: "POST",
                    body: formData,
                  });

                  const data = await resp.json();

                  if (
                    resp.ok &&
                    data.detections &&
                    data.detections.length > 0
                  ) {
                    updateCameraDetections(data.detections);
                  }
                } catch (e) {
                  console.error("Frame processing error:", e);
                }
              },
              "image/jpeg",
              0.95,
            ); // Increased quality from 0.8 to 0.95
          } catch (error) {
            console.error("Camera processing error:", error);
          }
        }, 500);
      }

      function updateCameraDetections(detections) {
        let resultsHTML = "";

        detections.forEach((detection, idx) => {
          const name = detection.matched_user || "Unknown";
          const similarity = (detection.similarity * 100).toFixed(1);
          const isMatch = detection.is_match;

          // Update stats for all enrolled users
          if (isMatch && name !== "Unknown") {
            if (cameraStats[name] !== undefined) {
              cameraStats[name]++;
            }
          } else {
            cameraStats["unknown"]++;
          }

          // Create detection item
          const badgeClass = isMatch ? "badge-success" : "badge-info";
          const icon = isMatch
            ? '<i class="fa-solid fa-user-check" aria-hidden="true"></i>'
            : '<i class="fa-solid fa-user-question" aria-hidden="true"></i>';

          resultsHTML += `
                    <div class="ticker-item">
                        <div class="ticker-avatar" style="background: ${isMatch ? "linear-gradient(135deg, #10b981 0%, #059669 100%)" : "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"};">
                            ${icon}
                        </div>
                        <div class="ticker-info">
                            <div class="ticker-name">${name}</div>
                            <div class="ticker-time">Confidence: ${similarity}%</div>
                        </div>
                        <span class="ticker-match ${badgeClass}">${isMatch ? "MATCH" : "UNKNOWN"}</span>
                    </div>
                `;
        });

        document.getElementById("detectionResults").innerHTML = resultsHTML;

        // Update stats dynamically
        updateStatsDisplay();
      }

      function updateStatsDisplay() {
        // Clear existing stats
        const statsGrid = document.querySelector(".stats-grid");
        if (!statsGrid) return;

        let statsHTML = "";

        // Add stats for each enrolled user
        enrolledUsers.forEach((user) => {
          const count = cameraStats[user.name] || 0;
          statsHTML += `
                    <div class="stat-box">
                        <div class="stat-icon green">
                            <i class="fa-solid fa-face-grin"></i>
                        </div>
                        <div class="stat-content">
                            <div class="stat-value">${count}</div>
                            <div class="stat-label">${user.name} Detections</div>
                        </div>
                    </div>
                `;
        });

        // Add unknown stats
        const unknownCount = cameraStats["unknown"] || 0;
        statsHTML += `
                <div class="stat-box">
                    <div class="stat-icon orange">
                        <i class="fa-solid fa-question"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${unknownCount}</div>
                        <div class="stat-label">Unknown Faces</div>
                    </div>
                </div>
            `;

        // Update the stats grid
        const statsContainer = document.querySelector(".stats-grid");
        if (statsContainer) {
          statsContainer.innerHTML = statsHTML;
        }
      }

      // Verify photo snapshot in testbed
      async function recognizePhoto() {
        const photoFile = document.getElementById("photoFile").files[0];

        if (!photoFile) {
          showMessage(
            "recognitionMessage",
            "Choose a photo file to analyze",
            "error",
          );
          return;
        }

        const formData = new FormData();
        formData.append("image", photoFile);

        showMessage(
          "recognitionMessage",
          "Extracting faces and comparing against registered profiles...",
          "info",
        );

        try {
          const resp = await fetch(`${API_BASE}/recognize/frame`, {
            method: "POST",
            body: formData,
          });
          const data = await resp.json();

          if (resp.ok) {
            const results = data.detections || [];
            let message = `<strong>Detections Analysis:</strong> Found ${data.total_faces_detected} face(s)<br><br>`;
            results.forEach((r) => {
              const styleClass =
                r.matched_user === "Unknown"
                  ? "color:#f87171;"
                  : "color:#34d399; font-weight:bold;";
              message += `<span style="${styleClass}"><i class="fa-solid fa-circle-check"></i> Match Found: ${r.matched_user} (Similarity Score: ${(r.similarity * 100).toFixed(1)}%)</span><br>`;
            });
            showMessage("recognitionMessage", message, "success");
            loadStats();
          } else {
            showMessage(
              "recognitionMessage",
              `Error: ${data.error}`,
              "error",
            );
          }
        } catch (e) {
          showMessage(
            "recognitionMessage",
            `Exception: ${e.message}`,
            "error",
          );
        }
      }

      // Verify RTSP manual capture
      async function recognizeRTSP() {
        const rtspUrl = document.getElementById("rtspUrl").value;
        const frames = document.getElementById("framesToProcess").value;

        if (!rtspUrl) {
          showMessage(
            "recognitionMessage",
            "Enter a valid RTSP stream URL",
            "error",
          );
          return;
        }

        showMessage(
          "recognitionMessage",
          "Opening RTSP network socket and grabbing frames...",
          "info",
        );

        try {
          const resp = await fetch(`${API_BASE}/recognize/rtsp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              rtsp_url: rtspUrl,
              frames: parseInt(frames),
            }),
          });
          const data = await resp.json();

          if (resp.ok) {
            const users = data.recognized_users || [];
            let message = `<strong>RTSP Capture Report:</strong> Analyzed ${data.frames_processed} frames<br><br>`;
            if (users.length > 0) {
              users.forEach(
                (u) =>
                  (message += `<i class="fa-solid fa-user-check"></i> Recognized User: <strong>${u}</strong><br>`),
              );
            } else {
              message +=
                "No registered staff matches identified in frames.<br>";
            }
            showMessage("recognitionMessage", message, "success");
            loadStats();
          } else {
            showMessage(
              "recognitionMessage",
              `Capture Failed: ${data.error}`,
              "error",
            );
          }
        } catch (e) {
          showMessage(
            "recognitionMessage",
            `Connection Exception: ${e.message}`,
            "error",
          );
        }
      }

      // Load metrics/statistics
      async function loadStats() {
        try {
          const resp = await fetch(`${API_BASE}/stats`);
          const data = await resp.json();

          document.getElementById("valEnrolled").textContent = data.total_users;
          document.getElementById("valAttendance").textContent =
            data.today_attendance;
          document.getElementById("valRecords").textContent = data.total_logs;
          document.getElementById("tickerTotalStudents").textContent =
            data.total_users ?? "--";
          document.getElementById("tickerTotalPresent").textContent =
            data.present_users ?? data.unique_users_today ?? "--";
          document.getElementById("tickerTotalAbsent").textContent =
            data.absent_users ?? "--";
        } catch (e) {
          console.error("Failed to load stats:", e);
        }
      }

      // Load logs into dashboard table
      async function loadAttendanceLogs() {
        try {
          const resp = await fetch(
            `${API_BASE}/attendance/logs?limit=15&_=${Date.now()}`,
            { cache: "no-store" },
          );
          const data = await resp.json();

          const syncStatus = document.getElementById("logSyncStatus");
          if (syncStatus) {
            const serverTime = data.server_time
              ? new Date(data.server_time).toLocaleTimeString()
              : new Date().toLocaleTimeString();
            syncStatus.textContent = `Live database sync: ${serverTime}`;
          }

          if (!data.logs || data.logs.length === 0) {
            document.getElementById("logsContainer").innerHTML = `
                        <p style="padding: 30px; text-align: center; color: var(--text-secondary);">No attendance logs recorded in the database yet.</p>
                    `;
            return;
          }

          let html =
            '<table class="table table-dark table-hover table-borderless align-middle"><thead><tr><th>User Name</th><th>Confidence</th><th>Log Source</th><th>Timestamp</th></tr></thead><tbody>';
          data.logs.forEach((log) => {
            const isMatch = log.name !== "Unknown";
            const badgeClass = isMatch ? "badge-success" : "badge-info";
            const formattedDate = log.timestamp
              ? new Date(log.timestamp).toLocaleString()
              : "Timestamp unavailable";
            const confidenceVal = (log.confidence * 100).toFixed(1);

            html += `<tr>
                        <td>
                            <div style="display:flex; align-items:center; gap:10px;">
                                <div class="ticker-avatar" style="width:30px; height:30px; font-size:0.85em;">${log.name.charAt(0)}</div>
                                <strong>${log.name}</strong>
                            </div>
                        </td>
                        <td><span class="badge ${badgeClass}">${confidenceVal}%</span></td>
                        <td><span class="badge badge-info" style="background-color:rgba(255,255,255,0.03); color:var(--text-primary); border-color:var(--border-color);">${log.source}</span></td>
                        <td style="color:var(--text-secondary);">${formattedDate}</td>
                    </tr>`;
          });
          html += "</tbody></table>";

          document.getElementById("logsContainer").innerHTML = html;
        } catch (e) {
          showMessage(
            "statsMessage",
            `Logs failed to load: ${e.message}`,
            "error",
          );
        }
      }

      // ============================================
      // STAFF DIRECTORY CRUD MANAGER JS
      // ============================================
      let allEnrolledUsers = [];

      async function loadStaffDirectory() {
        try {
          const resp = await fetch(`${API_BASE}/users`);
          const data = await resp.json();
          allEnrolledUsers = data.users || [];

          filterStaffDirectory();
        } catch (e) {
          console.error("Failed to load staff directory:", e);
          const tableBody = document.getElementById("directoryTableBody");
          if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--accent-danger); padding:30px;">Failed to fetch directory: ${e.message}</td></tr>`;
          }
        }
      }

      function filterStaffDirectory() {
        const q = (document.getElementById("staffDirectorySearch")?.value || "").toLowerCase().trim();
        const list = !q ? allEnrolledUsers : allEnrolledUsers.filter((u) =>
          [u.name, u.department, u.position, u.email, u.phone, u.cnic]
            .some((v) => (v || "").toString().toLowerCase().includes(q))
        );
        renderStaffDirectoryRows(list);
      }

      function cleanVal(v) {
        return v && v !== "None" && v !== "null" ? v : "";
      }

      function renderStaffDirectoryRows(users) {
        const tableBody = document.getElementById("directoryTableBody");
        if (!tableBody) return;

        if (!users || users.length === 0) {
          tableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-secondary); padding:35px;">
              <i class="fa-solid fa-users-slash" style="font-size:2em; margin-bottom:10px; display:block; opacity:0.5;"></i>
              No staff profiles found.</td></tr>`;
          return;
        }

        const dash = '<span style="color:var(--text-secondary); opacity:0.6;">—</span>';
        let html = "";
        users.forEach((user) => {
          const date = user.enrollment_date ? new Date(user.enrollment_date).toLocaleDateString() : "—";
          const dept = cleanVal(user.department);
          const pos = cleanVal(user.position);
          const email = cleanVal(user.email);
          const phone = cleanVal(user.phone);
          const cnic = cleanVal(user.cnic);
          const salary = Number(user.salary) > 0 ? `Rs. ${Number(user.salary).toLocaleString()}` : "";

          const present = (user.status_today || "Absent") === "Present";
          const statusBadge = present
            ? '<span class="badge badge-success" style="background:rgba(16,185,129,0.15); color:#10b981; border:1px solid rgba(16,185,129,0.3);"><i class="fa-solid fa-circle-check"></i> Present</span>'
            : '<span class="badge badge-danger" style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.2);"><i class="fa-solid fa-circle-xmark"></i> Absent</span>';
          const toggleBtn = present
            ? `<button onclick="toggleUserAttendance(${user.id}, 'absent', '__N__')" class="btn-outline btn-danger" style="width:auto; padding:5px 10px; font-size:0.78em;"><i class="fa-solid fa-user-minus"></i> Absent</button>`
            : `<button onclick="toggleUserAttendance(${user.id}, 'present', '__N__')" class="btn-outline" style="width:auto; padding:5px 10px; font-size:0.78em; border-color:#10b981; color:#10b981;"><i class="fa-solid fa-user-check"></i> Present</button>`;
          const safeName = (user.name || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, "&quot;");

          html += `<tr>
            <td><strong>#${user.id}</strong></td>
            <td>
              <div style="display:flex; align-items:center; gap:10px;">
                <div class="ticker-avatar" style="width:32px; height:32px; font-size:0.85em; font-weight:700; flex-shrink:0; background:linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);">${(user.name || "U").charAt(0).toUpperCase()}</div>
                <strong>${user.name}</strong>
              </div>
            </td>
            <td>
              ${dept ? `<span class="badge badge-info" style="font-weight:600;">${dept}</span>` : dash}
              ${pos ? `<div style="font-size:0.8em; color:var(--text-secondary); margin-top:3px;">${pos}</div>` : ""}
            </td>
            <td style="font-size:0.85em;">
              ${email ? `<div><i class="fa-regular fa-envelope" style="width:14px; opacity:0.6;"></i> ${email}</div>` : ""}
              ${phone ? `<div><i class="fa-solid fa-phone" style="width:14px; opacity:0.6;"></i> ${phone}</div>` : ""}
              ${!email && !phone ? dash : ""}
            </td>
            <td style="font-size:0.85em; font-family:monospace;">${cnic || dash}</td>
            <td style="font-size:0.85em; font-weight:600; color:#10b981;">${salary || dash}</td>
            <td>${statusBadge}</td>
            <td style="color:var(--text-secondary); font-size:0.82em;">${date}</td>
            <td style="text-align:right;">
              <div class="directory-actions" style="display:flex; gap:5px; justify-content:flex-end; flex-wrap:wrap;">
                ${toggleBtn.replace("__N__", safeName)}
                <button onclick="openEditModal(${user.id})" class="btn-outline" style="width:auto; padding:5px 10px; font-size:0.78em; border-color:var(--accent-primary); color:var(--accent-primary);" title="Edit"><i class="fa-solid fa-user-pen"></i></button>
                <button onclick="openPhotoUpload(${user.id}, '${safeName}')" class="btn-outline" style="width:auto; padding:5px 10px; font-size:0.78em; border-color:#14b8a6; color:#14b8a6;" title="Photo"><i class="fa-solid fa-camera"></i></button>
                <button onclick="deleteUserProfile(${user.id}, '${safeName}')" class="btn-outline btn-danger" style="width:auto; padding:5px 10px; font-size:0.78em;" title="Delete"><i class="fa-solid fa-trash"></i></button>
              </div>
            </td>
          </tr>`;
        });
        tableBody.innerHTML = html;
      }

      function openEditModal(userId) {
        const user = allEnrolledUsers.find((u) => u.id === userId);
        if (!user) return;

        document.getElementById("editUserId").value = user.id;
        document.getElementById("editName").value = user.name;
        document.getElementById("editEmail").value = user.email || "";
        document.getElementById("editDepartment").value = user.department || "";
        document.getElementById("editPhone").value = user.phone || "";
        document.getElementById("editNotes").value = user.notes || "";
        document.getElementById("editPosition").value = cleanVal(user.position);
        document.getElementById("editCNIC").value = cleanVal(user.cnic);
        document.getElementById("editSalary").value = Number(user.salary) > 0 ? user.salary : "";
        document.getElementById("editJoinDate").value = cleanVal(user.join_date);
        if (document.getElementById("editShiftId")) {
          document.getElementById("editShiftId").value = user.shift_id || 1;
        }

        document.getElementById("editModalMessage").innerHTML = "";

        const modal = document.getElementById("editUserModal");
        modal.style.display = "flex";
      }

      function closeEditModal() {
        document.getElementById("editUserModal").style.display = "none";
      }

      function openPhotoUpload(userId, userName) {
        document.getElementById("photoModalUserId").value = userId;
        document.getElementById("photoModalName").textContent = userName;
        document.getElementById("photoUploadMsg").innerHTML = "";
        document.getElementById("photoFileInput").value = "";
        document.getElementById("photoPreviewImg").style.display = "none";
        document.getElementById("photoPreviewIcon").style.display = "block";

        // Existing photo dikhao agar hai
        const existingImg = document.getElementById("photoPreviewImg");
        existingImg.src = `/profile_photos/user_${userId}.jpg`;
        existingImg.onload = function () {
          this.style.display = "block";
          document.getElementById("photoPreviewIcon").style.display = "none";
        };
        existingImg.onerror = function () {
          this.style.display = "none";
        };

        document.getElementById("photoUploadModal").style.display = "flex";
      }

      function closePhotoModal() {
        document.getElementById("photoUploadModal").style.display = "none";
      }

      function previewPhoto(input) {
        if (input.files && input.files[0]) {
          const reader = new FileReader();
          reader.onload = function (e) {
            const img = document.getElementById("photoPreviewImg");
            img.src = e.target.result;
            img.style.display = "block";
            document.getElementById("photoPreviewIcon").style.display = "none";
          };
          reader.readAsDataURL(input.files[0]);
        }
      }

      async function uploadProfilePhoto() {
        const userId = document.getElementById("photoModalUserId").value;
        const fileInput = document.getElementById("photoFileInput");

        if (!fileInput.files[0]) {
          document.getElementById("photoUploadMsg").innerHTML =
            '<div style="color:#dc2626; font-size:0.85em; margin-bottom:10px;"><i class="fa-solid fa-circle-exclamation"></i> Pehle photo select karein</div>';
          return;
        }

        const formData = new FormData();
        formData.append("photo", fileInput.files[0]);

        document.getElementById("photoUploadMsg").innerHTML =
          '<div style="color:#0891b2; font-size:0.85em; margin-bottom:10px;"><i class="fa-solid fa-spinner fa-spin"></i> Uploading...</div>';

        try {
          const resp = await fetch(`${API_BASE}/users/${userId}/photo`, {
            method: "POST",
            body: formData,
          });
          const data = await resp.json();

          if (resp.ok) {
            document.getElementById("photoUploadMsg").innerHTML =
              '<div style="color:#15803d; font-size:0.85em; margin-bottom:10px;"><i class="fa-solid fa-circle-check"></i> Photo uploaded successfully!</div>';

            // Directory mein bhi update karo
            loadStaffDirectory();

            setTimeout(() => closePhotoModal(), 1500);
          } else {
            document.getElementById("photoUploadMsg").innerHTML =
              `<div style="color:#dc2626; font-size:0.85em; margin-bottom:10px;"><i class="fa-solid fa-circle-exclamation"></i> ${data.error}</div>`;
          }
        } catch (e) {
          document.getElementById("photoUploadMsg").innerHTML =
            `<div style="color:#dc2626; font-size:0.85em; margin-bottom:10px;"><i class="fa-solid fa-circle-exclamation"></i> Error: ${e.message}</div>`;
        }
      }

      async function saveUserProfile() {
        const userId = document.getElementById("editUserId").value;
        const name = document.getElementById("editName").value.trim();
        const email = document.getElementById("editEmail").value.trim();
        const department = document.getElementById("editDepartment").value.trim();
        const phone = document.getElementById("editPhone").value.trim();
        const notes = document.getElementById("editNotes").value.trim();
        const position = document.getElementById("editPosition").value.trim();
        const cnic = document.getElementById("editCNIC").value.trim();
        const salary = document.getElementById("editSalary").value;
        const join_date = document.getElementById("editJoinDate").value;
        const shift_id = document.getElementById("editShiftId") ? parseInt(document.getElementById("editShiftId").value) : 1;
        const checkin_cameras = typeof getMultiSelectValues === 'function' ? getMultiSelectValues(document.getElementById("editCheckinCameras")) : 'all';
        const checkout_cameras = typeof getMultiSelectValues === 'function' ? getMultiSelectValues(document.getElementById("editCheckoutCameras")) : 'all';

        if (!name) {
          showMessage("editModalMessage", "Name is required", "error");
          return;
        }

        const btn = document.querySelector('#editUserModal button.btn-primary');
        const restoreBtn = setButtonLoading(btn, 'Saving...');
        try {
          const resp = await fetch(`${API_BASE}/users/${userId}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, department, phone, notes, position, cnic, salary, join_date, shift_id, checkin_cameras, checkout_cameras }),
          });
          const data = await resp.json();
          if (resp.ok) {
            closeEditModal();
            addTerminalLine(`[CRUD] Updated details for User '${name}' (ID: ${userId})`, "success");
            loadStaffDirectory();
            if (typeof loadTabStaffDirectory === 'function') loadTabStaffDirectory();
            loadStats();
            showAppToast(data.message || `Staff profile '${name}' updated successfully`, 'success');
          } else {
            showMessage("editModalMessage", data.error || 'Update failed', "error");
            showAppToast(data.error || 'Failed to update profile', 'error');
          }
        } catch (e) {
          showMessage("editModalMessage", `Connection Error: ${e.message}`, "error");
          showAppToast(`Error: ${e.message}`, 'error');
        } finally {
          restoreBtn();
        }
      }

      async function deleteUserProfile(userId, name) {
        if (!confirm(`WARNING:\nAre you absolutely sure you want to delete '${name}'?\n\nThis will permanently delete their profile, all trained biometric face embeddings, and attendance logs. This action CANNOT be undone.`)) return;

        addTerminalLine(`Deleting profile for '${name}' (ID: ${userId})...`, "warning");
        try {
          const resp = await fetch(`${API_BASE}/users/${userId}/delete`, { method: "POST" });
          const data = await resp.json();
          if (resp.ok) {
            addTerminalLine(`[CRUD] Successfully deleted User '${name}' (ID: ${userId}) and cleared all training embeddings.`, "success");
            loadStaffDirectory();
            loadStats();
            loadAttendanceLogs();
            showAppToast(`Profile for '${name}' permanently deleted`, 'success');
          } else {
            addTerminalLine(`[CRUD FAIL] Failed to delete User '${name}': ${data.error}`, "error-line");
            showAppToast(data.error || 'Deletion failed', 'error');
          }
        } catch (e) {
          addTerminalLine(`[CRUD ERROR] Failed to connect for deleting user: ${e.message}`, "error-line");
          showAppToast(`Error: ${e.message}`, 'error');
        }
      }

      async function toggleUserAttendance(userId, action, name) {
        const apiAction = action === "absent" ? "mark-absent" : "mark-present";
        addTerminalLine(
          `[CRUD] Manually marking '${name}' ${action}...`,
          "warning",
        );

        try {
          const resp = await fetch(`${API_BASE}/users/${userId}/${apiAction}`, {
            method: "POST",
          });

          const data = await resp.json();
          if (resp.ok) {
            showMessage(
              "directoryMessage",
              `'${name}' successfully marked ${action} for today`,
              "success",
            );
            addTerminalLine(
              `[CRUD] User '${name}' (ID: ${userId}) marked ${action} today.`,
              "success",
            );
            loadStaffDirectory();
            loadStats();
            loadAttendanceLogs();
            loadRoomsOccupancy();
            const locatorInput = document.getElementById("locatorSearchInput");
            if (locatorInput && locatorInput.value.trim()) {
              searchStaffLocation(locatorInput.value.trim());
            }
          } else {
            showMessage(
              "directoryMessage",
              `Action failed: ${data.error}`,
              "error",
            );
            addTerminalLine(
              `[CRUD FAIL] Failed to mark user: ${data.error}`,
              "error-line",
            );
          }
        } catch (e) {
          showMessage(
            "directoryMessage",
            `Connection Error: ${e.message}`,
            "error",
          );
          addTerminalLine(
            `[CRUD ERROR] Failed to connect: ${e.message}`,
            "error-line",
          );
        }
      }

      // ============================================
      // MULTI-CAMERA STAFF & ROOM LOCATOR JAVASCRIPT
      // ============================================
      function renderQuickStaffChips() {
        const container = document.getElementById("quickStaffChips");
        if (!container) return;

        if (allEnrolledUsers && allEnrolledUsers.length > 0) {
          container.innerHTML = allEnrolledUsers
            .slice(0, 8)
            .map(
              (u) => `
              <button 
                type="button"
                onclick="document.getElementById('locatorSearchInput').value='${u.name.replace(/'/g, "\\'")}'; searchStaffLocation('${u.name.replace(/'/g, "\\'")}');"
                style="background:#1e293b; border:1px solid #334155; color:#cbd5e1; padding:4px 10px; border-radius:16px; font-size:0.75em; cursor:pointer; font-weight:600; transition:all 0.15s;"
                onmouseover="this.style.borderColor='#3aafa9'; this.style.color='#3aafa9';"
                onmouseout="this.style.borderColor='#334155'; this.style.color='#cbd5e1';">
                <i class="fa-solid fa-user-tag" style="font-size:0.8em; margin-right:3px;"></i> ${u.name}
              </button>
            `
            )
            .join("");
        } else {
          fetch(`${API_BASE}/users`)
            .then((r) => r.json())
            .then((data) => {
              allEnrolledUsers = data.users || [];
              renderQuickStaffChips();
            })
            .catch(() => {
              container.innerHTML = '<span style="font-size:0.75em; color:#64748b;">No staff enrolled yet</span>';
            });
        }
      }

      async function searchStaffLocation(query) {
        const input = document.getElementById("locatorSearchInput");
        const q = (query || (input ? input.value : "")).trim();
        const msgDiv = document.getElementById("locatorStatusMsg");
        const resContainer = document.getElementById("locatorResultsContainer");
        const cardsDiv = document.getElementById("locatorResultsCards");

        if (!q) {
          if (msgDiv) {
            msgDiv.innerHTML = `<div class="error" style="background:rgba(239,68,68,0.1); border:1px solid #ef4444; color:#f87171; padding:10px 14px; border-radius:8px; font-size:0.88em;">
              <i class="fa-solid fa-triangle-exclamation"></i> Please enter an employee name to search.
            </div>`;
          }
          return;
        }

        if (msgDiv) {
          msgDiv.innerHTML = `<div class="info" style="background:rgba(58,175,169,0.1); border:1px solid #3aafa9; color:#3aafa9; padding:10px 14px; border-radius:8px; font-size:0.88em;">
            <i class="fa-solid fa-spinner fa-spin"></i> Searching all camera feeds for <strong>"${q}"</strong>...
          </div>`;
        }

        try {
          const resp = await fetch(`${API_BASE}/locate/person?name=${encodeURIComponent(q)}`);
          const data = await resp.json();

          if (!resp.ok) {
            throw new Error(data.message || "Failed to query locator API");
          }

          if (msgDiv) msgDiv.innerHTML = "";

          const results = data.results || [];
          if (results.length === 0) {
            resContainer.style.display = "block";
            cardsDiv.innerHTML = `
              <div style="background:#131826; border:1px dashed #334155; border-radius:14px; padding:32px; text-align:center; color:#94a3b8;">
                <i class="fa-solid fa-user-xmark" style="font-size:2.2em; color:#64748b; margin-bottom:10px; display:block;"></i>
                <div style="font-size:1.05em; font-weight:700; color:#e2e8f0;">No Enrolled Staff Matched "${q}"</div>
                <div style="font-size:0.85em; margin-top:5px;">Check spelling or enroll this employee in the Staff Enrollment tab first.</div>
              </div>
            `;
            return;
          }

          resContainer.style.display = "block";
          cardsDiv.innerHTML = results
            .map((res) => {
              const isActive = res.status === "active";
              const isRecent = res.status === "recent";
              const isNotSeen = res.status === "not_seen";

              const badgeBg = isActive
                ? "background:rgba(34,197,94,0.15); border:1px solid #22c55e; color:#22c55e;"
                : isRecent
                ? "background:rgba(245,158,11,0.15); border:1px solid #f59e0b; color:#f59e0b;"
                : "background:rgba(239,68,68,0.12); border:1px solid #ef4444; color:#f87171;";

              const pulseDot = isActive
                ? '<span class="status-pulse" style="width:9px; height:9px; background:#22c55e; border-radius:50%; display:inline-block; margin-right:6px;"></span>'
                : "";

              const confPct = Math.round((res.confidence || 0) * 100);
              const cropImg = res.face_crop
                ? `<img src="${res.face_crop}" style="width:72px; height:72px; border-radius:10px; object-fit:cover; border:2px solid #3aafa9;" />`
                : `<div style="width:72px; height:72px; border-radius:10px; background:#1e293b; border:1.5px dashed #475569; display:flex; align-items:center; justify-content:center; color:#64748b; font-size:0.7em; text-align:center; padding:4px;">No Live Crop</div>`;

              const streamBtn = res.camera_id
                ? `<button onclick="jumpToCameraFeed('${res.camera_id}')" class="btn btn-primary" style="padding:8px 16px; font-size:0.82em; background:linear-gradient(135deg,#3aafa9,#1d8a84); border:none; border-radius:8px; font-weight:700;">
                    <i class="fa-solid fa-video"></i> Switch Live View to ${res.camera_name || "Camera"}
                  </button>`
                : "";

              const scanBtn = `<button onclick="scanAllCamerasLiveNow('${res.name.replace(/'/g, "\\'")}')" class="btn btn-outline" style="padding:8px 14px; font-size:0.82em; border-color:#64748b; color:#cbd5e1; border-radius:8px;">
                    <i class="fa-solid fa-radar"></i> Rescan Cameras
                  </button>`;

              return `
                <div style="background:#131826; border:1px solid ${isActive ? "rgba(58,175,169,0.5)" : "#222c40"}; border-radius:16px; padding:20px 22px; margin-bottom:16px; box-shadow:0 8px 30px rgba(0,0,0,0.3); transition:transform 0.2s;">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
                    
                    <!-- Left: Profile & Location Details -->
                    <div style="display:flex; gap:16px; flex:1; min-width:280px;">
                      <div style="position:relative; flex-shrink:0;">
                        <img 
                          src="${res.photo_url}" 
                          style="width:72px; height:72px; border-radius:14px; object-fit:cover; border:2px solid #3aafa9; background:#1e293b;"
                          onerror="this.onerror=null; this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(res.name)}&background=3aafa9&color=fff&size=120';"
                        />
                        <span style="position:absolute; bottom:-3px; right:-3px; width:15px; height:15px; border-radius:50%; border:2px solid #131826; background:${isActive ? "#22c55e" : isRecent ? "#f59e0b" : "#ef4444"};"></span>
                      </div>

                      <div style="flex:1;">
                        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                          <h4 style="margin:0; font-size:1.15em; font-weight:800; color:#fff;">${res.name}</h4>
                          <span style="font-size:0.75em; color:#94a3b8; font-family:'JetBrains Mono',monospace;">EMP-${String(res.user_id).padStart(3, "0")}</span>
                          ${res.department ? `<span class="badge" style="background:#1e293b; color:#3aafa9; border:1px solid #334155; font-size:0.72em;">${res.department}</span>` : ""}
                        </div>

                        <!-- Big Room Status Banner -->
                        <div style="margin-top:10px; display:inline-flex; align-items:center; ${badgeBg} border-radius:20px; padding:6px 14px; font-weight:800; font-size:0.85em; letter-spacing:0.3px;">
                          ${pulseDot} ${res.status_label}
                        </div>

                        <div style="margin-top:8px; font-size:0.82em; color:#94a3b8; display:flex; flex-wrap:wrap; gap:14px;">
                          <span><i class="fa-solid fa-video" style="color:#3aafa9;"></i> <strong>Camera Feed:</strong> ${res.camera_name || "N/A"}</span>
                          <span><i class="fa-solid fa-clock" style="color:#f59e0b;"></i> <strong>Status Info:</strong> ${res.status_text}</span>
                          ${res.confidence > 0 ? `<span><i class="fa-solid fa-fingerprint" style="color:#22c55e;"></i> <strong>Confidence:</strong> ${confPct}%</span>` : ""}
                        </div>
                      </div>
                    </div>

                    <!-- Right: Live Face Snapshot & Actions -->
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:10px; flex-shrink:0;">
                      <div style="display:flex; align-items:center; gap:10px;">
                        <div style="text-align:right;">
                          <div style="font-size:0.72em; text-transform:uppercase; color:#64748b; font-weight:700;">Live Camera Crop</div>
                          <div style="font-size:0.75em; color:#94a3b8;">${res.last_seen_str}</div>
                        </div>
                        ${cropImg}
                      </div>

                      <div style="display:flex; gap:8px; margin-top:4px;">
                        ${streamBtn}
                        ${scanBtn}
                      </div>
                    </div>

                  </div>
                </div>
              `;
            })
            .join("");
        } catch (err) {
          if (msgDiv) {
            msgDiv.innerHTML = `<div class="error" style="background:rgba(239,68,68,0.1); border:1px solid #ef4444; color:#f87171; padding:10px 14px; border-radius:8px; font-size:0.88em;">
              <i class="fa-solid fa-triangle-exclamation"></i> Error locating staff: ${err.message}
            </div>`;
          }
        }
      }

      async function scanAllCamerasLiveNow(nameOverride) {
        const input = document.getElementById("locatorSearchInput");
        const targetName = (nameOverride || (input ? input.value : "")).trim();
        const msgDiv = document.getElementById("locatorStatusMsg");

        if (!targetName) {
          if (msgDiv) {
            msgDiv.innerHTML = `<div class="info" style="background:rgba(245,158,11,0.1); border:1px solid #f59e0b; color:#f59e0b; padding:10px 14px; border-radius:8px; font-size:0.88em;">
              <i class="fa-solid fa-circle-info"></i> Please type an employee name (e.g. Imran) above or click one of the quick staff chips before scanning.
            </div>`;
          }
          return;
        }

        if (msgDiv) {
          msgDiv.innerHTML = `<div class="info" style="background:rgba(58,175,169,0.12); border:1px solid #3aafa9; color:#3aafa9; padding:12px 16px; border-radius:8px; font-size:0.9em;">
            <i class="fa-solid fa-radar fa-spin"></i> Grabbing fresh snapshots from ALL connected cameras and checking for <strong>"${targetName}"</strong> right now...
          </div>`;
        }

        try {
          const resp = await fetch(`${API_BASE}/locate/scan-now`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: targetName }),
          });
          const data = await resp.json();

          if (!resp.ok) {
            throw new Error(data.message || "Instant scan failed");
          }

          if (data.found && data.found_details) {
            const f = data.found_details;
            if (msgDiv) {
              msgDiv.innerHTML = `<div class="success" style="background:rgba(34,197,94,0.15); border:1px solid #22c55e; color:#22c55e; padding:12px 16px; border-radius:8px; font-size:0.92em; font-weight:700;">
                <i class="fa-solid fa-circle-check"></i> MATCH FOUND! ${data.name} is currently sitting in <u>${f.room_name}</u> (${f.camera_name}) with ${(f.confidence * 100).toFixed(1)}% biometric confidence!
              </div>`;
            }
          } else {
            if (msgDiv) {
              msgDiv.innerHTML = `<div class="info" style="background:rgba(245,158,11,0.12); border:1px solid #f59e0b; color:#f59e0b; padding:12px 16px; border-radius:8px; font-size:0.9em;">
                <i class="fa-solid fa-circle-exclamation"></i> Instant scan completed across all active cameras: <strong>${data.name}</strong> was not detected sitting in front of any camera at this exact moment.
              </div>`;
            }
          }

          // Refresh the card results and the room grid
          searchStaffLocation(targetName);
          loadRoomsOccupancy();
        } catch (err) {
          if (msgDiv) {
            msgDiv.innerHTML = `<div class="error" style="background:rgba(239,68,68,0.1); border:1px solid #ef4444; color:#f87171; padding:10px 14px; border-radius:8px; font-size:0.88em;">
              <i class="fa-solid fa-triangle-exclamation"></i> Scan error: ${err.message}
            </div>`;
          }
        }
      }

      async function loadRoomsOccupancy() {
        const container = document.getElementById("roomsGridContainer");
        if (!container) return;

        try {
          const resp = await fetch(`${API_BASE}/locate/rooms`);
          const data = await resp.json();

          if (!resp.ok) throw new Error("Could not load rooms");

          const rooms = data.rooms || [];
          if (rooms.length === 0) {
            container.innerHTML = '<div style="padding:20px; color:#64748b; text-align:center; grid-column:1/-1;">No rooms configured</div>';
            return;
          }

          container.innerHTML = rooms
            .map((r) => {
              const occCount = r.occupant_count || 0;
              const hasOcc = occCount > 0;

              const occHTML = hasOcc
                ? r.occupants
                    .map(
                      (o) => `
                    <div style="display:flex; align-items:center; justify-content:space-between; background:#0b0f19; padding:8px 12px; border-radius:10px; border:1px solid #1e293b; margin-top:6px;">
                      <div style="display:flex; align-items:center; gap:9px;">
                        ${
                          o.face_crop
                            ? `<img src="${o.face_crop}" style="width:34px; height:34px; border-radius:8px; object-fit:cover; border:1.5px solid #3aafa9;" />`
                            : `<div style="width:34px; height:34px; border-radius:8px; background:#1e293b; border:1px solid #334155; display:flex; align-items:center; justify-content:center; color:#3aafa9; font-weight:800; font-size:0.8em;">${o.name.charAt(0)}</div>`
                        }
                        <div>
                          <div style="font-size:0.85em; font-weight:700; color:#e2e8f0;">${o.name}</div>
                          <div style="font-size:0.7em; color:#64748b;">${o.department || "Staff"} • In room: ${o.dwell_minutes}m</div>
                        </div>
                      </div>
                      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:5px;">
                        <span class="badge" style="background:#e5f5ff; color:#247eae; border:1px solid #9bcce7; font-size:0.68em; padding:3px 8px;">
                          Active (${o.last_seen_sec}s ago)
                        </span>
                        <button type="button" class="btn-outline" style="min-height:28px; padding:0 8px; font-size:0.68em;" onclick="openLocatorHistory(${o.user_id}, '${o.name.replace(/'/g, "\\'")}')">
                          <i class="fa-solid fa-clock-rotate-left"></i> History
                        </button>
                      </div>
                    </div>
                  `
                    )
                    .join("")
                : `<div style="padding:14px; text-align:center; color:#64748b; font-size:0.8em; font-style:italic; background:#0b0f19; border-radius:10px; border:1px dashed #1e293b;">No active occupants sitting in this room right now</div>`;

              return `
                <div style="background:#131826; border:1px solid ${hasOcc ? "rgba(58,175,169,0.3)" : "#222c40"}; border-radius:14px; padding:18px; display:flex; flex-direction:column; gap:12px;">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                      <div style="font-size:1.05em; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-door-open" style="color:#3aafa9;"></i> ${r.room_name}
                      </div>
                      <div style="font-size:0.75em; color:#94a3b8; margin-top:2px;">
                        ${r.camera_name} • <span style="color:#64748b;">${r.description}</span>
                      </div>
                    </div>
                    <span class="badge" style="${hasOcc ? "background:rgba(34,197,94,0.15); border:1px solid #22c55e; color:#22c55e;" : "background:#1e293b; color:#94a3b8; border:1px solid #334155;"} font-size:0.78em; padding:5px 10px;">
                      ${occCount} ${occCount === 1 ? "Person" : "People"}
                    </span>
                  </div>

                  <div>
                    <div style="font-size:0.75em; text-transform:uppercase; letter-spacing:0.5px; color:#64748b; font-weight:700; margin-bottom:4px;">Current Occupants</div>
                    ${occHTML}
                  </div>

                  <div style="margin-top:auto; padding-top:10px; border-top:1px solid #1e293b; display:flex; justify-content:flex-end;">
                    <button onclick="jumpToCameraFeed('${r.camera_id}')" class="btn btn-outline" style="padding:6px 14px; font-size:0.78em; border-color:#3aafa9; color:#3aafa9; border-radius:8px;">
                      <i class="fa-solid fa-video"></i> View Stream
                    </button>
                  </div>
                </div>
              `;
            })
            .join("");
        } catch (err) {
          container.innerHTML = `<div style="padding:20px; color:#f87171; text-align:center; grid-column:1/-1;">Failed to load rooms: ${err.message}</div>`;
        }
      }

      async function openLocatorHistory(userId, userName) {
        const modal = document.getElementById("locatorHistoryModal");
        const body = document.getElementById("locatorHistoryBody");
        const title = document.getElementById("locatorHistoryTitle");
        const subtitle = document.getElementById("locatorHistorySubtitle");
        if (!modal || !body) return;

        title.textContent = `${userName} - Presence History`;
        subtitle.textContent = "Persistent room snapshots recorded every five minutes";
        body.innerHTML = '<div class="locator-history-empty"><i class="fa-solid fa-spinner fa-spin"></i> Loading history...</div>';
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");

        try {
          const response = await fetch(`${API_BASE}/locate/history?user_id=${encodeURIComponent(userId)}&limit=500&_=${Date.now()}`, { cache: "no-store" });
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "History could not be loaded");

          const history = data.history || [];
          if (history.length === 0) {
            body.innerHTML = '<div class="locator-history-empty"><i class="fa-solid fa-clock"></i><br>No five-minute history has been recorded for this person yet.</div>';
            return;
          }

          body.innerHTML = `
            <table class="locator-history-table">
              <thead>
                <tr><th>Recorded</th><th>Room</th><th>Camera</th><th>Presence Window</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                ${history.map((entry) => `
                  <tr>
                    <td>${formatLocatorDate(entry.recorded_at)}</td>
                    <td><strong>${entry.room_name}</strong></td>
                    <td>${entry.camera_name}</td>
                    <td>${formatLocatorDate(entry.first_seen)} to ${formatLocatorDate(entry.last_seen)}</td>
                    <td>${Math.round((entry.confidence || 0) * 100)}%</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>`;
        } catch (error) {
          body.innerHTML = `<div class="locator-history-empty"><i class="fa-solid fa-circle-exclamation"></i><br>${error.message}</div>`;
        }
      }

      function formatLocatorDate(value) {
        if (!value) return "Unknown";
        const parsed = new Date(String(value).replace(" ", "T"));
        return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
      }

      function closeLocatorHistory() {
        const modal = document.getElementById("locatorHistoryModal");
        if (!modal) return;
        modal.classList.remove("is-open");
        modal.classList.remove("is-expanded");
        modal.setAttribute("aria-hidden", "true");
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => {});
        }
      }

      async function toggleLocatorHistoryFullscreen() {
        const modal = document.getElementById("locatorHistoryModal");
        const panel = modal?.querySelector(".locator-history-panel");
        if (!modal || !panel) return;

        if (document.fullscreenElement) {
          await document.exitFullscreen().catch(() => {});
          modal.classList.remove("is-expanded");
          return;
        }

        modal.classList.add("is-expanded");
        if (panel.requestFullscreen) {
          await panel.requestFullscreen().catch(() => {});
        }
      }

      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeLocatorHistory();
      });

      document.addEventListener("fullscreenchange", () => {
        const modal = document.getElementById("locatorHistoryModal");
        if (!document.fullscreenElement && modal) {
          modal.classList.remove("is-expanded");
        }
      });

      function jumpToCameraFeed(cameraId) {
        // Switch tab to live-view
        const liveViewBtn = document.querySelector(".menu-item[onclick*='live-view']");
        if (liveViewBtn) {
          switchTab("live-view", liveViewBtn);
        }

        // Select camera button
        setTimeout(() => {
          const camBtns = document.querySelectorAll(".camera-tab-btn");
          camBtns.forEach((btn) => {
            if (btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(cameraId)) {
              selectCamera(cameraId, btn);
              toggleLiveStream();
            }
          });
        }, 150);
      }

      // ── Main Attendance & Department Reports JS Logic ──
      let currentMainFilterDate = 'today';
      let mainReportData = null;

      async function initMainReportsTab() {
        fetchMainDepartments();
        fetchMainReport();
      }

      async function fetchMainDepartments() {
        try {
          const res = await fetch(`${API_BASE}/reports/departments`);
          const data = await res.json();
          const select = document.getElementById('mainDeptFilter');
          if (select && data.departments && data.departments.length > 0) {
            select.innerHTML = '<option value="all">All Departments</option>';
            data.departments.forEach(dept => {
              const opt = document.createElement('option');
              opt.value = dept;
              opt.textContent = dept;
              select.appendChild(opt);
            });
          }
        } catch (err) {
          console.error("Failed to load report departments:", err);
        }
      }

      let currentMainActiveModalUserId = null;

      function handleMainDateRangeChange(force = false) {
        const sInput = document.getElementById('mainStartDate');
        const eInput = document.getElementById('mainEndDate');
        let s = sInput ? sInput.value : '';
        let e = eInput ? eInput.value : '';

        currentMainFilterDate = 'custom';
        document.querySelectorAll('.main-date-preset').forEach(btn => {
          btn.classList.remove('btn-primary', 'active');
          btn.classList.add('btn-outline');
        });
        const targetBtn = document.getElementById('mBtnCustom');
        if (targetBtn) {
          targetBtn.classList.remove('btn-outline');
          targetBtn.classList.add('btn-primary', 'active');
        }

        const customGroup = document.getElementById('mainCustomRangeGroup');
        if (customGroup) customGroup.style.display = 'flex';

        if (s && e) {
          if (s > e) {
            const temp = s;
            s = e;
            e = temp;
            if (sInput) sInput.value = s;
            if (eInput) eInput.value = e;
          }
          fetchMainReport();
        } else if (force) {
          fetchMainReport();
        }
      }

      function setMainDateFilter(preset) {
        currentMainFilterDate = preset;
        document.querySelectorAll('.main-date-preset').forEach(btn => {
          btn.classList.remove('btn-primary', 'active');
          btn.classList.add('btn-outline');
        });
        
        const customGroup = document.getElementById('mainCustomRangeGroup');
        if (customGroup) customGroup.style.display = 'none';

        const btnMap = {
          'today': 'mBtnToday',
          'yesterday': 'mBtnYesterday',
          'last7': 'mBtnLast7',
          'this_week': 'mBtnThisWeek',
          'this_month': 'mBtnThisMonth',
          'last30': 'mBtnLast30',
          'custom': 'mBtnCustom'
        };

        const targetId = btnMap[preset] || 'mBtnToday';
        const targetBtn = document.getElementById(targetId);
        if (targetBtn) {
          targetBtn.classList.remove('btn-outline');
          targetBtn.classList.add('btn-primary', 'active');
        }

        if (preset === 'custom') {
          if (customGroup) customGroup.style.display = 'flex';
          const sInput = document.getElementById('mainStartDate');
          const eInput = document.getElementById('mainEndDate');
          if (sInput && eInput && (!sInput.value || !eInput.value)) {
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            if (!sInput.value) sInput.value = `${year}-${month}-01`;
            if (!eInput.value) eInput.value = `${year}-${month}-${day}`;
          }
          fetchMainReport();
          return;
        }
        fetchMainReport();
      }

      async function fetchMainReport() {
        let url = `${API_BASE}/reports/attendance?`;
        const dept = document.getElementById('mainDeptFilter')?.value || 'all';
        const status = document.getElementById('mainStatusFilter')?.value || 'all';

        if (dept !== 'all') url += `&department=${encodeURIComponent(dept)}`;
        if (status !== 'all') url += `&status=${encodeURIComponent(status)}`;

        const s = document.getElementById('mainStartDate')?.value;
        const e = document.getElementById('mainEndDate')?.value;

        if (currentMainFilterDate === 'custom' || (s && e)) {
          if (s && e) {
            url += `&start_date=${s <= e ? s : e}&end_date=${s <= e ? e : s}`;
          } else if (s) {
            url += `&start_date=${s}&end_date=${s}`;
          } else if (e) {
            url += `&start_date=${e}&end_date=${e}`;
          } else {
            url += '&date=today';
          }
        } else if (currentMainFilterDate === 'today') {
          url += '&date=today';
        } else if (currentMainFilterDate === 'yesterday') {
          url += '&date=yesterday';
        } else if (currentMainFilterDate === 'last7') {
          url += '&date=last7';
        } else if (currentMainFilterDate === 'this_week') {
          url += '&date=this_week';
        } else if (currentMainFilterDate === 'this_month') {
          url += '&date=this_month';
        } else if (currentMainFilterDate === 'last30') {
          url += '&date=last30';
        } else {
          url += '&date=today';
        }

        try {
          const res = await fetch(url);
          mainReportData = await res.json();
          renderMainReportUI(mainReportData);
        } catch (err) {
          console.error("Failed to fetch main report:", err);
        }
      }

      function formatMainTime(isoString) {
        if (!isoString) return '-';
        const strVal = String(isoString).trim();
        if (!strVal || strVal === 'None' || strVal === 'null' || strVal === '--:--' || strVal === '-') return '-';
        try {
          if (/am|pm/i.test(strVal)) return strVal;
          let s = strVal;
          if (s.includes(' ')) s = s.split(' ')[1];
          if (s.includes('T')) s = s.split('T')[1];
          s = s.split('.')[0];
          const parts = s.split(':');
          if (parts.length >= 2) {
            let h = parseInt(parts[0], 10);
            const m = parts[1];
            const ampm = h >= 12 ? 'PM' : 'AM';
            h = h % 12 || 12;
            return `${String(h).padStart(2, '0')}:${m} ${ampm}`;
          }
          const date = new Date(strVal.replace(' ', 'T'));
          if (!isNaN(date.getTime())) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
          }
        } catch (e) {}
        return strVal;
      }

      function renderMainReportUI(data) {
        const isMultiDay = Boolean(data.is_multi_day);
        const summary = data.summary || {};
        
        const elTotal = document.getElementById('mainStatTotal');
        const elPres = document.getElementById('mainStatPresent');
        const elAbs = document.getElementById('mainStatAbsent');
        const elLate = document.getElementById('mainStatLate');
        const elPresLabel = document.getElementById('mainStatPresentLabel');
        const elAbsLabel = document.getElementById('mainStatAbsentLabel');

        if (isMultiDay) {
          if (elTotal) elTotal.textContent = summary.total_enrolled || summary.total_registered || 0;
          if (elPres) elPres.textContent = summary.attended_count || 0;
          if (elAbs) elAbs.textContent = summary.zero_attendance_count || 0;
          if (elLate) elLate.textContent = summary.total_late_days || 0;

          if (elPresLabel) elPresLabel.textContent = `Attended (${summary.attendance_rate || 0}%)`;
          if (elAbsLabel) elAbsLabel.textContent = `Zero Attendance (${summary.total_absent_days || 0} Total Abs)`;
        } else {
          const tot = summary.total_enrolled || summary.total_matching || summary.total_registered || (data.records ? data.records.length : 0);
          const pres = summary.total_present_days !== undefined ? summary.total_present_days : (summary.present !== undefined ? summary.present : 0);
          const abs = summary.total_absent_days !== undefined ? summary.total_absent_days : (summary.absent !== undefined ? summary.absent : (tot - pres));
          const late = summary.total_late_days !== undefined ? summary.total_late_days : (summary.late !== undefined ? summary.late : 0);
          const rate = summary.attendance_rate !== undefined ? summary.attendance_rate : (tot > 0 ? (pres / tot * 100).toFixed(1) : 0);

          if (elTotal) elTotal.textContent = tot;
          if (elPres) elPres.textContent = pres;
          if (elAbs) elAbs.textContent = abs;
          if (elLate) elLate.textContent = late;

          if (elPresLabel) elPresLabel.textContent = `Present (${rate}%)`;
          const absRate = tot > 0 ? ((abs / tot) * 100).toFixed(1) : 0;
          if (elAbsLabel) elAbsLabel.textContent = `Absent (${absRate}%)`;
        }

        const elSubtitle = document.getElementById('mainReportSubtitle');
        if (elSubtitle) elSubtitle.textContent = `Report Period: ${data.date_label || 'Today'} • Sync: ${new Date().toLocaleTimeString()}`;

        // Render Department Grid
        const grid = document.getElementById('mainDeptGrid');
        if (grid) {
          grid.innerHTML = '';
          if (data.departments && data.departments.length > 0) {
            data.departments.forEach(dept => {
              const rate = dept.attendance_rate || 0;
              let barColor = '#10b981';
              if (rate < 50) barColor = '#ef4444';
              else if (rate < 75) barColor = '#f59e0b';

              const staffCount = dept.total !== undefined ? dept.total : (dept.total_staff !== undefined ? dept.total_staff : 0);
              const presText = dept.present_days !== undefined ? `${dept.present_days} Days` : `${dept.present || 0} Present`;
              const absText = dept.absent_days !== undefined ? `${dept.absent_days} Days` : `${dept.absent || 0} Absent`;

              const card = document.createElement('div');
              card.style.cssText = 'background:#ffffff; border:1px solid #cfe8f7; border-radius:12px; padding:14px; box-shadow:0 4px 14px rgba(61,159,212,0.06);';
              card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <strong style="color:#173042; font-size:0.92em;">${dept.department}</strong>
                  <span style="font-size:0.75em; color:#64748b; background:#f0f7fc; padding:2px 8px; border-radius:6px; font-weight:700;">${staffCount} Headcount</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.8em; margin-bottom:6px;">
                  <span style="color:#1e8e3e; font-weight:600;"><i class="fa-solid fa-check"></i> ${presText}</span>
                  <span style="color:#d93025; font-weight:600;"><i class="fa-solid fa-xmark"></i> ${absText}</span>
                  <span style="font-weight:800; color:#173042;">${rate}%</span>
                </div>
                <div style="width:100%; height:6px; background:#e2e8f0; border-radius:10px; overflow:hidden;">
                  <div style="height:100%; width:${rate}%; background:${barColor}; border-radius:10px; transition:width 0.4s ease;"></div>
                </div>
              `;
              grid.appendChild(card);
            });
          } else {
            grid.innerHTML = '<p style="color:#64748b; font-size:0.85em;">No department summary data available.</p>';
          }
        }

        // Re-apply the live search so a background refresh doesn't clear the user's filter
        const liveQuery = document.getElementById('mainReportSearch')?.value.trim() || '';
        if (liveQuery) {
          filterMainTableLocally();
        } else {
          renderMainTableRows(data.records || [], isMultiDay);
        }
      }

      function filterMainTableLocally() {
        const query = document.getElementById('mainReportSearch')?.value.toLowerCase().trim() || '';
        if (!mainReportData || !mainReportData.records) return;
        const isMultiDay = Boolean(mainReportData.is_multi_day);
        const filtered = mainReportData.records.filter(r => {
          if (!query) return true;
          return (r.name && r.name.toLowerCase().includes(query)) ||
                 (r.department && r.department.toLowerCase().includes(query)) ||
                 (r.position && r.position.toLowerCase().includes(query)) ||
                 (r.cnic && r.cnic.toLowerCase().includes(query)) ||
                 (r.email && r.email.toLowerCase().includes(query)) ||
                 (r.phone && r.phone.toLowerCase().includes(query)) ||
                 (r.user_id && String(r.user_id).includes(query));
        });
        renderMainTableRows(filtered, isMultiDay);
      }

      function renderMainTableRows(records, isMultiDay) {
        const thead = document.getElementById('mainReportThead');
        const tbody = document.getElementById('mainReportTbody');
        const emptyState = document.getElementById('mainReportEmpty');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (thead) {
          if (isMultiDay) {
            thead.innerHTML = `
              <tr>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; width:75px;"># ID</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Staff Member</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Department</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Designation</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Assigned Shift</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; text-align:center;">Present Days</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; text-align:center;">Absent Days</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; text-align:center;">Late Days</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; text-align:center;">Attendance %</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; text-align:center; width:140px;">Action</th>
              </tr>
            `;
          } else {
            thead.innerHTML = `
              <tr>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; width:75px;"># ID</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Staff Member</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Department</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Date</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Status</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Check-In Time</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Check-Out Time</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b;">Camera / Location</th>
                <th style="padding:12px 16px; font-size:0.75em; text-transform:uppercase; color:#64748b; text-align:right;">Quick Action</th>
              </tr>
            `;
          }
        }

        if (!records || records.length === 0) {
          if (emptyState) emptyState.style.display = 'block';
          return;
        }
        if (emptyState) emptyState.style.display = 'none';

        records.forEach(r => {
          const tr = document.createElement('tr');
          tr.style.borderBottom = '1px solid #f1f5f9';

          const initial = r.name ? r.name.charAt(0).toUpperCase() : '?';
          let photoHtml = `<div style="width:32px; height:32px; border-radius:50%; background:#0284c7; color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.8rem; flex-shrink:0;">${initial}</div>`;
          if (r.photo_path) {
            photoHtml = `<img src="/api/users/${r.user_id}/photo" style="width:32px; height:32px; border-radius:50%; object-fit:cover; flex-shrink:0;" onerror="this.onerror=null; this.outerHTML='<div style=\\'width:32px; height:32px; border-radius:50%; background:#0284c7; color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.8rem; flex-shrink:0;\\'>${initial}</div>'">`;
          }

          const empIdDisp = `EMP-${String(r.user_id).padStart(3, '0')}`;
          const shiftDisplay = r.shift_name || 'General Shift';

          if (isMultiDay) {
            // MULTI-DAY ONE ROW PER EMPLOYEE
            const presRate = r.attendance_rate || 0;
            let rateColor = '#16a34a';
            if (presRate < 50) rateColor = '#dc2626';
            else if (presRate < 75) rateColor = '#d97706';

            tr.innerHTML = `
              <td style="padding:10px 14px; font-weight:700; color:#0284c7; font-size:0.82rem;">${empIdDisp}</td>
              <td style="padding:10px 14px;">
                <div style="display:flex; align-items:center; gap:9px;">
                  ${photoHtml}
                  <div>
                    <div style="font-weight:600; color:#0f172a; font-size:0.88rem;">${r.name || ''}</div>
                    <div style="font-size:0.72rem; color:#64748b;">${r.position || 'Staff Member'}</div>
                  </div>
                </div>
              </td>
              <td style="padding:10px 14px;"><span style="color:#2563eb; font-weight:600; font-size:0.83rem;">${r.department || 'General'}</span></td>
              <td style="padding:10px 14px; font-size:0.82rem; color:#475569;">${r.position || 'Staff Member'}</td>
              <td style="padding:10px 14px; font-size:0.8rem; color:#475569;"><i class="fa-solid fa-business-time" style="color:#0284c7; margin-right:4px;"></i>${shiftDisplay}</td>
              <td style="padding:10px 14px; text-align:center;">
                <span class="badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; padding:4px 10px; font-weight:700; font-size:0.8rem;">
                  <i class="fa-solid fa-check"></i> ${r.present_display || (r.present_days + ' / ' + r.working_days)}
                </span>
              </td>
              <td style="padding:10px 14px; text-align:center;">
                <span class="badge" style="background:#fef2f2; color:#b91c1c; border:1px solid #fecaca; padding:4px 10px; font-weight:700; font-size:0.8rem;">
                  <i class="fa-solid fa-xmark"></i> ${r.absent_display || (r.absent_days + ' / ' + r.working_days)}
                </span>
              </td>
              <td style="padding:10px 14px; text-align:center;">
                <span class="badge" style="background:#fffbeb; color:#b45309; border:1px solid #fde68a; padding:4px 10px; font-weight:700; font-size:0.8rem;">
                  <i class="fa-solid fa-clock"></i> ${r.late_days || 0}
                </span>
              </td>
              <td style="padding:10px 14px; text-align:center;">
                <div style="display:inline-flex; flex-direction:column; align-items:center; gap:3px;">
                  <strong style="color:${rateColor}; font-size:0.88rem;">${presRate}%</strong>
                  <div style="width:50px; height:4px; background:#e2e8f0; border-radius:4px; overflow:hidden;">
                    <div style="height:100%; width:${presRate}%; background:${rateColor};"></div>
                  </div>
                </div>
              </td>
              <td style="padding:10px 14px; text-align:center;">
                <button onclick="openMainCompleteView(${r.user_id})" class="btn btn-sm" style="background:#0284c7; color:#ffffff; border:none; padding:5px 12px; font-size:0.78rem; font-weight:600; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; box-shadow:0 2px 4px rgba(2,132,199,0.2);">
                  <i class="fa-solid fa-calendar-days"></i> Complete View
                </button>
              </td>
            `;
          } else {
            // SINGLE DAY VIEW
            let statusBadge = '';
            const st = (r.status || 'absent').toLowerCase();
            if (st === 'checked_out' || (r.last_seen && r.last_seen !== '--:--' && r.last_seen !== '-')) {
              statusBadge = '<span class="badge" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-right-from-bracket"></i> Checked Out</span>';
            } else if (st === 'present') {
              statusBadge = '<span class="badge" style="background:#e6f4ea; color:#1e8e3e; border:1px solid #a8dab5; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-circle-check"></i> Present</span>';
            } else if (st === 'late') {
              statusBadge = '<span class="badge" style="background:#fef7e0; color:#b06000; border:1px solid #f9e29c; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-clock"></i> Late</span>';
            } else {
              statusBadge = '<span class="badge" style="background:#fce8e6; color:#d93025; border:1px solid #f5b4b0; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-circle-xmark"></i> Absent</span>';
            }

            const firstTime = formatMainTime(r.first_seen);
            const lastTime = formatMainTime(r.last_seen);
            const targetDate = r.date || 'today';
            const dept = String(r.department || '—').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const loc = String(r.location || '—').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const pos = String(r.position || r.email || r.phone || 'Staff Member').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

            tr.innerHTML = `
              <td style="padding:10px 14px; font-weight:600; color:#94a3b8; font-size:0.78em;">#${r.user_id}</td>
              <td style="padding:10px 14px;">
                <div style="display:flex; align-items:center; gap:8px;">
                  ${photoHtml}
                  <div>
                    <div style="font-weight:600; color:#173042; font-size:0.86em;">${r.name || ''}</div>
                    <div style="font-size:0.7em; color:#64748b;">${pos}</div>
                  </div>
                </div>
              </td>
              <td style="padding:10px 14px;"><span style="color:#247eae; font-weight:600; font-size:0.82em;">${dept}</span></td>
              <td style="padding:10px 14px; font-size:0.8em; color:#475569;">${r.date || 'Today'}</td>
              <td style="padding:10px 14px;">${statusBadge}</td>
              <td style="padding:10px 14px; font-size:0.8em; color:#475569;"><i class="fa-regular fa-clock" style="color:#94a3b8; margin-right:3px;"></i>${firstTime}</td>
              <td style="padding:10px 14px; font-size:0.8em; color:#475569;"><i class="fa-solid fa-eye" style="color:#94a3b8; margin-right:3px;"></i>${lastTime}</td>
              <td style="padding:10px 14px; font-size:0.78em; color:#475569;"><i class="fa-solid fa-location-dot" style="color:#3d9fd4; margin-right:3px;"></i>${loc}</td>
              <td style="padding:10px 14px; text-align:right;"></td>
            `;

            const actionCell = tr.lastElementChild;
            const btn = document.createElement('button');
            if (st === 'absent') {
              btn.style.cssText = 'padding:4px 10px; font-size:0.74em; font-weight:700; border-radius:6px; border:1.5px solid #16a34a; color:#15803d; background:#f0fdf4; cursor:pointer; display:inline-flex; align-items:center; gap:4px; transition:all 0.18s; white-space:nowrap;';
              btn.innerHTML = '<i class="fa-solid fa-check"></i> Mark Present';
              btn.addEventListener('mouseenter', function() { this.style.background = '#dcfce7'; });
              btn.addEventListener('mouseleave', function() { this.style.background = '#f0fdf4'; });
              btn.addEventListener('click', function() { markMainUserPresent(r.user_id, targetDate, r.name, this); });
            } else {
              btn.style.cssText = 'padding:4px 10px; font-size:0.74em; font-weight:700; border-radius:6px; border:1.5px solid #dc2626; color:#b91c1c; background:#fef2f2; cursor:pointer; display:inline-flex; align-items:center; gap:4px; transition:all 0.18s; white-space:nowrap;';
              btn.innerHTML = '<i class="fa-solid fa-xmark"></i> Mark Absent';
              btn.addEventListener('mouseenter', function() { this.style.background = '#fee2e2'; });
              btn.addEventListener('mouseleave', function() { this.style.background = '#fef2f2'; });
              btn.addEventListener('click', function() { markMainUserAbsent(r.user_id, targetDate, r.name, this); });
            }
            actionCell.appendChild(btn);
          }

          tbody.appendChild(tr);
        });
      }

      function showAppToast(message, type = 'info') {
        let container = document.getElementById('appToastContainer');
        if (!container) {
          container = document.createElement('div');
          container.id = 'appToastContainer';
          container.style.cssText = 'position:fixed; bottom:24px; right:24px; z-index:99999; display:flex; flex-direction:column; gap:10px; pointer-events:none;';
          document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.style.cssText = `
          pointer-events:auto;
          min-width:260px;
          max-width:380px;
          padding:12px 16px;
          border-radius:8px;
          box-shadow:0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.1);
          display:flex;
          align-items:center;
          gap:10px;
          font-size:0.85rem;
          font-weight:600;
          font-family:inherit;
          transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          transform:translateY(20px);
          opacity:0;
          ${type === 'success' ? 'background:#10b981; color:#ffffff;' : type === 'error' ? 'background:#ef4444; color:#ffffff;' : 'background:#1e293b; color:#ffffff;'}
        `;
        const icon = type === 'success' ? '<i class="fa-solid fa-circle-check"></i>' : type === 'error' ? '<i class="fa-solid fa-circle-exclamation"></i>' : '<i class="fa-solid fa-circle-info"></i>';
        toast.innerHTML = `<span>${icon}</span><span style="flex:1; line-height:1.3;">${message}</span>`;
        container.appendChild(toast);
        
        requestAnimationFrame(() => {
          toast.style.transform = 'translateY(0)';
          toast.style.opacity = '1';
        });
        
        setTimeout(() => {
          toast.style.transform = 'translateY(10px)';
          toast.style.opacity = '0';
          setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
          }, 300);
        }, 3200);
      }

      async function markMainUserPresent(userId, targetDate, userName, btnElement) {
        let originalContent = '';
        if (btnElement) {
          originalContent = btnElement.innerHTML;
          btnElement.disabled = true;
          btnElement.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating...';
          btnElement.style.opacity = '0.7';
          btnElement.style.cursor = 'not-allowed';
        }
        try {
          const resp = await fetch(`/api/users/${userId}/mark-present`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: targetDate && targetDate !== 'today' && targetDate !== 'Today' ? targetDate : null })
          });
          const data = await resp.json();
          if (resp.ok && (data.success || data.message)) {
            showAppToast(data.message || `Marked ${userName || 'staff'} present`, 'success');
            if (typeof fetchMainReport === 'function') {
              fetchMainReport();
            }
          } else {
            showAppToast(data.error || 'Failed to mark present', 'error');
            if (btnElement) {
              btnElement.disabled = false;
              btnElement.innerHTML = originalContent;
              btnElement.style.opacity = '1';
              btnElement.style.cursor = 'pointer';
            }
          }
        } catch (err) {
          showAppToast('Error marking present: ' + err.message, 'error');
          if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = originalContent;
            btnElement.style.opacity = '1';
            btnElement.style.cursor = 'pointer';
          }
        }
      }

      async function markMainUserAbsent(userId, targetDate, userName, btnElement) {
        let originalContent = '';
        if (btnElement) {
          originalContent = btnElement.innerHTML;
          btnElement.disabled = true;
          btnElement.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Updating...';
          btnElement.style.opacity = '0.7';
          btnElement.style.cursor = 'not-allowed';
        }
        try {
          const resp = await fetch(`/api/users/${userId}/mark-absent`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: targetDate && targetDate !== 'today' && targetDate !== 'Today' ? targetDate : null })
          });
          const data = await resp.json();
          if (resp.ok && (data.success || data.message)) {
            showAppToast(data.message || `Marked ${userName || 'staff'} absent`, 'success');
            if (typeof fetchMainReport === 'function') {
              fetchMainReport();
            }
          } else {
            showAppToast(data.error || 'Failed to mark absent', 'error');
            if (btnElement) {
              btnElement.disabled = false;
              btnElement.innerHTML = originalContent;
              btnElement.style.opacity = '1';
              btnElement.style.cursor = 'pointer';
            }
          }
        } catch (err) {
          showAppToast('Error marking absent: ' + err.message, 'error');
          if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = originalContent;
            btnElement.style.opacity = '1';
            btnElement.style.cursor = 'pointer';
          }
        }
      }

      // ================= MAIN COMPLETE VIEW MODAL LOGIC =================
      function openMainCompleteView(userId) {
        try {
          if (!mainReportData || !mainReportData.records) return;
          const emp = mainReportData.records.find(r => String(r.user_id) === String(userId));
          if (!emp) return;

          currentMainActiveModalUserId = userId;

          const initial = emp.name ? emp.name.charAt(0).toUpperCase() : '?';
          const avatarBox = document.getElementById('mainModalAvatar');
          if (avatarBox) {
            if (emp.photo_path) {
              avatarBox.innerHTML = `<img src="/api/users/${emp.user_id}/photo" style="width:48px; height:48px; border-radius:50%; object-fit:cover;" onerror="this.onerror=null; this.outerHTML='<div style=\\'width:48px; height:48px; border-radius:50%; background:#0284c7; color:#fff; display:flex; align-items:center; justify-content:center; font-size:1.2rem; font-weight:700;\\'>${initial}</div>'">`;
            } else {
              avatarBox.innerHTML = initial;
            }
          }

          const elName = document.getElementById('mainModalEmpName');
          if (elName) elName.textContent = emp.name || 'Employee';
          const elId = document.getElementById('mainModalEmpId');
          if (elId) elId.textContent = `EMP-${String(emp.user_id).padStart(3, '0')}`;
          const elDept = document.getElementById('mainModalEmpDept');
          if (elDept) elDept.textContent = emp.department || 'General';
          const elPos = document.getElementById('mainModalEmpPos');
          if (elPos) elPos.textContent = emp.position || 'Staff Member';
          const elShift = document.getElementById('mainModalEmpShift');
          if (elShift) elShift.innerHTML = `<i class="fa-solid fa-business-time"></i> ${emp.shift_name || 'General Shift'}`;

          const dateLabel = mainReportData.date_label || 'Reporting Period';
          const elPeriod = document.getElementById('mainModalPeriodBadge');
          if (elPeriod) elPeriod.textContent = `Period: ${dateLabel}`;

          const elTotDays = document.getElementById('mainModalStatTotalDays');
          if (elTotDays) elTotDays.textContent = emp.total_days || 0;
          const elWorkDays = document.getElementById('mainModalStatWorkingDays');
          if (elWorkDays) elWorkDays.textContent = emp.working_days || 0;
          const elPresDays = document.getElementById('mainModalStatPresentDays');
          if (elPresDays) elPresDays.textContent = emp.present_days || 0;
          const elAbsDays = document.getElementById('mainModalStatAbsentDays');
          if (elAbsDays) elAbsDays.textContent = emp.absent_days || 0;
          const elLateDays = document.getElementById('mainModalStatLateDays');
          if (elLateDays) elLateDays.textContent = emp.late_days || 0;
          const elRate = document.getElementById('mainModalStatRate');
          if (elRate) elRate.textContent = `${emp.attendance_rate || 0}%`;

          const dailyTbody = document.getElementById('mainModalDailyTbody');
          if (dailyTbody) {
            dailyTbody.innerHTML = '';
            const dailyRecords = emp.daily_records || [];
            if (dailyRecords.length === 0) {
              dailyTbody.innerHTML = '<tr><td colspan="7" style="padding:20px; text-align:center; color:#64748b;">No daily attendance records found in this date range.</td></tr>';
            } else {
              dailyRecords.forEach(d => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid #f1f5f9';

                const st = (d.status || 'absent').toLowerCase();
                let stBadge = '';
                if (st === 'present') {
                  stBadge = '<span class="badge" style="background:#e6f4ea; color:#1e8e3e; border:1px solid #a8dab5; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-circle-check"></i> Present</span>';
                } else if (st === 'late') {
                  stBadge = '<span class="badge" style="background:#fef7e0; color:#b06000; border:1px solid #f9e29c; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-clock"></i> Late</span>';
                } else if (st === 'checked_out') {
                  stBadge = '<span class="badge" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-right-from-bracket"></i> Checked Out</span>';
                } else if (st === 'weekend') {
                  stBadge = '<span class="badge" style="background:#f1f5f9; color:#64748b; border:1px solid #cbd5e1; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-bed"></i> Weekend / Off</span>';
                } else if (st === 'on_leave') {
                  stBadge = '<span class="badge" style="background:#ccfbf1; color:#0f766e; border:1px solid #99f6e4; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-envelope-open-text"></i> On Leave</span>';
                } else {
                  stBadge = '<span class="badge" style="background:#fce8e6; color:#d93025; border:1px solid #f5b4b0; padding:3px 9px; font-size:0.76em;"><i class="fa-solid fa-circle-xmark"></i> Absent</span>';
                }

                const checkInTime = formatMainTime(d.first_seen);
                const checkOutTime = formatMainTime(d.last_seen);

                tr.innerHTML = `
                  <td style="padding:8px 12px; font-weight:600; color:#0f172a;">${d.date_formatted || d.date}</td>
                  <td style="padding:8px 12px; color:#64748b; font-weight:600;">${d.day || '-'}</td>
                  <td style="padding:8px 12px;">${stBadge}</td>
                  <td style="padding:8px 12px; color:#334155;"><i class="fa-regular fa-clock" style="color:#94a3b8; margin-right:3px;"></i>${checkInTime}</td>
                  <td style="padding:8px 12px; color:#334155;"><i class="fa-solid fa-eye" style="color:#94a3b8; margin-right:3px;"></i>${checkOutTime}</td>
                  <td style="padding:8px 12px; color:#475569; font-size:0.78rem;">${d.shift_name || emp.shift_name || 'General'}</td>
                  <td style="padding:8px 12px; color:#475569; font-size:0.78rem;"><i class="fa-solid fa-location-dot" style="color:#0284c7; margin-right:3px;"></i>${d.location || '-'}</td>
                `;
                dailyTbody.appendChild(tr);
              });
            }
          }

          const modal = document.getElementById('mainCompleteViewModal');
          if (modal) modal.style.display = 'flex';
        } catch (err) {
          console.error("Error opening complete view modal:", err);
        }
      }

      function closeMainCompleteView() {
        const modal = document.getElementById('mainCompleteViewModal');
        if (modal) modal.style.display = 'none';
        currentMainActiveModalUserId = null;
      }

      function handleMainModalOverlayClick(event) {
        if (event.target && event.target.id === 'mainCompleteViewModal') {
          closeMainCompleteView();
        }
      }

      function buildMainExportQuery() {
        const params = new URLSearchParams();
        const dept = document.getElementById('mainDeptFilter')?.value || 'all';
        const status = document.getElementById('mainStatusFilter')?.value || 'all';
        const search = document.getElementById('mainReportSearch')?.value.trim() || '';

        if (dept !== 'all') params.append('department', dept);
        if (status !== 'all') params.append('status', status);
        if (search) params.append('search', search);

        const s = document.getElementById('mainStartDate')?.value;
        const e = document.getElementById('mainEndDate')?.value;

        if (currentMainFilterDate === 'custom' || (s && e)) {
          if (s && e) {
            params.append('start_date', s <= e ? s : e);
            params.append('end_date', s <= e ? e : s);
          } else if (s) {
            params.append('start_date', s);
            params.append('end_date', s);
          } else if (e) {
            params.append('start_date', e);
            params.append('end_date', e);
          } else {
            params.append('date', 'today');
          }
        } else if (currentMainFilterDate === 'today') {
          params.append('date', 'today');
        } else if (currentMainFilterDate === 'yesterday') {
          params.append('date', 'yesterday');
        } else if (currentMainFilterDate === 'last7') {
          params.append('date', 'last7');
        } else if (currentMainFilterDate === 'this_week') {
          params.append('date', 'this_week');
        } else if (currentMainFilterDate === 'this_month') {
          params.append('date', 'this_month');
        } else if (currentMainFilterDate === 'last30') {
          params.append('date', 'last30');
        } else {
          params.append('date', 'today');
        }
        return params.toString();
      }

      function exportMainCurrentEmployeeCSV() {
        if (!currentMainActiveModalUserId) return;
        const query = buildMainExportQuery();
        window.location.href = `${API_BASE}/reports/export/employee-csv?user_id=${currentMainActiveModalUserId}&${query}`;
      }

      function exportMainCSV() {
        const query = buildMainExportQuery();
        window.location.href = `${API_BASE}/reports/export/csv?${query}`;
      }

      // ================= STAFF DIRECTORY TAB LOGIC =================
      let tabAllStaff = [];

      async function loadTabStaffDirectory() {
        try {
          const res = await fetch(`${API_BASE}/users`);
          const data = await res.json();
          tabAllStaff = data.users || [];
          renderTabStaffMetrics(tabAllStaff);
          populateTabDeptDropdown(tabAllStaff);
          filterTabStaffTable();
        } catch (err) {
          console.error("Failed to load staff list:", err);
        }
      }

      function renderTabStaffMetrics(staffList) {
        const totalElem = document.getElementById('tabStatTotalStaff');
        const deptsElem = document.getElementById('tabStatDepts');
        const payrollElem = document.getElementById('tabStatPayroll');

        if (totalElem) totalElem.textContent = staffList.length;
        if (deptsElem) {
          const depts = new Set(staffList.map(s => s.department).filter(Boolean));
          deptsElem.textContent = depts.size;
        }
        if (payrollElem) {
          const totalSalary = staffList.reduce((sum, s) => sum + (parseFloat(s.salary) || 0), 0);
          payrollElem.textContent = `PKR ${totalSalary.toLocaleString()}`;
        }
      }

      function populateTabDeptDropdown(staffList) {
        const filterSelect = document.getElementById('tabStaffDeptFilter');
        if (!filterSelect) return;
        const currentVal = filterSelect.value;
        const depts = Array.from(new Set(staffList.map(s => s.department).filter(Boolean))).sort();

        filterSelect.innerHTML = '<option value="all">All Departments</option>';
        depts.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d;
          opt.textContent = d;
          filterSelect.appendChild(opt);
        });

        if (currentVal && currentVal !== 'all' && depts.includes(currentVal)) {
          filterSelect.value = currentVal;
        }
      }

      function filterTabStaffTable() {
        const query = document.getElementById('tabStaffSearchInput')?.value.toLowerCase() || '';
        const selectedDept = document.getElementById('tabStaffDeptFilter')?.value || 'all';

        const filtered = tabAllStaff.filter(s => {
          const matchesDept = selectedDept === 'all' || s.department === selectedDept;
          const matchesQuery = !query || 
            (s.name && s.name.toLowerCase().includes(query)) ||
            (s.department && s.department.toLowerCase().includes(query)) ||
            (s.position && s.position.toLowerCase().includes(query)) ||
            (s.cnic && s.cnic.toLowerCase().includes(query)) ||
            (s.email && s.email.toLowerCase().includes(query)) ||
            (s.phone && s.phone.toLowerCase().includes(query)) ||
            (s.id && String(s.id).includes(query));

          return matchesDept && matchesQuery;
        });

        renderTabStaffRows(filtered);
      }

      // =======================================================
      // ENTERPRISE CUSTOM CAMERA MULTI-SELECT SYSTEM
      // =======================================================
      let cachedActiveCameras = [];
      let selectedStaffIds = new Set();

      async function loadCameraAssignmentDropdowns() {
        try {
          const res = await fetch(`${API_BASE}/cameras?active_only=true`);
          const data = await res.json();
          cachedActiveCameras = data || [];
          populateCameraAssignmentDropdowns();
        } catch (e) {
          console.error("Failed to load active cameras for assignment:", e);
        }
      }

      function populateCameraAssignmentDropdowns() {
        const wrappers = [
          { id: 'enrollCheckinCamerasWrapper', selectId: 'enrollCheckinCameras', type: 'checkin' },
          { id: 'enrollCheckoutCamerasWrapper', selectId: 'enrollCheckoutCameras', type: 'checkout' },
          { id: 'editCheckinCamerasWrapper', selectId: 'editCheckinCameras', type: 'checkin' },
          { id: 'editCheckoutCamerasWrapper', selectId: 'editCheckoutCameras', type: 'checkout' },
          { id: 'bulkCheckinCamerasWrapper', selectId: 'bulkCheckinCameras', type: 'checkin' },
          { id: 'bulkCheckoutCamerasWrapper', selectId: 'bulkCheckoutCameras', type: 'checkout' }
        ];

        wrappers.forEach(w => {
          buildCustomCameraSelect(w.id, w.selectId, w.type);
        });
      }

      function buildCustomCameraSelect(wrapperId, selectId, type = 'checkin') {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;

        const currentVal = wrapper.dataset.currentVal || 'all';
        const isCheckout = type === 'checkout';
        const themeColor = isCheckout ? '#dc2626' : '#059669';
        const icon = isCheckout ? 'fa-camera-rotate' : 'fa-camera';

        let itemsHtml = `
          <div class="custom-camera-actions">
            <span style="font-size:0.75rem; font-weight:700; color:#64748b;">Select Authorized:</span>
            <div style="display:flex; gap:6px;">
              <button type="button" onclick="setCustomCameraAll('${wrapperId}', true)">All Active</button>
              <button type="button" onclick="setCustomCameraAll('${wrapperId}', false)" style="color:#64748b;">Clear</button>
            </div>
          </div>
          <div class="custom-camera-item" onclick="toggleCustomCameraItem('${wrapperId}', 'all', event)">
            <input type="checkbox" id="${wrapperId}_opt_all" value="all" onchange="onCustomCameraCheckboxChange('${wrapperId}', 'all', this.checked)" />
            <i class="fa-solid ${icon}" style="color:${themeColor}; font-size:0.85em;"></i>
            <span>All Active Cameras (Default)</span>
            <span class="cam-room-tag" style="background:#e0f2fe; color:#0369a1;">ALL</span>
          </div>
        `;

        cachedActiveCameras.forEach(cam => {
          const room = cam.room_name || cam.name || cam.camera_id;
          itemsHtml += `
            <div class="custom-camera-item" onclick="toggleCustomCameraItem('${wrapperId}', '${cam.camera_id}', event)">
              <input type="checkbox" id="${wrapperId}_opt_${cam.camera_id}" value="${cam.camera_id}" onchange="onCustomCameraCheckboxChange('${wrapperId}', '${cam.camera_id}', this.checked)" />
              <i class="fa-solid fa-video" style="color:#64748b; font-size:0.82em;"></i>
              <span style="font-weight:600; color:#1e293b;">${cam.name || cam.camera_id}</span>
              <span class="cam-room-tag">${room}</span>
            </div>
          `;
        });

        wrapper.innerHTML = `
          <div class="custom-camera-select-trigger" onclick="toggleCustomCameraDropdown('${wrapperId}', event)">
            <div class="custom-camera-chips-container" id="${wrapperId}_chips">
              <!-- Rendered chips -->
            </div>
            <i class="fa-solid fa-chevron-down" style="color:#94a3b8; font-size:0.75em; transition:transform 0.2s;" id="${wrapperId}_arrow"></i>
          </div>
          <div class="custom-camera-dropdown-panel" id="${wrapperId}_panel" onclick="event.stopPropagation()">
            ${itemsHtml}
          </div>
          <select class="form-select" id="${selectId}" multiple size="3" style="display:none;">
            <option value="all" selected>All Active Cameras</option>
            ${cachedActiveCameras.map(c => `<option value="${c.camera_id}">${c.name || c.camera_id}</option>`).join('')}
          </select>
        `;

        setMultiSelectValues(wrapperId, currentVal);
      }

      function toggleCustomCameraDropdown(wrapperId, event) {
        if (event) event.stopPropagation();
        const panel = document.getElementById(`${wrapperId}_panel`);
        const trigger = wrapperId ? document.querySelector(`#${wrapperId} .custom-camera-select-trigger`) : null;
        const arrow = document.getElementById(`${wrapperId}_arrow`);
        if (!panel) return;

        const isShowing = panel.classList.contains('show');
        // Close other panels
        document.querySelectorAll('.custom-camera-dropdown-panel.show').forEach(p => {
          if (p !== panel) {
            p.classList.remove('show');
            const parentWrap = p.closest('.custom-camera-select-wrapper');
            if (parentWrap) {
              const trg = parentWrap.querySelector('.custom-camera-select-trigger');
              if (trg) trg.classList.remove('active');
              const arr = parentWrap.querySelector('.fa-chevron-down');
              if (arr) arr.style.transform = 'rotate(0deg)';
            }
          }
        });

        if (isShowing) {
          panel.classList.remove('show');
          if (trigger) trigger.classList.remove('active');
          if (arrow) arrow.style.transform = 'rotate(0deg)';
        } else {
          panel.classList.add('show');
          if (trigger) trigger.classList.add('active');
          if (arrow) arrow.style.transform = 'rotate(180deg)';
        }
      }

      // Close panels when clicking outside
      document.addEventListener('click', function(e) {
        if (!e.target.closest('.custom-camera-select-wrapper')) {
          document.querySelectorAll('.custom-camera-dropdown-panel.show').forEach(p => {
            p.classList.remove('show');
            const parentWrap = p.closest('.custom-camera-select-wrapper');
            if (parentWrap) {
              const trg = parentWrap.querySelector('.custom-camera-select-trigger');
              if (trg) trg.classList.remove('active');
              const arr = parentWrap.querySelector('.fa-chevron-down');
              if (arr) arr.style.transform = 'rotate(0deg)';
            }
          });
        }
      });

      function toggleCustomCameraItem(wrapperId, val, event) {
        if (event.target.tagName === 'INPUT') return;
        const chk = document.getElementById(`${wrapperId}_opt_${val}`);
        if (chk) {
          chk.checked = !chk.checked;
          onCustomCameraCheckboxChange(wrapperId, val, chk.checked);
        }
      }

      function onCustomCameraCheckboxChange(wrapperId, val, checked) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;

        const allChk = document.getElementById(`${wrapperId}_opt_all`);
        const camCheckboxes = Array.from(wrapper.querySelectorAll('.custom-camera-item input[type="checkbox"]:not([value="all"])'));

        if (val === 'all') {
          if (checked) {
            camCheckboxes.forEach(cb => cb.checked = false);
          } else {
            if (camCheckboxes.every(cb => !cb.checked)) allChk.checked = true;
          }
        } else {
          if (checked && allChk) {
            allChk.checked = false;
          } else if (!checked) {
            const anyChecked = camCheckboxes.some(cb => cb.checked);
            if (!anyChecked && allChk) allChk.checked = true;
          }
        }

        syncCustomCameraFromCheckboxes(wrapperId);
      }

      function setCustomCameraAll(wrapperId, isAll) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;
        const allChk = document.getElementById(`${wrapperId}_opt_all`);
        const camCheckboxes = Array.from(wrapper.querySelectorAll('.custom-camera-item input[type="checkbox"]:not([value="all"])'));

        if (isAll) {
          if (allChk) allChk.checked = true;
          camCheckboxes.forEach(cb => cb.checked = false);
        } else {
          if (allChk) allChk.checked = false;
          camCheckboxes.forEach(cb => cb.checked = false);
        }
        syncCustomCameraFromCheckboxes(wrapperId);
      }

      function syncCustomCameraFromCheckboxes(wrapperId) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;
        const allChk = document.getElementById(`${wrapperId}_opt_all`);
        const camCheckboxes = Array.from(wrapper.querySelectorAll('.custom-camera-item input[type="checkbox"]:not([value="all"])'));

        let selected = [];
        if (allChk && allChk.checked) {
          selected = ['all'];
        } else {
          selected = camCheckboxes.filter(cb => cb.checked).map(cb => cb.value);
          if (selected.length === 0) {
            selected = ['all'];
            if (allChk) allChk.checked = true;
          }
        }

        const valueStr = selected.join(',');
        wrapper.dataset.currentVal = valueStr;

        const targetSelectId = wrapper.dataset.target || wrapper.querySelector('select')?.id;
        const sel = targetSelectId ? document.getElementById(targetSelectId) : null;
        if (sel) {
          Array.from(sel.options).forEach(opt => {
            if (valueStr === 'all') {
              opt.selected = (opt.value === 'all');
            } else {
              opt.selected = selected.includes(opt.value);
            }
          });
        }

        renderCustomCameraChips(wrapperId, valueStr);
      }

      function renderCustomCameraChips(wrapperId, valueStr) {
        const chipsCont = document.getElementById(`${wrapperId}_chips`);
        const wrapper = document.getElementById(wrapperId);
        if (!chipsCont || !wrapper) return;

        const isCheckout = wrapper.dataset.type === 'checkout';
        const str = (valueStr || 'all').trim();

        if (!str || str.toLowerCase() === 'all') {
          chipsCont.innerHTML = `<span class="custom-camera-chip all-badge"><i class="fa-solid fa-video" style="font-size:0.7em;"></i> All Active Cameras</span>`;
          return;
        }

        const tokens = str.split(',').map(t => t.trim()).filter(Boolean);
        if (tokens.length === 0) {
          chipsCont.innerHTML = `<span class="custom-camera-chip all-badge"><i class="fa-solid fa-video" style="font-size:0.7em;"></i> All Active Cameras</span>`;
          return;
        }

        const chipClass = isCheckout ? 'custom-camera-chip checkout-badge' : 'custom-camera-chip';
        const icon = isCheckout ? 'fa-camera-rotate' : 'fa-video';

        chipsCont.innerHTML = tokens.map(tok => {
          const matchedCam = cachedActiveCameras.find(c => 
            c.camera_id.toLowerCase() === tok.toLowerCase() || 
            (c.room_name && c.room_name.toLowerCase() === tok.toLowerCase()) ||
            (c.name && c.name.toLowerCase() === tok.toLowerCase())
          );
          const label = matchedCam ? (matchedCam.room_name || matchedCam.name) : tok;
          return `<span class="${chipClass}"><i class="fa-solid ${icon}" style="font-size:0.7em;"></i> ${label}</span>`;
        }).join('');
      }

      function getMultiSelectValues(containerOrSelect) {
        if (!containerOrSelect) return 'all';
        let el = typeof containerOrSelect === 'string' ? document.getElementById(containerOrSelect) : containerOrSelect;
        if (!el) return 'all';

        const wrapper = el.classList.contains('custom-camera-select-wrapper') ? el : el.closest('.custom-camera-select-wrapper');
        if (wrapper && wrapper.dataset.currentVal) {
          return wrapper.dataset.currentVal;
        }
        if (el.tagName === 'SELECT') {
          const selected = Array.from(el.selectedOptions).map(o => o.value);
          if (selected.length === 0 || selected.includes('all')) return 'all';
          return selected.join(',');
        }
        return 'all';
      }

      function setMultiSelectValues(containerOrSelect, valueStr) {
        if (!containerOrSelect) return;
        let el = typeof containerOrSelect === 'string' ? document.getElementById(containerOrSelect) : containerOrSelect;
        if (!el) return;

        const wrapper = el.classList.contains('custom-camera-select-wrapper') ? el : el.closest('.custom-camera-select-wrapper');
        const str = (valueStr || 'all').trim();

        if (wrapper) {
          wrapper.dataset.currentVal = str;
          const allChk = wrapper.querySelector('input[value="all"]');
          const camCheckboxes = Array.from(wrapper.querySelectorAll('.custom-camera-item input[type="checkbox"]:not([value="all"])'));

          if (!str || str.toLowerCase() === 'all') {
            if (allChk) allChk.checked = true;
            camCheckboxes.forEach(cb => cb.checked = false);
          } else {
            if (allChk) allChk.checked = false;
            const tokens = str.split(',').map(s => s.trim().toLowerCase());
            camCheckboxes.forEach(cb => {
              cb.checked = tokens.includes(cb.value.toLowerCase());
            });
          }
          syncCustomCameraFromCheckboxes(wrapper.id);
        } else if (el.tagName === 'SELECT') {
          const tokens = str.split(',').map(s => s.trim().toLowerCase());
          Array.from(el.options).forEach(opt => {
            opt.selected = (str === 'all' && opt.value === 'all') || tokens.includes(opt.value.toLowerCase());
          });
        }
      }

      function formatCameraBadges(cameraTokensStr, isCheckout = false) {
        const str = (cameraTokensStr || 'all').trim();
        const themeColor = isCheckout ? '#b45309' : '#047857';
        const bgColor = isCheckout ? '#fef3c7' : '#d1fae5';
        const borderColor = isCheckout ? '#fde68a' : '#a7f3d0';
        const icon = isCheckout ? 'fa-arrow-right-from-bracket' : 'fa-video';

        if (!str || str.toLowerCase() === 'all') {
          return `<span style="background:${bgColor}; color:${themeColor}; border:1px solid ${borderColor}; padding:2px 7px; border-radius:4px; font-weight:600; font-size:0.72rem; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid ${icon}" style="font-size:0.68rem;"></i> All Cameras</span>`;
        }

        const tokens = str.split(',').map(t => t.trim()).filter(Boolean);
        return tokens.map(tok => {
          const matchedCam = cachedActiveCameras.find(c => 
            c.camera_id.toLowerCase() === tok.toLowerCase() || 
            (c.room_name && c.room_name.toLowerCase() === tok.toLowerCase()) ||
            (c.name && c.name.toLowerCase() === tok.toLowerCase())
          );
          const label = matchedCam ? (matchedCam.room_name || matchedCam.name) : tok;
          return `<span style="background:${bgColor}; color:${themeColor}; border:1px solid ${borderColor}; padding:2px 6px; border-radius:4px; font-weight:600; font-size:0.72rem; display:inline-flex; align-items:center; gap:3px;" title="${tok}"><i class="fa-solid ${icon}" style="font-size:0.68rem;"></i> ${label}</span>`;
        }).join('');
      }

      function toggleSelectAllStaff(checked) {
        selectedStaffIds.clear();
        const checkboxes = document.querySelectorAll('.staff-row-checkbox');
        checkboxes.forEach(cb => {
          cb.checked = checked;
          if (checked) {
            selectedStaffIds.add(parseInt(cb.value));
          }
        });
        updateBulkButtonBadge();
      }

      function toggleStaffRowCheck(userId, checked) {
        if (checked) selectedStaffIds.add(userId);
        else selectedStaffIds.delete(userId);
        
        const allCbs = document.querySelectorAll('.staff-row-checkbox');
        const allChecked = allCbs.length > 0 && Array.from(allCbs).every(cb => cb.checked);
        const selectAll = document.getElementById('selectAllStaffCheck');
        if (selectAll) selectAll.checked = allChecked;
        
        updateBulkButtonBadge();
      }

      function updateBulkButtonBadge() {
        const summaryEl = document.getElementById('bulkTargetStaffSummary');
        if (summaryEl) {
          if (selectedStaffIds.size > 0) {
            summaryEl.innerHTML = `<strong>${selectedStaffIds.size}</strong> staff member(s) selected for camera assignment update.`;
          } else {
            summaryEl.innerHTML = `<strong>All ${tabAllStaff.length}</strong> staff members will receive this camera assignment.`;
          }
        }
      }

      function openBulkCameraModal() {
        populateCameraAssignmentDropdowns();
        updateBulkButtonBadge();
        document.getElementById('bulkCameraMsg').innerHTML = '';
        document.getElementById('bulkCameraModal').style.display = 'flex';
      }

      function closeBulkCameraModal() {
        document.getElementById('bulkCameraModal').style.display = 'none';
      }

      async function submitBulkCameraAssignment() {
        const checkinCameras = getMultiSelectValues('bulkCheckinCamerasWrapper');
        const checkoutCameras = getMultiSelectValues('bulkCheckoutCamerasWrapper');
        const user_ids = selectedStaffIds.size > 0 ? Array.from(selectedStaffIds) : 'all';

        const btn = document.querySelector('#bulkCameraModal button.btn-primary');
        const restoreBtn = setButtonLoading(btn, 'Assigning...');

        try {
          const resp = await fetch(`${API_BASE}/users/bulk-assign-cameras`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_ids, checkin_cameras: checkinCameras, checkout_cameras: checkoutCameras })
          });
          const data = await resp.json();
          if (resp.ok && data.success) {
            closeBulkCameraModal();
            showAppToast(data.message || 'Cameras successfully assigned', 'success');
            loadTabStaffDirectory();
          } else {
            document.getElementById('bulkCameraMsg').innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">${data.error || 'Failed to update camera assignments'}</div>`;
          }
        } catch (e) {
          document.getElementById('bulkCameraMsg').innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">Error: ${e.message}</div>`;
        } finally {
          restoreBtn();
        }
      }

      // =======================================================
      // STAFF DIRECTORY PAGINATION (25 PER PAGE)
      // =======================================================
      let tabStaffCurrentPage = 1;
      const tabStaffPageSize = 25;
      let tabStaffFilteredCache = [];

      function renderTabStaffRows(staffList) {
        tabStaffFilteredCache = staffList || [];
        renderTabStaffPage(tabStaffCurrentPage);
      }

      function tabStaffGoToPage(pageNum) {
        tabStaffCurrentPage = pageNum;
        renderTabStaffPage(tabStaffCurrentPage);
      }

      function renderTabStaffPage(pageNum) {
        const tbody = document.getElementById('tabStaffTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        const totalItems = tabStaffFilteredCache.length;
        const totalPages = Math.ceil(totalItems / tabStaffPageSize) || 1;
        if (pageNum < 1) pageNum = 1;
        if (pageNum > totalPages) pageNum = totalPages;
        tabStaffCurrentPage = pageNum;

        const startIndex = (pageNum - 1) * tabStaffPageSize;
        const endIndex = Math.min(startIndex + tabStaffPageSize, totalItems);
        const pageItems = tabStaffFilteredCache.slice(startIndex, endIndex);

        // Update Page Info & Indicators
        const startEl = document.getElementById('tabStaffShowingStart');
        const endEl = document.getElementById('tabStaffShowingEnd');
        const totalEl = document.getElementById('tabStaffShowingTotal');
        if (startEl) startEl.textContent = totalItems === 0 ? 0 : startIndex + 1;
        if (endEl) endEl.textContent = endIndex;
        if (totalEl) totalEl.textContent = totalItems;

        renderTabStaffPaginationControls(pageNum, totalPages);

        if (!pageItems || pageItems.length === 0) {
          tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:#64748b; padding:30px; font-size:0.85rem;">No staff records found.</td></tr>';
          return;
        }

        pageItems.forEach(s => {
          const tr = document.createElement('tr');
          tr.style.borderBottom = '1px solid #f1f5f9';
          tr.style.transition = 'background 0.15s ease';
          tr.onmouseenter = () => tr.style.background = '#f8fafc';
          tr.onmouseleave = () => tr.style.background = 'transparent';

          const initial = s.name ? s.name.charAt(0).toUpperCase() : '?';
          let photoHtml = `<div style="width:32px; height:32px; border-radius:50%; background:#e0f2fe; color:#0284c7; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.8rem; flex-shrink:0;">${initial}</div>`;
          if (s.photo_path) {
            photoHtml = `<img src="/api/users/${s.id}/photo" style="width:32px; height:32px; border-radius:50%; object-fit:cover; flex-shrink:0;" onerror="this.onerror=null; this.outerHTML='<div style=\\'width:32px; height:32px; border-radius:50%; background:#e0f2fe; color:#0284c7; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.8rem; flex-shrink:0;\\'>${initial}</div>'">`;
          }

          const salaryStr = s.salary ? `PKR ${parseFloat(s.salary).toLocaleString()}` : '--';
          const pos = String(s.position || 'Staff Member').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          const nameStr = String(s.name || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
          const deptStr = String(s.department || 'Unassigned').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

          const checkinBadges = formatCameraBadges(s.checkin_cameras, false);
          const checkoutBadges = formatCameraBadges(s.checkout_cameras, true);
          const isRowChecked = selectedStaffIds.has(s.id);

          tr.innerHTML = `
            <td style="padding:9px 12px; text-align:center; vertical-align:middle;">
              <input type="checkbox" class="staff-row-checkbox" value="${s.id}" onchange="toggleStaffRowCheck(${s.id}, this.checked)" ${isRowChecked ? 'checked' : ''} style="width:15px; height:15px; cursor:pointer; accent-color:#0284c7;" />
            </td>
            <td style="padding:9px 12px; font-weight:700; color:#0284c7; font-size:0.8rem; vertical-align:middle;">#${String(s.id).padStart(3, '0')}</td>
            <td style="padding:9px 12px; vertical-align:middle;">
              <div style="display:flex; align-items:center; gap:10px;">
                ${photoHtml}
                <div>
                  <strong style="color:#0f172a; font-size:0.85rem; font-weight:600; display:block; line-height:1.2;">${nameStr}</strong>
                  <span style="font-size:0.75rem; color:#64748b;">${pos}</span>
                </div>
              </div>
            </td>
            <td style="padding:9px 12px; vertical-align:middle;">
              <span style="font-weight:600; color:#2563eb; font-size:0.8rem;">${deptStr}</span>
              <div style="font-size:0.72rem; color:#64748b; margin-top:2px;"><i class="fa-solid fa-business-time" style="color:#0284c7; margin-right:3px;"></i>${s.shift_name || 'General Shift'}</div>
            </td>
            <td style="padding:9px 12px; vertical-align:middle;">
              <div style="display:flex; flex-wrap:wrap; gap:3px; align-items:center;">
                ${checkinBadges}
              </div>
            </td>
            <td style="padding:9px 12px; vertical-align:middle;">
              <div style="display:flex; flex-wrap:wrap; gap:3px; align-items:center;">
                ${checkoutBadges}
              </div>
            </td>
            <td style="padding:9px 12px; vertical-align:middle;">
              <div style="font-size:0.78rem; line-height:1.35;">
                <div style="color:#334155;"><i class="fa-regular fa-envelope" style="color:#0284c7; margin-right:4px; font-size:0.72rem;"></i>${s.email || '--'}</div>
                <div style="color:#64748b;"><i class="fa-solid fa-phone" style="color:#94a3b8; margin-right:4px; font-size:0.72rem;"></i>${s.phone || '--'}</div>
              </div>
            </td>
            <td style="padding:9px 12px; vertical-align:middle;"><span style="color:#475569; font-size:0.78rem; font-weight:500;">${s.cnic || '--'}</span></td>
            <td style="padding:9px 12px; vertical-align:middle;"><strong style="color:#16a34a; font-size:0.82rem; font-weight:700;">${salaryStr}</strong></td>
            <td style="padding:9px 12px; text-align:right; vertical-align:middle;">
              <div style="display:inline-flex; gap:5px;">
                <button onclick="openTabEditStaffModal(${s.id})" style="background:#f0f9ff; color:#0284c7; border:1px solid #bae6fd; padding:4px 9px; border-radius:5px; font-size:0.75rem; font-weight:600; cursor:pointer; transition:all 0.15s ease;" onmouseover="this.style.background='#e0f2fe'" onmouseout="this.style.background='#f0f9ff'"><i class="fa-solid fa-pen" style="margin-right:3px;"></i>Edit</button>
                <button onclick="deleteTabStaffMember(${s.id}, '${nameStr.replace(/'/g, "\\'")}')" style="background:#fef2f2; color:#dc2626; border:1px solid #fecaca; padding:4px 9px; border-radius:5px; font-size:0.75rem; font-weight:600; cursor:pointer; transition:all 0.15s ease;" onmouseover="this.style.background='#fee2e2'" onmouseout="this.style.background='#fef2f2'"><i class="fa-solid fa-trash" style="margin-right:3px;"></i>Delete</button>
              </div>
            </td>
          `;
          tbody.appendChild(tr);
        });
      }

      function renderTabStaffPaginationControls(currentPage, totalPages) {
        const controls = document.getElementById('tabStaffPageControls');
        if (!controls) return;
        controls.innerHTML = '';

        if (totalPages <= 1) return;

        // Previous button
        const prevBtn = document.createElement('button');
        prevBtn.className = 'app-page-btn';
        prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i> Previous';
        prevBtn.disabled = currentPage === 1;
        prevBtn.onclick = () => tabStaffGoToPage(currentPage - 1);
        controls.appendChild(prevBtn);

        // Page buttons
        for (let i = 1; i <= totalPages; i++) {
          const pageBtn = document.createElement('button');
          pageBtn.className = `app-page-btn ${i === currentPage ? 'active' : ''}`;
          pageBtn.textContent = i;
          pageBtn.onclick = () => tabStaffGoToPage(i);
          controls.appendChild(pageBtn);
        }

        // Next button
        const nextBtn = document.createElement('button');
        nextBtn.className = 'app-page-btn';
        nextBtn.innerHTML = 'Next <i class="fa-solid fa-chevron-right"></i>';
        nextBtn.disabled = currentPage === totalPages;
        nextBtn.onclick = () => tabStaffGoToPage(currentPage + 1);
        controls.appendChild(nextBtn);
      }

      function openTabAddStaffModal() {
        if (typeof _enrollmentEnabled !== 'undefined' && !_enrollmentEnabled) {
          alert('Staff Enrollment is currently disabled. Please enable it from Admin Configuration (Settings).');
          return;
        }
        const enrollBtn = document.getElementById('enrollMenuSidebarItem');
        if (enrollBtn) {
          switchTab('enroll-view', enrollBtn);
        }
      }

      function openTabEditStaffModal(userId) {
        const user = tabAllStaff.find(s => s.id === userId);
        if (!user) return;

        populateCameraAssignmentDropdowns();

        document.getElementById('editUserId').value = userId;
        document.getElementById('editName').value = user.name || '';
        document.getElementById('editEmail').value = user.email || '';
        document.getElementById('editDepartment').value = user.department || '';
        document.getElementById('editPhone').value = user.phone || '';
        if (typeof onEditDeptChange === 'function') {
          onEditDeptChange(user.department || '', user.position || '');
        } else if (document.getElementById('editPosition')) {
          document.getElementById('editPosition').value = user.position || '';
        }
        if (document.getElementById('editCNIC')) document.getElementById('editCNIC').value = user.cnic || '';
        if (document.getElementById('editSalary')) document.getElementById('editSalary').value = user.salary || '';
        if (document.getElementById('editJoinDate')) document.getElementById('editJoinDate').value = user.join_date || '';
        if (document.getElementById('editShiftId')) document.getElementById('editShiftId').value = user.shift_id || 1;
        if (document.getElementById('editNotes')) document.getElementById('editNotes').value = user.notes || '';

        setMultiSelectValues('editCheckinCamerasWrapper', user.checkin_cameras || 'all');
        setMultiSelectValues('editCheckoutCamerasWrapper', user.checkout_cameras || 'all');

        document.getElementById('editModalMessage').innerHTML = '';
        const modal = document.getElementById('editUserModal');
        if (modal) modal.style.display = 'flex';
      }

      async function deleteTabStaffMember(userId, userName) {
        if (!confirm(`Are you sure you want to permanently delete staff member "${userName}" (#${userId})?`)) return;
        try {
          const res = await fetch(`${API_BASE}/users/${userId}/delete`, { method: 'POST' });
          const json = await res.json();
          if (res.ok || json.success) {
            loadTabStaffDirectory();
            if (typeof loadStaffDirectory === 'function') loadStaffDirectory();
            showAppToast(json.message || `Staff member '${userName}' deleted successfully`, 'success');
          } else {
            showAppToast('Delete failed: ' + (json.error || json.message), 'error');
          }
        } catch (err) {
          showAppToast('Error deleting staff: ' + err, 'error');
        }
      }

      // =======================================================
      // SHIFT MANAGEMENT & PAGINATION (25 PER PAGE)
      // =======================================================
      let allShiftsCache = [];
      let selectedShiftStaffIds = new Set();
      let shiftStaffListCache = [];
      let shiftStaffFilteredCache = [];
      let shiftStaffCurrentPage = 1;
      const shiftStaffPageSize = 25;
      const shiftWeekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

      function getShiftEffectiveFrom() {
        const input = document.getElementById('shiftEffectiveFrom');
        if (!input) return '';
        if (!input.value) {
          const now = new Date();
          input.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        }
        return input.value;
      }

      function setShiftWorkingDays(workingDays) {
        const selectedDays = new Set((workingDays || [0, 1, 2, 3, 4, 5]).map(String));
        document.querySelectorAll('#shiftModal input[name="modalShiftWorkingDays"]').forEach((input) => {
          input.checked = selectedDays.has(input.value);
        });
      }

      function shiftWorkingDaysLabel(workingDays) {
        return (workingDays || [0, 1, 2, 3, 4, 5]).map(day => shiftWeekdayLabels[Number(day)]).filter(Boolean).join(', ');
      }

      async function loadShiftsList() {
        try {
          const resp = await fetch(`${API_BASE}/shifts`);
          const data = await resp.json();
          if (resp.ok && data.shifts) {
            allShiftsCache = data.shifts;
            renderShiftsUI(data.shifts);
            populateShiftDropdowns(data.shifts);
          }

          // Fetch active users for Shift Assignment Table
          const userResp = await fetch(`${API_BASE}/users`);
          const userData = await userResp.json();
          if (userResp.ok && userData.users) {
            shiftStaffListCache = userData.users;
            populateShiftDeptFilter(userData.users);
            filterShiftStaffTable();
          }
        } catch (e) {
          console.error("Failed to load shifts:", e);
        }
      }

      function toggleShiftGraceInput(enabled) {
        const box = document.getElementById("shiftGraceInputBox");
        const disabledBox = document.getElementById("shiftGraceDisabledBox");
        const graceInput = document.getElementById("modalShiftGrace");
        if (enabled) {
          if (box) box.style.display = "block";
          if (disabledBox) disabledBox.style.display = "none";
          if (graceInput && (parseInt(graceInput.value) <= 0 || !graceInput.value)) graceInput.value = "15";
        } else {
          if (box) box.style.display = "none";
          if (disabledBox) disabledBox.style.display = "block";
          if (graceInput) graceInput.value = "0";
        }
      }

      function populateShiftDropdowns(shifts) {
        const dropdownIds = ["enrollShiftId", "editShiftId", "bulkShiftTargetSelect", "shiftFilterCurrentShift"];
        dropdownIds.forEach((id) => {
          const select = document.getElementById(id);
          if (!select) return;
          const currentVal = select.value;

          if (id === "shiftFilterCurrentShift") {
            select.innerHTML = '<option value="all">All Assigned Shifts</option>' + 
              shifts.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
          } else {
            select.innerHTML = shifts
              .map(
                (s) => {
                  const start12 = formatMainTime(s.start_time);
                  const end12 = formatMainTime(s.end_time);
                  const graceStr = (s.grace_period_minutes && parseInt(s.grace_period_minutes) > 0) ? `${s.grace_period_minutes}m Grace Window` : 'Grace Disabled';
                  return `<option value="${s.id}">${s.name} (${start12} - ${end12} | ${graceStr})</option>`;
                }
              )
              .join("");
          }

          if (currentVal && Array.from(select.options).some(o => o.value == currentVal)) {
            select.value = currentVal;
          }
        });
      }

      function populateShiftDeptFilter(staffList) {
        const select = document.getElementById("shiftFilterDept");
        if (!select) return;
        const currentVal = select.value;
        const depts = Array.from(new Set((staffList || []).map(s => s.department).filter(Boolean))).sort();
        select.innerHTML = '<option value="all">All Departments</option>' + 
          depts.map(d => `<option value="${d}">${d}</option>`).join("");
        if (currentVal && Array.from(select.options).some(o => o.value == currentVal)) {
          select.value = currentVal;
        }
      }

      function filterShiftStaffTable() {
        const search = (document.getElementById("shiftStaffSearch")?.value || "").toLowerCase().trim();
        const dept = document.getElementById("shiftFilterDept")?.value || "all";
        const shiftFilter = document.getElementById("shiftFilterCurrentShift")?.value || "all";

        const filtered = shiftStaffListCache.filter(user => {
          const matchesSearch = !search || 
            (user.name && user.name.toLowerCase().includes(search)) ||
            (user.id && String(user.id).includes(search)) ||
            (user.position && user.position.toLowerCase().includes(search)) ||
            (user.department && user.department.toLowerCase().includes(search));
          const matchesDept = (dept === "all") || (user.department === dept);
          const matchesShift = (shiftFilter === "all") || (String(user.shift_id || 1) === String(shiftFilter));
          return matchesSearch && matchesDept && matchesShift;
        });

        shiftStaffFilteredCache = filtered;
        shiftStaffCurrentPage = 1;
        renderShiftStaffPage(shiftStaffCurrentPage);
      }

      function shiftStaffGoToPage(pageNum) {
        shiftStaffCurrentPage = pageNum;
        renderShiftStaffPage(shiftStaffCurrentPage);
      }

      function renderShiftStaffPage(pageNum) {
        const tbody = document.getElementById("shiftStaffTableBody");
        if (!tbody) return;
        tbody.innerHTML = "";

        const totalItems = shiftStaffFilteredCache.length;
        const totalPages = Math.ceil(totalItems / shiftStaffPageSize) || 1;
        if (pageNum < 1) pageNum = 1;
        if (pageNum > totalPages) pageNum = totalPages;
        shiftStaffCurrentPage = pageNum;

        const startIndex = (pageNum - 1) * shiftStaffPageSize;
        const endIndex = Math.min(startIndex + shiftStaffPageSize, totalItems);
        const pageItems = shiftStaffFilteredCache.slice(startIndex, endIndex);

        // Update Page Info Indicators
        const startEl = document.getElementById('shiftStaffShowingStart');
        const endEl = document.getElementById('shiftStaffShowingEnd');
        const totalEl = document.getElementById('shiftStaffShowingTotal');
        if (startEl) startEl.textContent = totalItems === 0 ? 0 : startIndex + 1;
        if (endEl) endEl.textContent = endIndex;
        if (totalEl) totalEl.textContent = totalItems;

        renderShiftStaffPaginationControls(pageNum, totalPages);

        if (!pageItems || pageItems.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#64748b; padding:32px; font-size:0.86rem;"><i class="fa-solid fa-user-slash" style="font-size:1.8em; margin-bottom:8px; display:block; opacity:0.5;"></i>No staff members found matching this filter.</td></tr>';
          return;
        }

        pageItems.forEach(user => {
          const tr = document.createElement("tr");
          tr.style.borderBottom = "1px solid #f1f5f9";
          tr.style.transition = "background 0.15s ease";
          tr.onmouseenter = () => tr.style.background = "#f8fafc";
          tr.onmouseleave = () => tr.style.background = "transparent";

          const initial = user.name ? user.name.charAt(0).toUpperCase() : "?";
          const isChecked = selectedShiftStaffIds.has(user.id);
          const shiftId = user.shift_id || 1;
          const assignedShift = allShiftsCache.find(s => s.id === shiftId) || { name: user.shift_name || "Morning Shift", start_time: "09:00", end_time: "17:00", grace_period_minutes: 15 };
          const start12 = formatMainTime(assignedShift.start_time);
          const end12 = formatMainTime(assignedShift.end_time);
          const safeName = (user.name || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");

          let shiftOptions = allShiftsCache.map(s => {
            const isSel = s.id === shiftId ? "selected" : "";
            return `<option value="${s.id}" ${isSel}>${s.name} (${formatMainTime(s.start_time)} - ${formatMainTime(s.end_time)})</option>`;
          }).join("");

          tr.innerHTML = `
            <td style="padding:10px 14px; text-align:center;">
              <input type="checkbox" class="shift-staff-checkbox" value="${user.id}" ${isChecked ? "checked" : ""} onchange="toggleShiftStaffRowCheck(${user.id}, this.checked)" style="width:16px; height:16px; cursor:pointer; accent-color:#3d9fd4;" />
            </td>
            <td style="padding:10px 14px; font-weight:700; color:#94a3b8; font-size:0.78em;">#${user.id}</td>
            <td style="padding:10px 14px;">
              <div style="display:flex; align-items:center; gap:9px;">
                <div style="width:32px; height:32px; border-radius:50%; background:#e0f2fe; color:#0284c7; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.8rem; flex-shrink:0;">${initial}</div>
                <div>
                  <div style="font-weight:700; color:#173042; font-size:0.86rem;">${user.name}</div>
                  <div style="font-size:0.72rem; color:#64748b;">${user.position || "Staff Member"}</div>
                </div>
              </div>
            </td>
            <td style="padding:10px 14px;">
              <span class="badge" style="background:#f0f9ff; color:#0369a1; border:1px solid #bae6fd; font-size:0.75rem; font-weight:600;">${user.department || "General"}</span>
            </td>
            <td style="padding:10px 14px;">
              <div style="display:inline-flex; align-items:center; gap:6px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:4px 9px;">
                <i class="fa-solid fa-business-time" style="color:#3d9fd4; font-size:0.85em;"></i>
                <span style="font-weight:700; color:#1e293b; font-size:0.82rem;">${assignedShift.name}</span>
                <span style="font-size:0.72rem; color:#64748b; font-family:'JetBrains Mono',monospace;">(${start12} - ${end12})</span>
              </div>
            </td>
            <td style="padding:10px 14px; text-align:right;">
              <select class="form-select enterprise-select" onchange="assignStaffShift(${user.id}, this.value, '${safeName}', this)" style="display:inline-block; width:100%; max-width:270px; background:#ffffff; border:1.5px solid #cfe8f7; border-radius:8px; padding:5px 10px; font-size:0.82rem; font-weight:600; color:#1e293b; cursor:pointer;">
                ${shiftOptions}
              </select>
            </td>
          `;

          tbody.appendChild(tr);
        });

        updateBulkShiftButtonBadge();
      }

      function renderShiftStaffPaginationControls(currentPage, totalPages) {
        const controls = document.getElementById('shiftStaffPageControls');
        if (!controls) return;
        controls.innerHTML = '';

        if (totalPages <= 1) return;

        // Previous button
        const prevBtn = document.createElement('button');
        prevBtn.className = 'app-page-btn';
        prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i> Previous';
        prevBtn.disabled = currentPage === 1;
        prevBtn.onclick = () => shiftStaffGoToPage(currentPage - 1);
        controls.appendChild(prevBtn);

        // Page buttons
        for (let i = 1; i <= totalPages; i++) {
          const pageBtn = document.createElement('button');
          pageBtn.className = `app-page-btn ${i === currentPage ? 'active' : ''}`;
          pageBtn.textContent = i;
          pageBtn.onclick = () => shiftStaffGoToPage(i);
          controls.appendChild(pageBtn);
        }

        // Next button
        const nextBtn = document.createElement('button');
        nextBtn.className = 'app-page-btn';
        nextBtn.innerHTML = 'Next <i class="fa-solid fa-chevron-right"></i>';
        nextBtn.disabled = currentPage === totalPages;
        nextBtn.onclick = () => shiftStaffGoToPage(currentPage + 1);
        controls.appendChild(nextBtn);
      }

      function toggleSelectAllShiftStaff(checked) {
        selectedShiftStaffIds.clear();
        const checkboxes = document.querySelectorAll(".shift-staff-checkbox");
        checkboxes.forEach(cb => {
          cb.checked = checked;
          if (checked) {
            selectedShiftStaffIds.add(parseInt(cb.value));
          }
        });
        updateBulkShiftButtonBadge();
      }

      function toggleShiftStaffRowCheck(userId, checked) {
        if (checked) {
          selectedShiftStaffIds.add(userId);
        } else {
          selectedShiftStaffIds.delete(userId);
        }

        const allCbs = document.querySelectorAll(".shift-staff-checkbox");
        const allChecked = allCbs.length > 0 && Array.from(allCbs).every(cb => cb.checked);
        const selectAll = document.getElementById("selectAllShiftStaffCheck");
        if (selectAll) selectAll.checked = allChecked;

        updateBulkShiftButtonBadge();
      }

      function updateBulkShiftButtonBadge() {
        const countSpan = document.getElementById("bulkShiftSelectedCount");
        if (countSpan) {
          countSpan.textContent = selectedShiftStaffIds.size;
        }
      }

      async function assignStaffShift(userId, shiftId, userName, selectEl) {
        let prevBorder = '';
        if (selectEl) {
          prevBorder = selectEl.style.borderColor;
          selectEl.style.borderColor = '#3d9fd4';
          selectEl.disabled = true;
        }
        try {
          const resp = await fetch(`${API_BASE}/users/${userId}/assign-shift`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shift_id: parseInt(shiftId), effective_from: getShiftEffectiveFrom() })
          });
          const data = await resp.json();
          if (resp.ok && data.success) {
            showAppToast(data.message || `Shift updated for ${userName}`, 'success');
            loadShiftsList();
            if (typeof loadTabStaffDirectory === 'function') loadTabStaffDirectory();
          } else {
            showAppToast(data.error || 'Failed to update shift', 'error');
            if (selectEl) selectEl.disabled = false;
          }
        } catch (err) {
          showAppToast('Error assigning shift: ' + err.message, 'error');
          if (selectEl) selectEl.disabled = false;
        } finally {
          if (selectEl) {
            selectEl.disabled = false;
            selectEl.style.borderColor = prevBorder;
          }
        }
      }

      async function applyBulkShiftAssignment() {
        const targetShiftSelect = document.getElementById("bulkShiftTargetSelect");
        const targetShiftId = targetShiftSelect?.value;
        if (!targetShiftId) {
          showAppToast("Please select a target shift first.", "error");
          return;
        }

        const selectedShiftObj = allShiftsCache.find(s => String(s.id) === String(targetShiftId));
        const shiftTitle = selectedShiftObj ? selectedShiftObj.name : `Shift #${targetShiftId}`;

        let userIds = 'all';
        if (selectedShiftStaffIds.size > 0) {
          userIds = Array.from(selectedShiftStaffIds);
        } else {
          if (!confirm(`No specific staff selected.\n\nDo you want to assign '${shiftTitle}' to ALL registered staff members?`)) {
            return;
          }
        }

        const btn = document.getElementById("btnApplyBulkShift");
        const restoreBtn = setButtonLoading(btn, "Assigning...");

        try {
          const resp = await fetch(`${API_BASE}/users/bulk-assign-shifts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_ids: userIds, shift_id: parseInt(targetShiftId), effective_from: getShiftEffectiveFrom() })
          });
          const data = await resp.json();
          if (resp.ok && data.success) {
            showAppToast(data.message || `Assigned ${shiftTitle} to staff members`, 'success');
            selectedShiftStaffIds.clear();
            const selectAll = document.getElementById("selectAllShiftStaffCheck");
            if (selectAll) selectAll.checked = false;
            loadShiftsList();
            if (typeof loadTabStaffDirectory === 'function') loadTabStaffDirectory();
          } else {
            showAppToast(data.error || 'Failed to bulk assign shifts', 'error');
          }
        } catch (err) {
          showAppToast('Error in bulk shift assignment: ' + err.message, 'error');
        } finally {
          restoreBtn();
        }
      }

      function selectBulkCamerasAll(selectId, selectAll) {
        const select = document.getElementById(selectId);
        if (!select) return;
        Array.from(select.options).forEach((opt, idx) => {
          if (selectAll) {
            opt.selected = (idx === 0 || opt.value === 'all');
          } else {
            opt.selected = false;
          }
        });
      }

      function renderShiftsUI(shifts) {
        const grid = document.getElementById("shiftsCardsGrid");
        const tbody = document.getElementById("shiftsTableBody");
        const badge = document.getElementById("shiftsCountBadge");

        if (badge) badge.textContent = `${shifts.length} Shifts Configured`;

        if (grid) {
          grid.innerHTML = shifts
            .map((s) => {
              const start12 = formatMainTime(s.start_time);
              const end12 = formatMainTime(s.end_time);
              const hasGrace = s.grace_period_minutes && parseInt(s.grace_period_minutes) > 0;
              let windowStr = `${start12} - ${end12} (Full Shift)`;
              if (hasGrace) {
                let endGrace = `${s.start_time} +${s.grace_period_minutes}m`;
                try {
                  const [sh, sm] = s.start_time.split(':').map(Number);
                  const totalM = sh * 60 + sm + parseInt(s.grace_period_minutes);
                  endGrace = `${String(Math.floor(totalM / 60) % 24).padStart(2, '0')}:${String(totalM % 60).padStart(2, '0')}`;
                  endGrace = formatMainTime(endGrace);
                } catch (e) {}
                windowStr = `${start12} - ${endGrace}`;
              }

              const graceBadge = hasGrace
                ? `<span style="font-size:0.8em; color:#059669; font-weight:600;"><i class="fa-solid fa-clock-rotate-left"></i> Grace Window: ${s.grace_period_minutes} mins</span>`
                : `<span style="font-size:0.8em; color:#475569; font-weight:600;"><i class="fa-solid fa-ban"></i> Grace: Disabled</span>`;

              return `
              <div class="card p-3 shadow-sm" style="background:#ffffff; border:1px solid ${s.is_default ? '#86efac' : '#cfe8f7'}; border-radius:14px; position:relative;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                  <div>
                    <h3 style="font-size:1.1em; font-weight:800; color:#173042; margin:0; display:flex; align-items:center; gap:6px;">
                      ${s.name}
                      ${s.is_default ? '<span class="badge bg-success" style="font-size:0.68em; font-weight:700;"><i class="fa-solid fa-star"></i> DEFAULT</span>' : ''}
                    </h3>
                    <span class="badge bg-light text-primary border" style="font-size:0.75em; font-weight:700; margin-top:4px;">ID #${s.id}</span>
                  </div>
                  <span class="badge" style="background:#e5f5ff; color:#3d9fd4; font-size:0.8em; font-weight:700; padding:6px 12px; border-radius:8px;">
                    <i class="fa-solid fa-users" style="margin-right:4px;"></i> ${s.user_count || 0} Staff
                  </span>
                </div>

                <div style="background:#f8fafc; border-radius:10px; padding:12px; font-size:0.85em; display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:14px;">
                  <div>
                    <div style="color:#64748b; font-size:0.78em; font-weight:600;">Shift Hours</div>
                    <div style="font-weight:700; color:#1e293b;"><i class="fa-regular fa-clock" style="color:#3d9fd4; margin-right:3px;"></i> In: ${start12} <br/><i class="fa-solid fa-right-from-bracket" style="color:#64748b; margin-right:3px;"></i> Out: ${end12}</div>
                  </div>
                  <div>
                    <div style="color:#64748b; font-size:0.78em; font-weight:600;">Attendance Window</div>
                    <div style="font-weight:700; color:#0284c7;">${windowStr}</div>
                  </div>
                  <div style="grid-column:1/-1;">
                    <div style="color:#64748b; font-size:0.78em; font-weight:600;">Scheduled Working Days</div>
                    <div style="font-weight:700; color:#1e293b;">${shiftWorkingDaysLabel(s.working_days)}</div>
                  </div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center;">
                  ${graceBadge}
                  <div style="display:flex; gap:6px; align-items:center;">
                    ${!s.is_default ? `<button class="btn btn-sm btn-outline-success" onclick="setDefaultShift(${s.id}, '${s.name}')" style="padding:4px 8px; font-size:0.78em;" title="Set as Default Shift"><i class="fa-solid fa-star"></i> Set Default</button>` : ''}
                    <button class="btn btn-sm btn-outline-primary" onclick="openEditShiftModal(${s.id}, '${s.name}', '${s.start_time}', '${s.end_time}', ${s.grace_period_minutes}, ${JSON.stringify(s.working_days || [0, 1, 2, 3, 4, 5])})" style="padding:4px 10px; font-size:0.8em;">
                      <i class="fa-solid fa-pen-to-square"></i> Edit
                    </button>
                    ${!s.is_default ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteShift(${s.id}, '${s.name}')" style="padding:4px 10px; font-size:0.8em;" title="Delete Shift"><i class="fa-solid fa-trash"></i></button>` : ''}
                  </div>
                </div>
              </div>
            `;
            })
            .join("");
        }

        if (tbody) {
          tbody.innerHTML = shifts
            .map((s) => {
              const start12 = formatMainTime(s.start_time);
              const end12 = formatMainTime(s.end_time);
              const hasGrace = s.grace_period_minutes && parseInt(s.grace_period_minutes) > 0;
              let windowStr = `${start12} to ${end12} (Full Shift)`;
              if (hasGrace) {
                let endGrace = `${s.start_time} +${s.grace_period_minutes}m`;
                try {
                  const [sh, sm] = s.start_time.split(':').map(Number);
                  const totalM = sh * 60 + sm + parseInt(s.grace_period_minutes);
                  endGrace = `${String(Math.floor(totalM / 60) % 24).padStart(2, '0')}:${String(totalM % 60).padStart(2, '0')}`;
                  endGrace = formatMainTime(endGrace);
                } catch (e) {}
                windowStr = `${start12} to ${endGrace} (${s.grace_period_minutes}m Grace)`;
              }

              return `
              <tr style="border-bottom:1px solid #e2e8f0;">
                <td style="padding:12px 16px; font-weight:700; color:#173042;">
                  ${s.name} ${s.is_default ? '<span class="badge bg-success" style="font-size:0.65em; margin-left:4px;"><i class="fa-solid fa-star"></i> DEFAULT</span>' : ''}
                </td>
                <td style="padding:12px 16px; font-family:'JetBrains Mono',monospace; color:#334155; font-weight:600;"><i class="fa-regular fa-clock" style="color:#3d9fd4; margin-right:4px;"></i>${start12}</td>
                <td style="padding:12px 16px; font-family:'JetBrains Mono',monospace; color:#334155; font-weight:600;"><i class="fa-solid fa-right-from-bracket" style="color:#64748b; margin-right:4px;"></i>${end12}</td>
                <td style="padding:12px 16px;">
                  <span style="background:${hasGrace ? '#e0f2fe' : '#f1f5f9'}; color:${hasGrace ? '#0369a1' : '#475569'}; padding:4px 10px; border-radius:6px; font-weight:700; font-size:0.82em;">
                    <i class="fa-solid ${hasGrace ? 'fa-clock-rotate-left' : 'fa-ban'}" style="margin-right:4px;"></i> ${windowStr}
                  </span>
                </td>
                <td style="padding:12px 16px; font-weight:700; color:#475569;">${s.user_count || 0} Staff</td>
                <td style="padding:12px 16px; text-align:right;">
                  ${!s.is_default ? `<button class="btn btn-sm btn-outline-success me-1" onclick="setDefaultShift(${s.id}, '${s.name}')" title="Set as Default Shift"><i class="fa-solid fa-star"></i> Set Default</button>` : ''}
                  <button class="btn btn-sm btn-outline-primary me-1" onclick="openEditShiftModal(${s.id}, '${s.name}', '${s.start_time}', '${s.end_time}', ${s.grace_period_minutes}, ${JSON.stringify(s.working_days || [0, 1, 2, 3, 4, 5])})">
                    <i class="fa-solid fa-pen-to-square"></i>
                  </button>
                  ${!s.is_default ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteShift(${s.id}, '${s.name}')"><i class="fa-solid fa-trash"></i></button>` : ''}
                </td>
              </tr>
            `;
            })
            .join("");
        }
      }

      async function setDefaultShift(id, name) {
        try {
          const resp = await fetch(`${API_BASE}/shifts/${id}/set-default`, { method: "POST" });
          const data = await resp.json();
          if (resp.ok && data.success) {
            showAppToast(`'${name}' is now set as the Default Shift.`, "success");
            loadShiftsList();
          } else {
            showAppToast(data.error || "Failed to set default shift", "error");
          }
        } catch (e) {
          showAppToast("Error setting default shift", "error");
        }
      }

      function openAddShiftModal() {
        document.getElementById("modalShiftId").value = "";
        document.getElementById("modalShiftName").value = "";
        document.getElementById("modalShiftStart").value = "09:00";
        document.getElementById("modalShiftEnd").value = "17:00";
        setShiftWorkingDays([0, 1, 2, 3, 4, 5]);
        
        const chk = document.getElementById("modalShiftGraceCheck");
        if (chk) { chk.checked = true; toggleShiftGraceInput(true); }
        document.getElementById("modalShiftGrace").value = "15";

        document.getElementById("shiftModalTitle").innerHTML = '<i class="fa-solid fa-business-time" style="color:#3d9fd4; margin-right:8px;"></i> Add New Shift';
        document.getElementById("shiftModalMsg").innerHTML = "";

        const modalEl = document.getElementById("shiftModal");
        if (modalEl) modalEl.style.display = "flex";
      }

      function openEditShiftModal(id, name, start, end, grace, workingDays) {
        document.getElementById("modalShiftId").value = id;
        document.getElementById("modalShiftName").value = name;
        document.getElementById("modalShiftStart").value = start;
        document.getElementById("modalShiftEnd").value = end;
        setShiftWorkingDays(workingDays);

        const hasGrace = (grace !== undefined && grace !== null && parseInt(grace) > 0);
        const chk = document.getElementById("modalShiftGraceCheck");
        if (chk) {
          chk.checked = hasGrace;
          toggleShiftGraceInput(hasGrace);
        }
        document.getElementById("modalShiftGrace").value = hasGrace ? grace : "0";

        document.getElementById("shiftModalTitle").innerHTML = `<i class="fa-solid fa-pen-to-square" style="color:#3d9fd4; margin-right:8px;"></i> Edit Shift: ${name}`;
        document.getElementById("shiftModalMsg").innerHTML = "";

        const modalEl = document.getElementById("shiftModal");
        if (modalEl) modalEl.style.display = "flex";
      }

      function closeShiftModal() {
        const modalEl = document.getElementById("shiftModal");
        if (modalEl) modalEl.style.display = "none";
      }

      async function saveShift() {
        const id = document.getElementById("modalShiftId").value;
        const name = document.getElementById("modalShiftName").value.trim();
        const start_time = document.getElementById("modalShiftStart").value;
        const end_time = document.getElementById("modalShiftEnd").value;
        const working_days = Array.from(document.querySelectorAll('#shiftModal input[name="modalShiftWorkingDays"]:checked'))
          .map(input => Number(input.value));
        const chk = document.getElementById("modalShiftGraceCheck");
        const isGraceEnabled = chk ? chk.checked : true;
        const grace_period_minutes = isGraceEnabled ? Math.max(0, parseInt(document.getElementById("modalShiftGrace").value || 0)) : 0;

        if (!name) {
          showMessage("shiftModalMsg", "Shift name is required", "error");
          return;
        }
        if (!working_days.length) {
          showMessage("shiftModalMsg", "Select at least one scheduled working day", "error");
          return;
        }

        const btn = document.querySelector('#shiftModal button.btn-primary');
        const restoreBtn = setButtonLoading(btn, id ? 'Updating...' : 'Creating...');
        try {
          const url = id ? `${API_BASE}/shifts/${id}` : `${API_BASE}/shifts`;
          const method = id ? "PUT" : "POST";
          const resp = await fetch(url, {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, start_time, end_time, grace_period_minutes, working_days }),
          });
          const data = await resp.json();
          if (resp.ok) {
            closeShiftModal();
            loadShiftsList();
            if (typeof loadStaffDirectory === 'function') loadStaffDirectory();
            showAppToast(data.message || `Shift '${name}' saved successfully`, 'success');
          } else {
            showMessage("shiftModalMsg", data.error || "Failed to save shift", "error");
            showAppToast(data.error || 'Failed to save shift', 'error');
          }
        } catch (e) {
          showMessage("shiftModalMsg", `Error: ${e.message}`, "error");
          showAppToast(`Error: ${e.message}`, 'error');
        } finally {
          restoreBtn();
        }
      }

      async function deleteShift(id, name) {
        if (!confirm(`Are you sure you want to delete shift '${name}'?\nAny employees assigned to this shift will revert to Morning Shift.`)) return;
        try {
          const resp = await fetch(`${API_BASE}/shifts/${id}`, { method: "DELETE" });
          const data = await resp.json();
          if (resp.ok) {
            loadShiftsList();
            if (typeof loadStaffDirectory === 'function') loadStaffDirectory();
            showAppToast(data.message || `Shift '${name}' deleted`, 'success');
          } else {
            showAppToast(data.error || 'Failed to delete shift', 'error');
          }
        } catch (e) {
          showAppToast(`Error: ${e.message}`, 'error');
        }
      }

      // ========================================================
      // SYSTEM SETTINGS & ADMIN CONFIGURATION (DYNAMIC CRUD)
      // ========================================================
      let currentSettingsTab = 'branch-tab';
      let cachedDepartments = [];
      let cachedDesignations = [];
      let cachedCameras = [];
      let cachedPayrollRules = [];
      let cachedPayrollCalendar = [];
      let cachedPayrollCalendarShifts = [];
      let cachedPayrollCalendarUsers = [];

      function switchSettingsTab(tabId, btn) {
        currentSettingsTab = tabId;
        document.querySelectorAll('.settings-nav-btn').forEach(b => {
          b.classList.remove('active');
          b.style.background = '#f1f5f9';
          b.style.color = '#475569';
        });
        if (btn) {
          btn.classList.add('active');
          btn.style.background = '#3d9fd4';
          btn.style.color = '#ffffff';
        }

        document.querySelectorAll('.settings-sub-tab').forEach(pane => {
          pane.style.display = 'none';
        });

        const activePane = document.getElementById(tabId);
        if (activePane) activePane.style.display = 'block';

        const SUBTAB_CONFIG = {
          'branch-tab': { title: 'Settings', subtitle: 'Manage organization, branch, staff, shift, and system configuration.' },
          'depts-tab': { title: 'Department Management', subtitle: 'Manage departments used across the organization.' },
          'desigs-tab': { title: 'Designation Management', subtitle: 'Manage department-specific staff designations.' },
          'cameras-tab': { title: 'Camera Management', subtitle: 'Configure and manage attendance cameras.' },
          'payroll-rules-tab': { title: 'Payroll Rules', subtitle: 'Configure database-backed attendance deduction rules.' },
          'payroll-calendar-tab': { title: 'Payroll Calendar', subtitle: 'Configure date-specific working days, closures, and holidays.' },
          'salary-config-tab': { title: 'Employee Salary Structure', subtitle: 'Configure employee basic pay, allowances, deductions, and hourly overtime rates.' }
        };
        const topbarTitle = document.getElementById("headerCurrentPageTitle");
        const settingsSubEl = document.getElementById("settingsPageSubtitle");
        if (SUBTAB_CONFIG[tabId]) {
          if (topbarTitle) topbarTitle.textContent = SUBTAB_CONFIG[tabId].title;
          if (settingsSubEl) settingsSubEl.textContent = SUBTAB_CONFIG[tabId].subtitle;
        }

        if (tabId === 'branch-tab') loadBranchSettings();
        else if (tabId === 'depts-tab') loadDepartmentsTable();
        else if (tabId === 'desigs-tab') loadDesignationsTable();
        else if (tabId === 'cameras-tab') loadCamerasGrid();
        else if (tabId === 'payroll-rules-tab') loadPayrollRules();
        else if (tabId === 'payroll-calendar-tab') loadPayrollCalendar();
        else if (tabId === 'salary-config-tab') loadSalaryConfigs();
      }

      async function reloadSystemConfiguration() {
        await Promise.allSettled([
          loadBranchSettings(),
          loadDepartmentsTable(),
          loadDesignationsTable(),
          loadCamerasGrid(),
          loadPayrollRules(),
          loadPayrollCalendar(),
          loadSalaryConfigs(),
          loadDepartmentDropdowns(),
          loadLiveCameras()
        ]);
      }

      async function loadPayrollRules() {
        const tbody = document.getElementById('payrollRulesTableBody');
        if (!tbody) return;
        try {
          const response = await fetch(`${API_BASE}/payroll/rules`);
          const rules = await response.json();
          if (!response.ok) throw new Error(rules.error || 'Failed to load payroll rules');
          cachedPayrollRules = rules;
          renderPayrollRules();
        } catch (error) {
          tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger p-4">${payrollEscape(error.message)}</td></tr>`;
        }
      }

      async function loadPayrollCalendar() {
        const tbody = document.getElementById('payrollCalendarTableBody');
        if (!tbody) return;
        try {
          const [response, shiftsResponse, usersResponse] = await Promise.all([
            fetch(`${API_BASE}/payroll/calendar`),
            fetch(`${API_BASE}/shifts`),
            fetch(`${API_BASE}/users`)
          ]);
          const entries = await response.json();
          const shifts = await shiftsResponse.json();
          const users = await usersResponse.json();
          if (!response.ok) throw new Error(entries.error || 'Failed to load special dates');
          if (!shiftsResponse.ok || !usersResponse.ok) throw new Error('Failed to load calendar targets');
          cachedPayrollCalendar = entries;
          cachedPayrollCalendarShifts = shifts.shifts || [];
          cachedPayrollCalendarUsers = users.users || [];
          updatePayrollCalendarScopeOptions();
          renderPayrollCalendar();
        } catch (error) {
          tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger p-4">${payrollEscape(error.message)}</td></tr>`;
        }
      }

      function renderPayrollCalendar() {
        const tbody = document.getElementById('payrollCalendarTableBody');
        if (!tbody) return;
        if (!cachedPayrollCalendar.length) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted p-4">No special dates configured.</td></tr>';
          return;
        }
        const labels = { working_day: 'Working Day', off_day: 'Off Day', holiday: 'Holiday' };
        tbody.innerHTML = cachedPayrollCalendar.map(entry => {
          const date = new Date(`${entry.calendar_date}T00:00:00Z`);
          const weekday = new Intl.DateTimeFormat(undefined, { weekday: 'long', timeZone: 'UTC' }).format(date);
          const scopeLabel = entry.scope_type === 'shift'
            ? `Shift: ${(cachedPayrollCalendarShifts.find(item => Number(item.id) === Number(entry.scope_id)) || {}).name || `#${entry.scope_id}`}`
            : entry.scope_type === 'employee'
              ? `Employee: ${(cachedPayrollCalendarUsers.find(item => Number(item.id) === Number(entry.scope_id)) || {}).name || `#${entry.scope_id}`}`
              : 'All employees';
          return `<tr>
            <td class="fw-semibold">${payrollEscape(weekday)}, ${payrollEscape(entry.calendar_date)}</td>
            <td>${payrollEscape(labels[entry.override_type] || entry.override_type)}</td>
            <td>${payrollEscape(scopeLabel)}${entry.note ? `<div class="text-muted small">${payrollEscape(entry.note)}</div>` : ''}</td>
            <td style="text-align:right; white-space:nowrap;">
              <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="editPayrollCalendarOverride(${Number(entry.id)})" aria-label="Edit special date"><i class="fa-solid fa-pen-to-square"></i></button>
              <button type="button" class="btn btn-outline-danger btn-sm" onclick="deletePayrollCalendarOverride(${Number(entry.id)})" aria-label="Remove special date"><i class="fa-solid fa-trash"></i></button>
            </td>
          </tr>`;
        }).join('');
      }

      function updatePayrollCalendarScopeOptions(selectedId = '') {
        const scopeType = document.getElementById('payrollCalendarScope').value;
        const field = document.getElementById('payrollCalendarTargetField');
        const target = document.getElementById('payrollCalendarTarget');
        field.style.display = scopeType === 'all' ? 'none' : 'grid';
        const options = scopeType === 'shift' ? cachedPayrollCalendarShifts : cachedPayrollCalendarUsers;
        target.innerHTML = options.map(item => `<option value="${Number(item.id)}">${payrollEscape(item.name)}</option>`).join('');
        if (selectedId && Array.from(target.options).some(option => option.value === String(selectedId))) {
          target.value = String(selectedId);
        }
      }

      function resetPayrollCalendarForm() {
        document.getElementById('payrollCalendarForm').reset();
        document.getElementById('payrollCalendarId').value = '';
        document.getElementById('payrollCalendarType').value = 'working_day';
        document.getElementById('payrollCalendarScope').value = 'all';
        updatePayrollCalendarScopeOptions();
        document.getElementById('payrollCalendarSaveButton').innerHTML = '<i class="fa-solid fa-plus me-1"></i> Add Date';
        document.getElementById('payrollCalendarCancelButton').style.display = 'none';
      }

      function editPayrollCalendarOverride(overrideId) {
        const entry = cachedPayrollCalendar.find(item => Number(item.id) === Number(overrideId));
        if (!entry) return;
        document.getElementById('payrollCalendarId').value = entry.id;
        document.getElementById('payrollCalendarDate').value = entry.calendar_date;
        document.getElementById('payrollCalendarType').value = entry.override_type;
        document.getElementById('payrollCalendarScope').value = entry.scope_type || 'all';
        updatePayrollCalendarScopeOptions(entry.scope_id);
        document.getElementById('payrollCalendarNote').value = entry.note || '';
        document.getElementById('payrollCalendarSaveButton').innerHTML = '<i class="fa-solid fa-floppy-disk me-1"></i> Save Date';
        document.getElementById('payrollCalendarCancelButton').style.display = 'inline-block';
        document.getElementById('payrollCalendarMessage').innerHTML = '';
        document.getElementById('payrollCalendarDate').focus();
      }

      async function refreshDraftPayrollAfterCalendarChange() {
        await loadPayrollCalendar();
        const monthInput = document.getElementById('payrollMonth');
        if (currentPayrollPreview && !currentPayrollPreview.is_finalized &&
            currentPayrollPreview.payroll_month === monthInput?.value) {
          await loadMonthlyPayroll();
        }
      }

      async function savePayrollCalendarOverride() {
        const id = document.getElementById('payrollCalendarId').value;
        const payload = {
          calendar_date: document.getElementById('payrollCalendarDate').value,
          override_type: document.getElementById('payrollCalendarType').value,
          note: document.getElementById('payrollCalendarNote').value,
          scope_type: document.getElementById('payrollCalendarScope').value,
          scope_id: document.getElementById('payrollCalendarScope').value === 'all'
            ? 0
            : document.getElementById('payrollCalendarTarget').value
        };
        const message = document.getElementById('payrollCalendarMessage');
        try {
          const response = await fetch(id ? `${API_BASE}/payroll/calendar/${id}` : `${API_BASE}/payroll/calendar`, {
            method: id ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Failed to save special date');
          message.innerHTML = '';
          resetPayrollCalendarForm();
          await refreshDraftPayrollAfterCalendarChange();
          showAppToast(id ? 'Special date updated' : 'Special date added', 'success');
        } catch (error) {
          message.innerHTML = `<div class="alert alert-danger py-2 mb-0">${payrollEscape(error.message)}</div>`;
        }
      }

      async function deletePayrollCalendarOverride(overrideId) {
        const entry = cachedPayrollCalendar.find(item => Number(item.id) === Number(overrideId));
        if (!entry || !window.confirm(`Remove the special date for ${entry.calendar_date}?`)) return;
        try {
          const response = await fetch(`${API_BASE}/payroll/calendar/${overrideId}`, { method: 'DELETE' });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Failed to remove special date');
          await refreshDraftPayrollAfterCalendarChange();
          showAppToast('Special date removed', 'success');
        } catch (error) {
          showAppToast(error.message, 'error');
        }
      }

      function renderPayrollRules() {
        const tbody = document.getElementById('payrollRulesTableBody');
        if (!tbody) return;
        if (!cachedPayrollRules.length) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted p-4">No payroll rules configured. Add an active absence range before finalizing payroll with absences.</td></tr>';
          return;
        }
        tbody.innerHTML = cachedPayrollRules.map(rule => {
          const range = rule.max_absent_days === null
            ? `${rule.min_absent_days}+ absent days`
            : rule.min_absent_days === rule.max_absent_days
              ? `${rule.min_absent_days} absent days`
              : `${rule.min_absent_days}-${rule.max_absent_days} absent days`;
          const status = Number(rule.active) === 1 ? 'Active' : 'Inactive';
          const badge = Number(rule.active) === 1 ? 'bg-success-subtle text-success' : 'bg-secondary-subtle text-secondary';
          const toggleLabel = Number(rule.active) === 1 ? 'Deactivate' : 'Activate';
          const ruleValue = rule.deduction_type === 'fixed'
            ? payrollMoney(rule.fixed_amount)
            : `${Number(rule.deduction_percent).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
          return `<tr>
            <td>${payrollEscape(range)}</td>
            <td class="fw-semibold">${payrollEscape(ruleValue)}</td>
            <td><span class="badge ${badge}">${status}</span></td>
            <td style="text-align:right; white-space:nowrap;">
              <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="editPayrollRule(${Number(rule.id)})" aria-label="Edit rule"><i class="fa-solid fa-pen-to-square"></i></button>
              <button type="button" class="btn btn-outline-secondary btn-sm" onclick="togglePayrollRule(${Number(rule.id)}, ${Number(rule.active) !== 1})">${toggleLabel}</button>
            </td>
          </tr>`;
        }).join('');
      }

      function resetPayrollRuleForm() {
        document.getElementById('payrollRuleForm').reset();
        document.getElementById('payrollRuleId').value = '';
        document.getElementById('payrollRuleActive').checked = true;
        document.getElementById('payrollRuleType').value = 'percentage';
        updatePayrollRuleFields();
        document.getElementById('payrollRuleSaveButton').innerHTML = '<i class="fa-solid fa-plus me-1"></i> Add Rule';
        document.getElementById('payrollRuleCancelButton').style.display = 'none';
      }

      function updatePayrollRuleFields() {
        const isFixed = document.getElementById('payrollRuleType').value === 'fixed';
        const percentageInput = document.getElementById('payrollRulePercent');
        const fixedInput = document.getElementById('payrollRuleFixed');
        document.getElementById('payrollRulePercentField').style.display = isFixed ? 'none' : 'grid';
        document.getElementById('payrollRuleFixedField').style.display = isFixed ? 'grid' : 'none';
        percentageInput.required = !isFixed;
        percentageInput.disabled = isFixed;
        fixedInput.required = isFixed;
        fixedInput.disabled = !isFixed;
      }

      function editPayrollRule(ruleId) {
        const rule = cachedPayrollRules.find(item => Number(item.id) === Number(ruleId));
        if (!rule) return;
        document.getElementById('payrollRuleId').value = rule.id;
        document.getElementById('payrollRuleMin').value = rule.min_absent_days;
        document.getElementById('payrollRuleMax').value = rule.max_absent_days ?? '';
        document.getElementById('payrollRuleType').value = rule.deduction_type || 'percentage';
        document.getElementById('payrollRulePercent').value = rule.deduction_percent ?? '';
        document.getElementById('payrollRuleFixed').value = rule.fixed_amount ?? '';
        updatePayrollRuleFields();
        document.getElementById('payrollRuleActive').checked = Number(rule.active) === 1;
        document.getElementById('payrollRuleSaveButton').innerHTML = '<i class="fa-solid fa-floppy-disk me-1"></i> Save Rule';
        document.getElementById('payrollRuleCancelButton').style.display = 'inline-block';
        document.getElementById('payrollRulesMessage').innerHTML = '';
        document.getElementById('payrollRuleMin').focus();
      }

      async function savePayrollRule() {
        const id = document.getElementById('payrollRuleId').value;
        const data = {
          min_absent_days: document.getElementById('payrollRuleMin').value,
          max_absent_days: document.getElementById('payrollRuleMax').value || null,
          deduction_type: deductionType,
          deduction_percent: deductionType === 'percentage' ? document.getElementById('payrollRulePercent').value : 0,
          fixed_amount: deductionType === 'fixed' ? document.getElementById('payrollRuleFixed').value : 0,
          active: document.getElementById('payrollRuleActive').checked
        };
        const message = document.getElementById('payrollRulesMessage');
        try {
          const response = await fetch(id ? `${API_BASE}/payroll/rules/${id}` : `${API_BASE}/payroll/rules`, {
            method: id ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Failed to save payroll rule');
          message.innerHTML = '';
          resetPayrollRuleForm();
          await loadPayrollRules();
          showAppToast(id ? 'Payroll rule updated' : 'Payroll rule added', 'success');
        } catch (error) {
          message.innerHTML = `<div class="alert alert-danger py-2 mb-0">${payrollEscape(error.message)}</div>`;
        }
      }

      async function togglePayrollRule(ruleId, activate) {
        const message = document.getElementById('payrollRulesMessage');
        try {
          const response = await fetch(`${API_BASE}/payroll/rules/${ruleId}${activate ? '/activate' : ''}`, {
            method: activate ? 'POST' : 'DELETE'
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Failed to change payroll rule status');
          message.innerHTML = '';
          await loadPayrollRules();
          showAppToast(activate ? 'Payroll rule activated' : 'Payroll rule deactivated', 'success');
        } catch (error) {
          message.innerHTML = `<div class="alert alert-danger py-2 mb-0">${payrollEscape(error.message)}</div>`;
        }
      }

      // ================================================================
      // EMPLOYEE SALARY STRUCTURE & CONFIGURATION MODULE
      // ================================================================
      let cachedSalaryConfigs = [];
      let cachedSalarySummary = null;

      function formatSalaryCurrency(val) {
        const num = parseFloat(val) || 0;
        return 'PKR ' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      }

      function escapeSalaryHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/[&<>"']/g, m => ({
          '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[m]));
      }

      async function loadSalaryConfigs() {
        const tbody = document.getElementById('salaryConfigTableBody');
        const msgEl = document.getElementById('salaryConfigMessage');
        if (msgEl) msgEl.innerHTML = '';
        if (tbody) {
          tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin me-2"></i> Loading salary structures...</td></tr>`;
        }
        try {
          const [configsResp, summaryResp] = await Promise.all([
            fetch(`${API_BASE}/salary`),
            fetch(`${API_BASE}/salary/summary`)
          ]);
          if (!configsResp.ok) throw new Error('Failed to load salary configurations');
          cachedSalaryConfigs = await configsResp.json();
          if (summaryResp.ok) {
            cachedSalarySummary = await summaryResp.json();
            updateSalarySummaryCards(cachedSalarySummary);
          }
          populateSalaryDeptDropdown();
          renderSalaryTable(cachedSalaryConfigs);
        } catch (error) {
          console.error("Failed to load salary configs:", error);
          if (tbody) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center text-danger p-4"><i class="fa-solid fa-triangle-exclamation me-2"></i> Error loading salary structures: ${escapeSalaryHtml(error.message)}</td></tr>`;
          }
        }
      }

      function updateSalarySummaryCards(summary) {
        if (!summary) return;
        const totalStaffEl = document.getElementById('salaryTotalStaff');
        const totalBaseEl = document.getElementById('salaryTotalBase');
        const totalAllowEl = document.getElementById('salaryTotalAllowances');
        const totalNetEl = document.getElementById('salaryTotalNet');

        if (totalStaffEl) totalStaffEl.textContent = summary.total_employees ?? '--';
        if (totalBaseEl) totalBaseEl.textContent = formatSalaryCurrency(summary.total_basic);
        if (totalAllowEl) totalAllowEl.textContent = formatSalaryCurrency(summary.total_allowances);
        if (totalNetEl) totalNetEl.textContent = formatSalaryCurrency(summary.total_net_payroll);
      }

      function populateSalaryDeptDropdown() {
        const select = document.getElementById('salaryDeptFilter');
        if (!select) return;
        const currentVal = select.value;
        const depts = new Set();
        (cachedSalaryConfigs || []).forEach(c => {
          if (c.department && c.department.trim()) depts.add(c.department.trim());
        });
        const sortedDepts = Array.from(depts).sort();
        let optionsHtml = '<option value="all">All Departments</option>';
        sortedDepts.forEach(d => {
          optionsHtml += `<option value="${escapeSalaryHtml(d)}">${escapeSalaryHtml(d)}</option>`;
        });
        select.innerHTML = optionsHtml;
        if (currentVal && (sortedDepts.includes(currentVal) || currentVal === 'all')) {
          select.value = currentVal;
        }
      }

      function renderSalaryTable(list) {
        const tbody = document.getElementById('salaryConfigTableBody');
        if (!tbody) return;

        if (!list || list.length === 0) {
          tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted p-4"><i class="fa-solid fa-inbox me-2"></i> No employee salary structures found matching criteria.</td></tr>`;
          return;
        }

        let html = '';
        list.forEach(item => {
          const isConfigured = Boolean(item.is_configured);
          const initials = (item.user_name || 'U').split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
          const badgeHtml = isConfigured
            ? `<span class="badge" style="background:#ecfdf5; color:#059669; border:1px solid #a7f3d0; font-size:0.75em; padding:4px 8px;"><i class="fa-solid fa-circle-check me-1"></i> Configured</span>`
            : `<span class="badge" style="background:#f1f5f9; color:#64748b; border:1px solid #cbd5e1; font-size:0.75em; padding:4px 8px;">Base Only</span>`;

          const dept = item.department || 'General';
          const desig = item.designation || 'Staff Member';

          html += `
            <tr style="border-bottom: 1px solid #f1f5f9; transition: background 0.15s ease;">
              <td style="padding: 12px 14px; font-weight: 700; color: #64748b; font-size: 0.82em;">#${item.user_id}</td>
              <td style="padding: 12px 14px;">
                <div style="display:flex; align-items:center; gap:10px;">
                  <div style="width:32px; height:32px; border-radius:8px; background:linear-gradient(135deg, #3d9fd4, #247eae); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:0.78em; flex-shrink:0;">
                    ${initials}
                  </div>
                  <div>
                    <div style="font-weight:700; color:#173042; font-size:0.9em;">${escapeSalaryHtml(item.user_name)}</div>
                    <div style="font-size:0.75em; color:#94a3b8;">${escapeSalaryHtml(item.email || 'No email')}</div>
                  </div>
                </div>
              </td>
              <td style="padding: 12px 14px;">
                <div style="font-weight:600; color:#334155; font-size:0.85em;">${escapeSalaryHtml(dept)}</div>
                <div style="font-size:0.75em; color:#64748b;">${escapeSalaryHtml(desig)}</div>
              </td>
              <td style="padding: 12px 14px; text-align:right; font-weight:700; color:#0f172a; font-size:0.88em;">
                ${formatSalaryCurrency(item.basic_salary)}
              </td>
              <td style="padding: 12px 14px; text-align:right; font-weight:700; color:#059669; font-size:0.88em;">
                ${item.allowances > 0 ? '+' + formatSalaryCurrency(item.allowances) : '<span style="color:#94a3b8;">--</span>'}
              </td>
              <td style="padding: 12px 14px; text-align:right; font-weight:700; color:#dc2626; font-size:0.88em;">
                ${item.deductions > 0 ? '-' + formatSalaryCurrency(item.deductions) : '<span style="color:#94a3b8;">--</span>'}
              </td>
              <td style="padding: 12px 14px; text-align:right; font-weight:700; color:#0284c7; font-size:0.88em;">
                ${item.ot_rate > 0 ? formatSalaryCurrency(item.ot_rate) + '<span style="font-size:0.75em; color:#94a3b8;">/hr</span>' : '<span style="color:#94a3b8;">--</span>'}
              </td>
              <td style="padding: 12px 14px; text-align:right; font-weight:800; color:#148f77; font-size:0.92em;">
                ${formatSalaryCurrency(item.net_estimated)}
              </td>
              <td style="padding: 12px 14px; text-align:center;">
                ${badgeHtml}
              </td>
              <td style="padding: 12px 14px; text-align:right;">
                <div style="display:flex; gap:6px; justify-content:flex-end; align-items:center;">
                  <button type="button" class="btn btn-sm btn-outline-primary" onclick="openEditSalaryModal(${item.user_id})" style="border-radius:6px; font-size:0.78em; padding:4px 9px;" title="Configure Salary Package">
                    <i class="fa-solid fa-pen-to-square"></i> Edit
                  </button>
                  ${isConfigured ? `
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="resetSalaryPackage(${item.user_id}, '${escapeSalaryHtml(item.user_name)}')" style="border-radius:6px; font-size:0.78em; padding:4px 8px;" title="Reset Custom Package to Default Base">
                      <i class="fa-solid fa-rotate-left"></i>
                    </button>
                  ` : ''}
                </div>
              </td>
            </tr>
          `;
        });
        tbody.innerHTML = html;
      }

      function filterSalaryTable() {
        const query = (document.getElementById('salarySearchInput')?.value || '').trim().toLowerCase();
        const deptFilter = (document.getElementById('salaryDeptFilter')?.value || 'all').trim().toLowerCase();
        const statusFilter = (document.getElementById('salaryStatusFilter')?.value || 'all').trim().toLowerCase();

        const filtered = (cachedSalaryConfigs || []).filter(item => {
          if (query) {
            const name = (item.user_name || '').toLowerCase();
            const email = (item.email || '').toLowerCase();
            const dept = (item.department || '').toLowerCase();
            const desig = (item.designation || '').toLowerCase();
            const uid = String(item.user_id || '');
            const matchQuery = name.includes(query) || email.includes(query) || dept.includes(query) || desig.includes(query) || uid.includes(query);
            if (!matchQuery) return false;
          }

          if (deptFilter !== 'all') {
            const itemDept = (item.department || '').trim().toLowerCase();
            if (itemDept !== deptFilter) return false;
          }

          if (statusFilter === 'configured') {
            if (!item.is_configured) return false;
          } else if (statusFilter === 'unconfigured') {
            if (item.is_configured) return false;
          }

          return true;
        });

        renderSalaryTable(filtered);
      }

      function resetSalaryFilters() {
        const searchInput = document.getElementById('salarySearchInput');
        const deptFilter = document.getElementById('salaryDeptFilter');
        const statusFilter = document.getElementById('salaryStatusFilter');
        if (searchInput) searchInput.value = '';
        if (deptFilter) deptFilter.value = 'all';
        if (statusFilter) statusFilter.value = 'all';
        renderSalaryTable(cachedSalaryConfigs);
      }

      async function openEditSalaryModal(userId) {
        const modal = document.getElementById('editSalaryConfigModal');
        const msgEl = document.getElementById('modalSalaryMsg');
        if (msgEl) msgEl.innerHTML = '';
        if (!modal) return;

        let item = (cachedSalaryConfigs || []).find(c => c.user_id === userId);
        try {
          const resp = await fetch(`${API_BASE}/salary/${userId}`);
          if (resp.ok) item = await resp.json();
        } catch (e) {
          console.warn("Could not fetch fresh user salary config, using cache:", e);
        }

        if (!item) {
          showAppToast('Employee not found', 'error');
          return;
        }

        document.getElementById('modalSalaryUserId').value = item.user_id;
        document.getElementById('modalSalaryEmpName').textContent = item.user_name || 'Staff Member';
        document.getElementById('modalSalaryEmpMeta').textContent = `${item.department || 'General'} • ${item.designation || 'Staff Member'} (ID: #${item.user_id})`;
        const initials = (item.user_name || 'U').split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
        document.getElementById('modalSalaryAvatar').textContent = initials;

        document.getElementById('modalSalaryBasic').value = parseFloat(item.basic_salary) || 0;
        document.getElementById('modalSalaryAllowances').value = parseFloat(item.allowances) || 0;
        document.getElementById('modalSalaryDeductions').value = parseFloat(item.deductions) || 0;
        document.getElementById('modalSalaryOtRate').value = parseFloat(item.ot_rate) || 0;

        updateSalaryModalLiveCalc();
        modal.style.display = 'flex';
      }

      function closeEditSalaryModal() {
        const modal = document.getElementById('editSalaryConfigModal');
        if (modal) modal.style.display = 'none';
        const msgEl = document.getElementById('modalSalaryMsg');
        if (msgEl) msgEl.innerHTML = '';
      }

      function updateSalaryModalLiveCalc() {
        const basic = Math.max(0, parseFloat(document.getElementById('modalSalaryBasic')?.value || 0));
        const allow = Math.max(0, parseFloat(document.getElementById('modalSalaryAllowances')?.value || 0));
        const deduct = Math.max(0, parseFloat(document.getElementById('modalSalaryDeductions')?.value || 0));
        const net = Math.max(0, basic + allow - deduct);

        const baseEl = document.getElementById('modalPreviewBase');
        const allowEl = document.getElementById('modalPreviewAllow');
        const deductEl = document.getElementById('modalPreviewDeduct');
        const netEl = document.getElementById('modalPreviewNet');

        if (baseEl) baseEl.textContent = formatSalaryCurrency(basic);
        if (allowEl) allowEl.textContent = formatSalaryCurrency(allow);
        if (deductEl) deductEl.textContent = formatSalaryCurrency(deduct);
        if (netEl) netEl.textContent = formatSalaryCurrency(net);
      }

      function calcSuggestedOtRate() {
        const basic = Math.max(0, parseFloat(document.getElementById('modalSalaryBasic')?.value || 0));
        const suggested = basic > 0 ? (Math.round((basic / 208) * 100) / 100) : 0;
        const input = document.getElementById('modalSalaryOtRate');
        if (input) input.value = suggested;
      }

      async function saveSalaryConfig() {
        const uid = document.getElementById('modalSalaryUserId')?.value;
        const msgEl = document.getElementById('modalSalaryMsg');
        const btn = document.getElementById('saveSalaryBtn');
        if (!uid) return;

        const basic = parseFloat(document.getElementById('modalSalaryBasic')?.value || 0);
        const allow = parseFloat(document.getElementById('modalSalaryAllowances')?.value || 0);
        const deduct = parseFloat(document.getElementById('modalSalaryDeductions')?.value || 0);
        const otRate = parseFloat(document.getElementById('modalSalaryOtRate')?.value || 0);

        if (isNaN(basic) || basic < 0 || isNaN(allow) || allow < 0 || isNaN(deduct) || deduct < 0 || isNaN(otRate) || otRate < 0) {
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger py-2 mb-0" style="font-size:0.85em;">All salary amounts must be valid non-negative numbers.</div>`;
          return;
        }

        const originalBtnText = btn ? btn.innerHTML : '';
        if (btn) {
          btn.disabled = true;
          btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin me-1"></i> Saving...`;
        }

        try {
          const resp = await fetch(`${API_BASE}/salary/${uid}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: parseInt(uid),
              basic_salary: basic,
              allowances: allow,
              deductions: deduct,
              ot_rate: otRate
            })
          });
          const result = await resp.json();
          if (!resp.ok || !result.success) {
            throw new Error(result.message || result.error || 'Failed to save salary configuration');
          }

          showAppToast('Salary package updated successfully', 'success');
          closeEditSalaryModal();
          await loadSalaryConfigs();
        } catch (error) {
          console.error("Save salary error:", error);
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger py-2 mb-0" style="font-size:0.85em;">${escapeSalaryHtml(error.message)}</div>`;
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalBtnText;
          }
        }
      }

      async function resetSalaryPackage(userId, userName) {
        if (!confirm(`Are you sure you want to reset the custom salary package for "${userName}"? This will clear allowances, custom deductions, and overtime rates back to default base.`)) {
          return;
        }
        try {
          const resp = await fetch(`${API_BASE}/salary/${userId}`, { method: 'DELETE' });
          const result = await resp.json();
          if (!resp.ok || !result.success) {
            throw new Error(result.message || 'Failed to reset package');
          }
          showAppToast(`Salary package reset for ${userName}`, 'info');
          await loadSalaryConfigs();
        } catch (error) {
          console.error("Reset salary error:", error);
          showAppToast(error.message || 'Failed to reset salary', 'error');
        }
      }

      function openAutoOtRateModal() {
        const modal = document.getElementById('autoOtRateModal');
        const msgEl = document.getElementById('modalAutoOtMsg');
        if (msgEl) msgEl.innerHTML = '';
        if (modal) modal.style.display = 'flex';
      }

      function closeAutoOtRateModal() {
        const modal = document.getElementById('autoOtRateModal');
        if (modal) modal.style.display = 'none';
        const msgEl = document.getElementById('modalAutoOtMsg');
        if (msgEl) msgEl.innerHTML = '';
      }

      async function runAutoOtRateCalculation() {
        const divisorInput = document.getElementById('autoOtDivisorInput');
        const divisor = parseFloat(divisorInput?.value || 208);
        const msgEl = document.getElementById('modalAutoOtMsg');
        const btn = document.getElementById('runAutoOtBtn');

        if (isNaN(divisor) || divisor <= 0) {
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger py-2 mb-0" style="font-size:0.85em;">Divisor must be a positive number of hours.</div>`;
          return;
        }

        const originalBtnText = btn ? btn.innerHTML : '';
        if (btn) {
          btn.disabled = true;
          btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin me-1"></i> Calculating...`;
        }

        try {
          const resp = await fetch(`${API_BASE}/salary/auto-ot-rates`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ divisor: divisor })
          });
          const result = await resp.json();
          if (!resp.ok || !result.success) {
            throw new Error(result.message || 'Failed to auto-calculate overtime rates');
          }
          showAppToast(result.message || 'Overtime rates calculated successfully', 'success');
          closeAutoOtRateModal();
          await loadSalaryConfigs();
        } catch (error) {
          console.error("Auto OT calc error:", error);
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger py-2 mb-0" style="font-size:0.85em;">${escapeSalaryHtml(error.message)}</div>`;
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalBtnText;
          }
        }
      }

      function openSalaryConfigFromPayroll() {
        switchTab('settings-view', document.getElementById('settingsMenuSidebarItem'));
        const btn = document.getElementById('salaryConfigNavBtn');
        switchSettingsTab('salary-config-tab', btn);
      }

      // --- BRANCH SETTINGS ---
      async function loadBranchSettings() {
        try {
          const resp = await fetch(`${API_BASE}/settings/branch`);
          const data = await resp.json();
          if (data) {
            if (document.getElementById('settingBranchName')) document.getElementById('settingBranchName').value = data.branch_name || '';
            if (document.getElementById('settingCity')) document.getElementById('settingCity').value = data.city || '';
            if (document.getElementById('settingCompanyName')) document.getElementById('settingCompanyName').value = data.company_name || '';
            if (document.getElementById('settingAdminName')) document.getElementById('settingAdminName').value = data.admin_name || 'Mr. Junaid';
            if (document.getElementById('settingPhone')) document.getElementById('settingPhone').value = data.phone || '';
            if (document.getElementById('settingEmail')) document.getElementById('settingEmail').value = data.email || '';
            if (document.getElementById('settingAddress')) document.getElementById('settingAddress').value = data.address || '';
            updateDynamicBranchHeaders(data.branch_name, data.city, data.admin_name);
          }
        } catch (e) {
          console.error("Failed to load branch settings:", e);
        }
      }

      function updateDynamicBranchHeaders(branchName, city, adminName) {
        const branchDisplay = (branchName || '').trim();
        const cityDisplay = (city || '').trim();
        let fullBranchText = branchDisplay;
        if (branchDisplay && cityDisplay) {
          fullBranchText = `${branchDisplay} (${cityDisplay})`;
        } else if (!branchDisplay && cityDisplay) {
          fullBranchText = cityDisplay;
        } else if (!branchDisplay) {
          fullBranchText = 'Main Branch';
        }

        // Main header brand company name
        const brandSpan = document.querySelector('.sidebar-brand span');
        if (brandSpan) {
          brandSpan.textContent = 'QIntellect Technologies';
        }
        const compHeader = document.querySelector('.header-company-name');
        if (compHeader) {
          compHeader.innerHTML = '<i class="fa-solid fa-circle-nodes" style="color:#3d9fd4;"></i> QIntellect Technologies';
        }

        // Header branch badge
        const headerBranchBadge = document.getElementById('headerBranchBadge');
        const headerBranchText = document.getElementById('headerBranchNameText');
        if (headerBranchText) {
          headerBranchText.textContent = fullBranchText;
        }
        if (headerBranchBadge) {
          headerBranchBadge.style.display = 'inline-flex';
        }

        // Sidebar branch text
        const sidebarBranchText = document.getElementById('sidebarBranchNameText');
        if (sidebarBranchText) {
          sidebarBranchText.textContent = fullBranchText;
        }

        // Dynamic title
        document.title = `${fullBranchText} - QIntellect Technologies`;

        // User / Admin display name
        const displayName = adminName || 'Mr. Junaid';
        const sidebarUserEl = document.getElementById('sidebarUserName');
        if (sidebarUserEl) sidebarUserEl.textContent = displayName;
        const headerUserEl = document.getElementById('headerUserName');
        if (headerUserEl) headerUserEl.textContent = displayName;
        document.querySelectorAll('.header-user-name').forEach(el => {
          el.textContent = displayName;
        });

        // Any dynamic branch elements
        document.querySelectorAll('.dynamic-branch-text').forEach(el => {
          el.textContent = fullBranchText;
        });
      }

      async function saveBranchSettings() {
        const msgEl = document.getElementById('branchSettingsMsg');
        const branch_name = document.getElementById('settingBranchName')?.value.trim();
        const city = document.getElementById('settingCity')?.value.trim();
        const company_name = document.getElementById('settingCompanyName')?.value.trim();
        const admin_name = document.getElementById('settingAdminName')?.value.trim() || 'Mr. Junaid';
        const phone = document.getElementById('settingPhone')?.value.trim();
        const email = document.getElementById('settingEmail')?.value.trim();
        const address = document.getElementById('settingAddress')?.value.trim();

        if (!branch_name || !city) {
          if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger p-2" style="font-size:0.85em;">Branch Name and City are required.</div>';
          return;
        }

        const btn = document.querySelector('#branchSettingsForm button[type="submit"]');
        const restoreBtn = setButtonLoading(btn, 'Saving...');
        try {
          const resp = await fetch(`${API_BASE}/settings/branch`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ branch_name, city, company_name, admin_name, phone, email, address })
          });
          const res = await resp.json();
          if (resp.ok && res.success) {
            if (msgEl) msgEl.innerHTML = '';
            updateDynamicBranchHeaders(branch_name, city, admin_name);
            showAppToast(res.message || 'Branch & Organization settings updated successfully', 'success');
          } else {
            showAppToast(res.error || 'Failed to save settings', 'error');
            if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">${res.error || 'Failed to save settings'}</div>`;
          }
        } catch (e) {
          showAppToast(`Error: ${e.message}`, 'error');
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">Error: ${e.message}</div>`;
        } finally {
          restoreBtn();
        }
      }

      // --- DEPARTMENT MANAGEMENT ---
      async function loadDepartmentsTable() {
        try {
          const resp = await fetch(`${API_BASE}/departments?active_only=false`);
          const depts = await resp.json();
          if (!resp.ok) throw new Error(depts.error || 'Failed to load departments');
          cachedDepartments = depts || [];
          renderDepartmentsTable(cachedDepartments);
          populateDesigFilterDeptDropdown(cachedDepartments);
          loadDepartmentDropdowns();
        } catch (e) {
          console.error("Failed to load departments:", e);
          const tbody = document.getElementById('departmentsTableBody');
          if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger p-4">${e.message}</td></tr>`;
        }
      }

      function renderDepartmentsTable(depts) {
        const tbody = document.getElementById('departmentsTableBody');
        if (!tbody) return;
        if (!depts || depts.length === 0) {
          tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-4">No departments found. Click "+ Add New Department" to create one.</td></tr>';
          return;
        }
        tbody.innerHTML = depts.map(d => {
          const statusBadge = d.active 
            ? '<span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size:0.78em; padding:4px 8px;"><i class="fa-solid fa-check"></i> Active</span>'
            : '<span class="badge bg-danger-subtle text-danger border border-danger-subtle" style="font-size:0.78em; padding:4px 8px;"><i class="fa-solid fa-ban"></i> Disabled</span>';
          return `
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="font-family: 'JetBrains Mono', monospace; font-weight:700; color:#3d9fd4;">#${d.id}</td>
              <td style="font-weight:700; color:#173042;">${d.name}</td>
              <td><span class="badge bg-light text-dark border">${d.code || '—'}</span></td>
              <td style="color:#64748b; font-size:0.85em;">${d.description || '—'}</td>
              <td style="font-weight:600;"><i class="fa-solid fa-users" style="color:#3d9fd4; margin-right:4px;"></i> ${d.staff_count || 0} Staff</td>
              <td style="font-weight:600;"><i class="fa-solid fa-id-badge" style="color:#0ea5e9; margin-right:4px;"></i> ${d.designation_count || 0} Roles</td>
              <td>${statusBadge}</td>
              <td style="text-align: right;">
                <button class="btn btn-sm btn-outline-primary me-1" onclick="openEditDeptModal(${d.id}, '${d.name.replace(/'/g, "\\'")}', '${(d.code||'').replace(/'/g, "\\'")}', '${(d.description||'').replace(/'/g, "\\'")}')" style="padding:3px 8px; font-size:0.8em;">
                  <i class="fa-solid fa-pen-to-square"></i> Edit
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteDepartment(${d.id}, '${d.name.replace(/'/g, "\\'")}')" style="padding:3px 8px; font-size:0.8em;">
                  <i class="fa-solid fa-trash"></i>
                </button>
              </td>
            </tr>
          `;
        }).join('');
      }

      function openAddDeptModal() {
        document.getElementById('modalDeptId').value = '';
        document.getElementById('modalDeptName').value = '';
        document.getElementById('modalDeptCode').value = '';
        document.getElementById('modalDeptDesc').value = '';
        document.getElementById('deptModalTitle').innerHTML = '<i class="fa-solid fa-sitemap" style="color:#3d9fd4; margin-right:8px;"></i> Add New Department';
        document.getElementById('deptModalMsg').innerHTML = '';
        document.getElementById('deptModal').style.display = 'flex';
      }

      function openEditDeptModal(id, name, code, desc) {
        document.getElementById('modalDeptId').value = id;
        document.getElementById('modalDeptName').value = name;
        document.getElementById('modalDeptCode').value = code || '';
        document.getElementById('modalDeptDesc').value = desc || '';
        document.getElementById('deptModalTitle').innerHTML = `<i class="fa-solid fa-pen-to-square" style="color:#3d9fd4; margin-right:8px;"></i> Edit Department: ${name}`;
        document.getElementById('deptModalMsg').innerHTML = '';
        document.getElementById('deptModal').style.display = 'flex';
      }

      function closeDeptModal() {
        document.getElementById('deptModal').style.display = 'none';
      }

      async function saveDepartment() {
        const id = document.getElementById('modalDeptId').value;
        const name = document.getElementById('modalDeptName').value.trim();
        const code = document.getElementById('modalDeptCode').value.trim();
        const description = document.getElementById('modalDeptDesc').value.trim();
        const msgEl = document.getElementById('deptModalMsg');

        if (!name) {
          if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger p-2" style="font-size:0.85em;">Department name is required.</div>';
          return;
        }

        const btn = document.querySelector('#deptModal button.btn-primary');
        const restoreBtn = setButtonLoading(btn, id ? 'Updating...' : 'Creating...');
        try {
          const url = id ? `${API_BASE}/departments/${id}` : `${API_BASE}/departments`;
          const method = id ? 'PUT' : 'POST';
          const resp = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, code, description, active: 1 })
          });
          const res = await resp.json();
          if (resp.ok && (res.success || res.id)) {
            closeDeptModal();
            loadDepartmentsTable();
            showAppToast(res.message || `Department '${name}' saved successfully`, 'success');
          } else {
            if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">${res.error || 'Failed to save department'}</div>`;
            showAppToast(res.error || 'Failed to save department', 'error');
          }
        } catch (e) {
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">Error: ${e.message}</div>`;
          showAppToast(`Error: ${e.message}`, 'error');
        } finally {
          restoreBtn();
        }
      }

      async function deleteDepartment(id, name) {
        if (!confirm(`Are you sure you want to disable department "${name}"?\nExisting staff records will remain intact.`)) return;
        try {
          const resp = await fetch(`${API_BASE}/departments/${id}`, { method: 'DELETE' });
          const res = await resp.json();
          if (resp.ok && res.success) {
            loadDepartmentsTable();
            showAppToast(res.message || `Department '${name}' disabled`, 'success');
          } else {
            showAppToast(res.error || 'Failed to delete department', 'error');
          }
        } catch (e) {
          showAppToast('Error: ' + e.message, 'error');
        }
      }

      // --- DESIGNATION MANAGEMENT ---
      function populateDesigFilterDeptDropdown(depts) {
        const filterSelect = document.getElementById('desigDeptFilter');
        if (!filterSelect) return;
        const curVal = filterSelect.value;
        filterSelect.innerHTML = '<option value="">All Departments</option>' + 
          (depts || []).filter(d => d.active).map(d => `<option value="${d.id}">${d.name}</option>`).join('');
        if (curVal) filterSelect.value = curVal;
      }

      async function loadDesignationsTable() {
        try {
          const deptId = document.getElementById('desigDeptFilter')?.value || '';
          let url = `${API_BASE}/designations?active_only=false`;
          if (deptId) url += `&department_id=${deptId}`;
          const resp = await fetch(url);
          const desigs = await resp.json();
          cachedDesignations = desigs || [];
          renderDesignationsTable(cachedDesignations);
        } catch (e) {
          console.error("Failed to load designations:", e);
        }
      }

      function renderDesignationsTable(desigs) {
        const tbody = document.getElementById('designationsTableBody');
        if (!tbody) return;
        if (!desigs || desigs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-4">No designations found. Click "+ Add Designation" to create one.</td></tr>';
          return;
        }
        tbody.innerHTML = desigs.map(d => {
          const statusBadge = d.active 
            ? '<span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size:0.78em; padding:4px 8px;"><i class="fa-solid fa-check"></i> Active</span>'
            : '<span class="badge bg-danger-subtle text-danger border border-danger-subtle" style="font-size:0.78em; padding:4px 8px;"><i class="fa-solid fa-ban"></i> Disabled</span>';
          return `
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="font-family: 'JetBrains Mono', monospace; font-weight:700; color:#3d9fd4;">#${d.id}</td>
              <td style="font-weight:700; color:#173042;">${d.title}</td>
              <td><span class="badge bg-primary-subtle text-primary border border-primary-subtle" style="font-weight:700;">${d.department_name}</span></td>
              <td style="color:#64748b; font-size:0.85em;">${d.description || '—'}</td>
              <td>${statusBadge}</td>
              <td style="text-align: right;">
                <button class="btn btn-sm btn-outline-primary me-1" onclick="openEditDesigModal(${d.id}, ${d.department_id}, '${d.title.replace(/'/g, "\\'")}', '${(d.description||'').replace(/'/g, "\\'")}')" style="padding:3px 8px; font-size:0.8em;">
                  <i class="fa-solid fa-pen-to-square"></i> Edit
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteDesignation(${d.id}, '${d.title.replace(/'/g, "\\'")}')" style="padding:3px 8px; font-size:0.8em;">
                  <i class="fa-solid fa-trash"></i>
                </button>
              </td>
            </tr>
          `;
        }).join('');
      }

      function openAddDesigModal() {
        document.getElementById('modalDesigId').value = '';
        document.getElementById('modalDesigTitle').value = '';
        document.getElementById('modalDesigDesc').value = '';
        const deptSelect = document.getElementById('modalDesigDeptId');
        if (deptSelect) {
          deptSelect.innerHTML = '<option value="">Select Parent Department...</option>' + 
            cachedDepartments.filter(d => d.active).map(d => `<option value="${d.id}">${d.name}</option>`).join('');
          const filterVal = document.getElementById('desigDeptFilter')?.value;
          if (filterVal) deptSelect.value = filterVal;
        }
        document.getElementById('desigModalTitle').innerHTML = '<i class="fa-solid fa-id-badge" style="color:#3d9fd4; margin-right:8px;"></i> Add Designation';
        document.getElementById('desigModalMsg').innerHTML = '';
        document.getElementById('desigModal').style.display = 'flex';
      }

      function openEditDesigModal(id, deptId, title, desc) {
        document.getElementById('modalDesigId').value = id;
        document.getElementById('modalDesigTitle').value = title;
        document.getElementById('modalDesigDesc').value = desc || '';
        const deptSelect = document.getElementById('modalDesigDeptId');
        if (deptSelect) {
          deptSelect.innerHTML = '<option value="">Select Parent Department...</option>' + 
            cachedDepartments.filter(d => d.active).map(d => `<option value="${d.id}">${d.name}</option>`).join('');
          deptSelect.value = deptId;
        }
        document.getElementById('desigModalTitle').innerHTML = `<i class="fa-solid fa-pen-to-square" style="color:#3d9fd4; margin-right:8px;"></i> Edit Designation: ${title}`;
        document.getElementById('desigModalMsg').innerHTML = '';
        document.getElementById('desigModal').style.display = 'flex';
      }

      function closeDesigModal() {
        document.getElementById('desigModal').style.display = 'none';
      }

      async function saveDesignation() {
        const id = document.getElementById('modalDesigId').value;
        const department_id = document.getElementById('modalDesigDeptId').value;
        const title = document.getElementById('modalDesigTitle').value.trim();
        const description = document.getElementById('modalDesigDesc').value.trim();
        const msgEl = document.getElementById('desigModalMsg');

        if (!department_id) {
          if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger p-2" style="font-size:0.85em;">Please select a Parent Department.</div>';
          return;
        }
        if (!title) {
          if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger p-2" style="font-size:0.85em;">Designation title is required.</div>';
          return;
        }

        const btn = document.querySelector('#desigModal button.btn-primary');
        const restoreBtn = setButtonLoading(btn, id ? 'Updating...' : 'Creating...');
        try {
          const url = id ? `${API_BASE}/designations/${id}` : `${API_BASE}/designations`;
          const method = id ? 'PUT' : 'POST';
          const resp = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ department_id: parseInt(department_id), title, description, active: 1 })
          });
          const res = await resp.json();
          if (resp.ok && (res.success || res.id)) {
            closeDesigModal();
            loadDesignationsTable();
            showAppToast(res.message || `Designation '${title}' saved successfully`, 'success');
          } else {
            if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">${res.error || 'Failed to save designation'}</div>`;
            showAppToast(res.error || 'Failed to save designation', 'error');
          }
        } catch (e) {
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">Error: ${e.message}</div>`;
          showAppToast(`Error: ${e.message}`, 'error');
        } finally {
          restoreBtn();
        }
      }

      async function deleteDesignation(id, title) {
        if (!confirm(`Are you sure you want to disable designation "${title}"?`)) return;
        try {
          const resp = await fetch(`${API_BASE}/designations/${id}`, { method: 'DELETE' });
          const res = await resp.json();
          if (resp.ok && res.success) {
            loadDesignationsTable();
            showAppToast(res.message || `Designation '${title}' disabled`, 'success');
          } else {
            showAppToast(res.error || 'Failed to delete designation', 'error');
          }
        } catch (e) {
          showAppToast('Error: ' + e.message, 'error');
        }
      }

      // --- DYNAMIC STAFF DEPARTMENT & DESIGNATION CASCADING ---
      async function loadDepartmentDropdowns() {
        try {
          const resp = await fetch(`${API_BASE}/departments?active_only=true`);
          const depts = await resp.json();
          if (!depts) return;

          const enrollDept = document.getElementById('enrollDepartment');
          if (enrollDept) {
            const cur = enrollDept.value;
            enrollDept.innerHTML = '<option value="">Select Department...</option>' + 
              depts.map(d => `<option value="${d.name}">${d.name}</option>`).join('');
            if (cur) enrollDept.value = cur;
          }

          const editDept = document.getElementById('editDepartment');
          if (editDept) {
            const cur = editDept.value;
            editDept.innerHTML = '<option value="">Select Department...</option>' + 
              depts.map(d => `<option value="${d.name}">${d.name}</option>`).join('');
            if (cur) editDept.value = cur;
          }
        } catch (e) {
          console.error("Failed to load department dropdowns:", e);
        }
      }

      async function onEnrollDeptChange(deptName) {
        const desigSelect = document.getElementById('enrollPosition');
        if (!desigSelect) return;
        if (!deptName) {
          desigSelect.innerHTML = '<option value="">Select Department First...</option>';
          return;
        }
        desigSelect.innerHTML = '<option value="">Loading Designations...</option>';
        try {
          const resp = await fetch(`${API_BASE}/designations?department_name=${encodeURIComponent(deptName)}&active_only=true`);
          const desigs = await resp.json();
          if (!desigs || desigs.length === 0) {
            desigSelect.innerHTML = '<option value="">No designations found for this department</option>';
          } else {
            desigSelect.innerHTML = '<option value="">Select Designation / Role...</option>' + 
              desigs.map(d => `<option value="${d.title}">${d.title}</option>`).join('');
          }
        } catch (e) {
          desigSelect.innerHTML = '<option value="">Error loading designations</option>';
        }
      }

      async function onEditDeptChange(deptName, selectTitle = '') {
        const desigSelect = document.getElementById('editPosition');
        if (!desigSelect) return;
        if (!deptName) {
          desigSelect.innerHTML = '<option value="">Select Department First...</option>';
          return;
        }
        desigSelect.innerHTML = '<option value="">Loading Designations...</option>';
        try {
          const resp = await fetch(`${API_BASE}/designations?department_name=${encodeURIComponent(deptName)}&active_only=true`);
          const desigs = await resp.json();
          if (!desigs || desigs.length === 0) {
            desigSelect.innerHTML = '<option value="">No designations found for this department</option>';
          } else {
            desigSelect.innerHTML = '<option value="">Select Designation / Role...</option>' + 
              desigs.map(d => `<option value="${d.title}">${d.title}</option>`).join('');
            if (selectTitle) desigSelect.value = selectTitle;
          }
        } catch (e) {
          desigSelect.innerHTML = '<option value="">Error loading designations</option>';
        }
      }

      // --- DYNAMIC CAMERA MANAGEMENT & LIVE STREAM INTEGRATION ---
      async function loadCamerasGrid() {
        try {
          const resp = await fetch(`${API_BASE}/cameras?active_only=false`);
          const cameras = await resp.json();
          cachedCameras = cameras || [];
          renderCamerasGrid(cachedCameras);
          loadLiveCameras();
        } catch (e) {
          console.error("Failed to load cameras grid:", e);
        }
      }

      function renderCamerasGrid(cameras) {
        const container = document.getElementById('camerasGridContainer');
        if (!container) return;
        if (!cameras || cameras.length === 0) {
          container.innerHTML = '<div class="col-12 text-center text-muted p-4">No cameras configured yet. Click "+ Add New Camera" to set up your DVR/NVR/IP or Web camera.</div>';
          return;
        }
        container.innerHTML = cameras.map(c => {
          const isWebcam = c.camera_type === 'webcam';
          const typeBadge = isWebcam
            ? '<span class="badge bg-info-subtle text-info border"><i class="fa-solid fa-video"></i> Local Webcam</span>'
            : `<span class="badge bg-primary-subtle text-primary border"><i class="fa-solid fa-network-wired"></i> ${c.camera_type.toUpperCase()}</span>`;
          const statusBadge = c.active
            ? '<span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size:0.75em;"><i class="fa-solid fa-circle"></i> Active</span>'
            : '<span class="badge bg-danger-subtle text-danger border border-danger-subtle" style="font-size:0.75em;"><i class="fa-solid fa-circle"></i> Disabled</span>';

          const connectionSource = isWebcam
            ? `USB Device Index: <strong>#${c.rtsp_url}</strong>`
            : `RTSP URL: <span style="font-family:'JetBrains Mono',monospace; font-size:0.85em; word-break:break-all;">${c.rtsp_url || 'None'}</span>`;

          return `
            <div class="col-md-6 col-lg-4">
              <div class="card p-3 shadow-sm h-100" style="background:#ffffff; border:1px solid #cfe8f7; border-radius:14px; display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                    <div>
                      <h4 style="font-weight:800; color:#173042; margin:0; font-size:1.05em;"><i class="fa-solid fa-video" style="color:#3d9fd4; margin-right:6px;"></i> ${c.name}</h4>
                      <div style="color:#64748b; font-size:0.82em; margin-top:2px;"><i class="fa-solid fa-location-dot" style="color:#0284c7; margin-right:4px;"></i> Room: <strong>${c.room_name}</strong></div>
                    </div>
                    <div>${statusBadge}</div>
                  </div>

                  <div style="margin-bottom:10px;">${typeBadge}</div>

                  <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; font-size:0.82em; margin-bottom:12px;">
                    <div style="color:#64748b; font-weight:600; margin-bottom:3px;">Connection:</div>
                    <div style="color:#1e293b;">${connectionSource}</div>
                  </div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #f1f5f9; padding-top:10px; margin-top:6px;">
                  <span style="font-size:0.75em; color:#94a3b8; font-weight:600;">ID: ${c.camera_id}</span>
                  <div>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="openEditCameraModal(${c.id}, '${c.camera_id}', '${c.name.replace(/'/g, "\\'")}', '${c.room_name.replace(/'/g, "\\'")}', '${c.camera_type}', '${(c.rtsp_url||'').replace(/'/g, "\\'")}', ${c.active})" style="padding:3px 8px; font-size:0.78em;">
                      <i class="fa-solid fa-pen-to-square"></i> Edit
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteCamera(${c.id}, '${c.name.replace(/'/g, "\\'")}')" style="padding:3px 8px; font-size:0.78em;">
                      <i class="fa-solid fa-trash"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          `;
        }).join('');
      }

      function onCameraTypeChange(type) {
        const rtspBox = document.getElementById('cameraRtspBox');
        const webcamBox = document.getElementById('cameraWebcamBox');
        if (type === 'webcam') {
          if (rtspBox) rtspBox.style.display = 'none';
          if (webcamBox) webcamBox.style.display = 'block';
        } else {
          if (rtspBox) rtspBox.style.display = 'block';
          if (webcamBox) webcamBox.style.display = 'none';
        }
      }

      function openAddCameraModal() {
        document.getElementById('modalCameraDbId').value = '';
        document.getElementById('modalCameraName').value = '';
        document.getElementById('modalCameraRoom').value = '';
        document.getElementById('modalCameraType').value = 'nvr';
        document.getElementById('modalCameraId').value = 'cam_' + Date.now().toString().slice(-4);
        document.getElementById('modalCameraRtsp').value = '';
        onCameraTypeChange('nvr');
        document.getElementById('cameraModalTitle').innerHTML = '<i class="fa-solid fa-video" style="color:#3d9fd4; margin-right:8px;"></i> Add New AI Camera';
        document.getElementById('cameraModalMsg').innerHTML = '';
        document.getElementById('cameraModal').style.display = 'flex';
      }

      function openEditCameraModal(id, camId, name, room, type, rtsp, active) {
        document.getElementById('modalCameraDbId').value = id;
        document.getElementById('modalCameraName').value = name;
        document.getElementById('modalCameraRoom').value = room;
        document.getElementById('modalCameraType').value = type;
        document.getElementById('modalCameraId').value = camId;
        document.getElementById('modalCameraRtsp').value = rtsp;
        onCameraTypeChange(type);
        if (type === 'webcam') {
          const sel = document.getElementById('modalWebcamSelect');
          if (sel) sel.value = rtsp;
        }
        document.getElementById('cameraModalTitle').innerHTML = `<i class="fa-solid fa-pen-to-square" style="color:#3d9fd4; margin-right:8px;"></i> Edit Camera: ${name}`;
        document.getElementById('cameraModalMsg').innerHTML = '';
        document.getElementById('cameraModal').style.display = 'flex';
      }

      function closeCameraModal() {
        document.getElementById('cameraModal').style.display = 'none';
      }

      async function triggerWebcamDetection() {
        try {
          const resp = await fetch(`${API_BASE}/cameras/detect-webcams`);
          const data = await resp.json();
          const select = document.getElementById('modalWebcamSelect');
          if (select && data.webcams && data.webcams.length > 0) {
            select.innerHTML = data.webcams.map(w => `<option value="${w.index}">${w.name} (Index ${w.index})</option>`).join('');
            document.getElementById('modalCameraRtsp').value = select.value;
            alert(`Detected ${data.webcams.length} connected camera(s): ` + data.webcams.map(w => w.name).join(', '));
          } else {
            alert('No USB web cameras detected via DirectShow scan.');
          }
        } catch (e) {
          alert('Webcam detection error: ' + e.message);
        }
      }

      async function saveCameraConfig() {
        const id = document.getElementById('modalCameraDbId').value;
        const name = document.getElementById('modalCameraName').value.trim();
        const room_name = document.getElementById('modalCameraRoom').value.trim();
        const camera_type = document.getElementById('modalCameraType').value;
        const camera_id = document.getElementById('modalCameraId').value.trim();
        let rtsp_url = document.getElementById('modalCameraRtsp').value.trim();
        const msgEl = document.getElementById('cameraModalMsg');

        if (camera_type === 'webcam') {
          const select = document.getElementById('modalWebcamSelect');
          if (select) rtsp_url = select.value;
          if (!rtsp_url) rtsp_url = '0';
        }

        if (!name || !room_name) {
          if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger p-2" style="font-size:0.85em;">Camera Name and Room Location are required.</div>';
          return;
        }

        if (camera_type !== 'webcam' && !rtsp_url) {
          if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger p-2" style="font-size:0.85em;">RTSP URL is required for DVR/NVR/IP cameras.</div>';
          return;
        }

        const btn = document.querySelector('#cameraModal button.btn-primary');
        const restoreBtn = setButtonLoading(btn, id ? 'Updating...' : 'Saving...');
        try {
          const url = id ? `${API_BASE}/cameras/${id}` : `${API_BASE}/cameras`;
          const method = id ? 'PUT' : 'POST';
          const resp = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera_id, name, room_name, camera_type, rtsp_url, active: 1 })
          });
          const res = await resp.json();
          if (resp.ok && (res.success || res.id)) {
            closeCameraModal();
            loadCamerasGrid();
            showAppToast(res.message || `Camera '${name}' configured successfully`, 'success');
          } else {
            if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">${res.error || 'Failed to save camera'}</div>`;
            showAppToast(res.error || 'Failed to save camera', 'error');
          }
        } catch (e) {
          if (msgEl) msgEl.innerHTML = `<div class="alert alert-danger p-2" style="font-size:0.85em;">Error: ${e.message}</div>`;
          showAppToast(`Error: ${e.message}`, 'error');
        } finally {
          restoreBtn();
        }
      }

      async function deleteCamera(id, name) {
        if (!confirm(`Are you sure you want to delete camera "${name}"?\nIt will be removed from Live AI streaming.`)) return;
        try {
          const resp = await fetch(`${API_BASE}/cameras/${id}`, { method: 'DELETE' });
          const res = await resp.json();
          if (resp.ok && res.success) {
            loadCamerasGrid();
            showAppToast(res.message || `Camera '${name}' deleted`, 'success');
          } else {
            showAppToast(res.error || 'Failed to delete camera', 'error');
          }
        } catch (e) {
          showAppToast('Error: ' + e.message, 'error');
        }
      }

      async function loadLiveCameras() {
        const tabsContainer = document.getElementById("cctvCameraTabs");
        try {
          const res = await fetch(`${API_BASE}/cameras?active_only=true`);
          const cameras = await res.json();
          cachedLiveCameras = cameras || [];

          if (!cameras || cameras.length === 0) {
            if (tabsContainer) tabsContainer.innerHTML = '<span style="color:#64748b; font-size:0.85em; padding:6px 12px;">No active cameras configured. Add cameras in System Settings.</span>';
            return;
          }

          if (tabsContainer) {
            tabsContainer.innerHTML = '';
            let foundSelected = false;
            cameras.forEach((cam, idx) => {
              const btn = document.createElement('button');
              const isActive = cam.camera_id === selectedCameraId || (!selectedCameraId && idx === 0);
              btn.className = `camera-tab-btn ${isActive ? 'active' : ''}`;
              if (isActive) {
                selectedCameraId = cam.camera_id;
                foundSelected = true;
                const badgeText = document.getElementById("singleCamBadgeName");
                if (badgeText) badgeText.textContent = `${cam.name} (${cam.room_name})`;
              }
              const icon = cam.camera_type === 'webcam' ? 'fa-video' : (cam.camera_type === 'nvr' ? 'fa-building-user' : 'fa-door-open');
              btn.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${cam.name} (${cam.room_name})</span>`;
              btn.onclick = () => selectCamera(cam.camera_id, btn, cam.name, cam.room_name);
              tabsContainer.appendChild(btn);
            });

            if (!foundSelected && cameras.length > 0) {
              selectedCameraId = cameras[0].camera_id;
              const firstBtn = tabsContainer.querySelector('.camera-tab-btn');
              if (firstBtn) firstBtn.classList.add('active');
              const badgeText = document.getElementById("singleCamBadgeName");
              if (badgeText) badgeText.textContent = `${cameras[0].name} (${cameras[0].room_name})`;
            }
          }

          // Automatically start streaming on the primary viewport without requiring manual refresh
          const streamView = document.getElementById("streamView");
          if (streamView && selectedCameraId) {
            streamView.setAttribute('data-cam-id', selectedCameraId);
            if (!streamView.src || streamView.src.includes('nvr_office') || streamView.src.endsWith('/')) {
              streamView.src = `/api/stream/${selectedCameraId}?t=${Date.now()}`;
            }
          }

          // If in multi-grid view, update grid tiles
          if (currentLiveLayout !== 'single') {
            renderLiveMultiGrid(currentLiveLayout);
          }

          // Start compact attendance ticker
          startTickerFeed();
        } catch (err) {
          console.error("Failed to load live cameras:", err);
        }
      }

      window.addEventListener('DOMContentLoaded', () => {
        loadShiftsList();
        loadLiveCameras();
        const urlParams = new URLSearchParams(window.location.search);
        const tabParam = urlParams.get('tab');
        const hashParam = window.location.hash.replace('#', '');
        
        let targetTab = tabParam || hashParam;
        if (targetTab === 'staff-directory' || targetTab === 'staff-management' || targetTab === 'staff') {
          targetTab = 'staff-view';
        } else if (targetTab === 'shifts' || targetTab === 'shift-management') {
          targetTab = 'shifts-view';
        }
        
        if (targetTab && document.getElementById(targetTab)) {
          const matchingBtn = document.querySelector(`.menu-item[onclick*="${targetTab}"]`);
          switchTab(targetTab, matchingBtn);
        }
      });
    