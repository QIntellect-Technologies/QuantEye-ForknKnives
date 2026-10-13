import datetime
import calendar

def is_valid_date(d):
    if not d or type(d) != str:
        return False
    parts = d.split('-')
    if len(parts) != 3: return False
    try:
        y, m, day = map(int, parts)
        if m < 1 or m > 12: return False
        if day < 1 or day > calendar.monthrange(y, m)[1]: return False
        return True
    except:
        return False

def test_leave_filter(req_start, req_end, month_filter, date_filter):
    r_start = req_start if is_valid_date(req_start) else None
    r_end = req_end if is_valid_date(req_end) else r_start
    
    month_match = True
    date_match = True
    
    if month_filter:
        if r_start and r_end:
            y, m = map(int, month_filter.split('-'))
            days_in_month = calendar.monthrange(y, m)[1]
            month_start = f"{y}-{m:02d}-01"
            month_end = f"{y}-{m:02d}-{days_in_month}"
            month_match = (r_start <= month_end and r_end >= month_start)
        else:
            month_match = False
            
    if date_filter:
        if r_start and r_end:
            date_match = (r_start <= date_filter and r_end >= date_filter)
        else:
            date_match = False
            
    return month_match and date_match

print("TEST 1: Month Only (Feb) -> Leave ends on Feb 28th:", test_leave_filter("2026-02-25", "2026-02-28", "2026-02", ""))
print("TEST 2: Date Only -> Leave spans across date:", test_leave_filter("2026-10-10", "2026-10-20", "", "2026-10-15"))
print("TEST 3: Combined -> Month overlaps but Date is outside:", test_leave_filter("2026-10-10", "2026-10-20", "2026-10", "2026-11-05"))
print("TEST 4: Combined -> Month overlaps AND Date overlaps:", test_leave_filter("2026-10-10", "2026-10-20", "2026-10", "2026-10-15"))
print("TEST 5: Empty Filters -> Both match implicitly:", test_leave_filter("2026-10-10", "2026-10-20", "", ""))
print("TEST 6: Invalid Date -> Filter applied to bad date string:", test_leave_filter("2026-02-30", "2026-03-05", "", "2026-03-01"))
print("TEST 7: Missing End Date -> Defaults to Start Date (1-day leave):", test_leave_filter("2026-10-15", None, "", "2026-10-15"))
