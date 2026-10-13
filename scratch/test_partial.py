import sys
sys.path.insert(0, '.')
import sqlite3
import database as db

print('Testing lines 347 onwards:')
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute('SELECT count(*) FROM users WHERE id = 130')
print('Users count:', c.fetchone()[0])
c.execute('SELECT count(*) FROM embeddings WHERE user_id = 130')
print('Embeddings count:', c.fetchone()[0])
c.execute('SELECT count(*) FROM employee_shift_history WHERE user_id = 130')
print('Shift history count:', c.fetchone()[0])
conn.close()

print('Pragma test:')
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute('PRAGMA integrity_check')
print('Integrity:', c.fetchall())
c.execute('PRAGMA foreign_key_check')
print('FK check:', c.fetchall())
conn.close()

print('Payroll test:')
prev = db.calculate_monthly_payroll('2026-10')
print('Payroll records count:', len(prev.get('records', [])))
imran = next((r for r in prev.get('records', []) if r.get('employee_id') == 38), None)
print('Imran payroll:', imran)
