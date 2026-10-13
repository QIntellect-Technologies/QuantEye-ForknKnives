with open('database.py', encoding='utf-8') as f:
    c = f.read()

import re
# Find calculate_monthly_payroll
start_idx = c.find('def calculate_monthly_payroll')
end_idx = c.find('def finalize_monthly_payroll')
payroll_code = c[start_idx:end_idx]

print("Length of calculate_monthly_payroll:", len(payroll_code))
print("Does it mention 'overtime'?", 'overtime' in payroll_code.lower())
print("Does it mention 'ot_rate'?", 'ot_rate' in payroll_code.lower())
print("Does it mention 'allowances'?", 'allowances' in payroll_code.lower())
print("Does it mention 'deductions'?", 'deductions' in payroll_code.lower())
print("Does it query the 'overtime' table?", 'FROM overtime' in payroll_code or 'from overtime' in payroll_code.lower())

# Check finalize_monthly_payroll
end_finalize = c.find('def _persist_draft_monthly_payroll', end_idx)
finalize_code = c[end_idx:end_finalize]
print("\nDoes finalize_monthly_payroll mention 'overtime'?", 'overtime' in finalize_code.lower())
