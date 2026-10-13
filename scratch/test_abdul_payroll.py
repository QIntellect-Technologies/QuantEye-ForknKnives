import sys
sys.path.append('.')
import database
payroll = database.calculate_monthly_payroll('2026-10')
abdul_payroll = next((r for r in payroll['records'] if r['employee_id'] == 46), None)
print(abdul_payroll)
