const getLeaveStatusEntries = () => [{}]; // Mock

function testFilter(req_start, req_end, monthFilter, dateFilter) {
    const req = { start_date: req_start, end_date: req_end };
    
    // Exact logic from index.html (with the correction for missing vs invalid end_date)
    let monthMatch = true;
    let dateMatch = true;
    
    const isValidDate = (d) => {
      if (!d || typeof d !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(d)) return false;
      const [y, m, day] = d.split('-').map(Number);
      const dateObj = new Date(y, m - 1, day);
      return dateObj.getFullYear() === y && dateObj.getMonth() === m - 1 && dateObj.getDate() === day;
    };
    
    const rStart = isValidDate(req.start_date) ? req.start_date : null;
    // Fix: only fallback to rStart if end_date is strictly missing/empty. If invalid string, it becomes null.
    const isMissingEnd = (req.end_date === null || req.end_date === undefined || req.end_date === "");
    const rEnd = isMissingEnd ? rStart : (isValidDate(req.end_date) ? req.end_date : null);
    
    if (monthFilter) {
      if (rStart && rEnd) {
        const [fYear, fMonth] = monthFilter.split('-').map(Number);
        const daysInMonth = new Date(fYear, fMonth, 0).getDate();
        const fMonthStr = String(fMonth).padStart(2, '0');
        const monthStart = `${fYear}-${fMonthStr}-01`;
        const monthEnd = `${fYear}-${fMonthStr}-${daysInMonth}`;
        monthMatch = (rStart <= monthEnd && rEnd >= monthStart);
      } else {
        monthMatch = false; 
      }
    }
    
    if (dateFilter) {
      if (rStart && rEnd) {
         dateMatch = (rStart <= dateFilter && rEnd >= dateFilter);
      } else {
         dateMatch = false; 
      }
    }
    
    return monthMatch && dateMatch;
}

console.log("TEST 1: Month Only (Feb) -> Leave ends on Feb 28th:", testFilter("2026-02-25", "2026-02-28", "2026-02", ""));
console.log("TEST 2: Date Only -> Leave spans across date:", testFilter("2026-10-10", "2026-10-20", "", "2026-10-15"));
console.log("TEST 3: Combined -> Month overlaps but Date is outside:", testFilter("2026-10-10", "2026-10-20", "2026-10", "2026-11-05"));
console.log("TEST 4: Combined -> Month overlaps AND Date overlaps:", testFilter("2026-10-10", "2026-10-20", "2026-10", "2026-10-15"));
console.log("TEST 5: Empty Filters -> Both match implicitly:", testFilter("2026-10-10", "2026-10-20", "", ""));
console.log("TEST 6: Invalid Date (Feb 30):", testFilter("2026-02-30", "2026-03-05", "", "2026-03-01"));
console.log("TEST 7: Missing End Date -> Defaults to Start Date (1-day leave):", testFilter("2026-10-15", "", "", "2026-10-15"));
console.log("TEST 8: Invalid End Date -> Fails match entirely:", testFilter("2026-10-15", "invalid", "", "2026-10-15"));
