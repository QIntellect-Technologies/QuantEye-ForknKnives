const fs = require('fs');

const html = fs.readFileSync('templates/index.html', 'utf8');

const filterLeavesTableStr = html.match(/function filterLeavesTable\(\) \{([\s\S]*?)\n    \}/)[0];

const _allLeaveRequests = [
  { id: 1, user_id: 101, user_name: 'Alice', status: 'pending', start_date: '2026-10-01', end_date: '2026-10-05' },
  { id: 2, user_id: 102, user_name: 'Bob', status: 'approved', start_date: '2026-10-02', end_date: '2026-10-02' },
  { id: 3, user_id: 103, user_name: 'Charlie', status: 'partially_approved', start_date: '2026-10-10', end_date: '2026-10-12' },
  { id: 4, user_id: 101, user_name: 'Alice', status: 'rejected', start_date: '2026-11-01', end_date: '2026-11-02' }
];

let domMocks = {
  'leaveSearch': '',
  'leaveStatusFilter': 'all',
  'leaveMonthFilter': '',
  'leaveDateFilter': '',
  'leavePaginationInfo': ''
};

let _leavePage = 1;
let _leavePageSize = 25;
let _leaveRequestDisplayData = new Map();
let lastInnerHTML = '';
let renderedPagination = false;

global.document = {
  getElementById: (id) => {
    if (id === 'leaveRequestsTableBody') {
      return {
        set innerHTML(val) { lastInnerHTML = val; }
      };
    }
    if (id === 'leavePaginationInfo') {
      return {
        set textContent(val) { domMocks['leavePaginationInfo'] = val; }
      };
    }
    if (id in domMocks) {
      return { value: domMocks[id] };
    }
    return null;
  }
};

global.renderLeavePaginationControls = (id, page, total, cb) => {
    renderedPagination = true;
};
global.escapeHtml = (str) => str;

eval(filterLeavesTableStr);

function runTest(name, state, expectedCount, expectedPagination) {
  Object.assign(domMocks, state);
  _leavePage = 1;
  filterLeavesTable();
  
  // Extract number of rendered rows from lastInnerHTML
  let match = lastInnerHTML.match(/<tr/g);
  let renderedCount = match ? match.length : 0;
  // If it's a "No leave requests found" row
  if (lastInnerHTML.includes("No leave requests found")) renderedCount = 0;
  
  let passed = (renderedCount === expectedCount);
  if (expectedPagination && !domMocks['leavePaginationInfo'].includes(expectedPagination)) {
    passed = false;
  }
  
  console.log(`[${passed ? 'PASS' : 'FAIL'}] ${name}`);
  if (!passed) {
    console.log(`  Expected ${expectedCount} rows, got ${renderedCount}`);
    console.log(`  Pagination info: ${domMocks['leavePaginationInfo']}`);
  }
}

console.log("Running Ticket 2 Tests...");
runTest("All Statuses", { leaveStatusFilter: 'all' }, 4, "Showing 1-4 of 4 requests");
runTest("Pending Only", { leaveStatusFilter: 'pending' }, 1, "Showing 1 of 1 pending leave");
runTest("Approved Only", { leaveStatusFilter: 'approved' }, 1, "Showing 1 of 1 approved leave");
runTest("Partially Approved Only", { leaveStatusFilter: 'partially_approved' }, 1, "Showing 1 of 1 partially_approved leave");
runTest("Rejected Only", { leaveStatusFilter: 'rejected' }, 1, "Showing 1 of 1 rejected leave");

runTest("Pagination Check with Status", { leaveStatusFilter: 'pending' }, 1, "Showing 1 of 1 pending leave across 1 employee");

console.log("Tests complete.");
