import sqlite3
conn = sqlite3.connect('db/medical_reports.db')
c = conn.cursor()
c.execute('PRAGMA table_info(reports)')
cols = [col[1] for col in c.fetchall()]
print('Columns:', cols)
if 'submitted_by_user_id' not in cols:
    c.execute('ALTER TABLE reports ADD COLUMN submitted_by_user_id INTEGER')
    print('Column added!')
else:
    print('Column exists')
conn.commit()
conn.close()
print('Done!')






