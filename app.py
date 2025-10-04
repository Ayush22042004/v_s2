import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort
from io import BytesIO
from openpyxl import Workbook
from db_pg import exec_sql, migrate_and_seed, install_jinja_filters, parse_ist_local_to_utc, now_utc

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY','dev-secret')
install_jinja_filters(app)
migrate_and_seed()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **k):
        if not session.get('user'):
            return redirect(url_for('login'))
        return f(*a, **k)
    return w

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **k):
        u = session.get('user')
        if not u or u.get('role')!='admin':
            return redirect(url_for('login'))
        return f(*a, **k)
    return w

def classify_elections(rows):
    now = now_utc()
    ongoing, scheduled, ended = [], [], []
    for e in rows:
        st, en = e['start_time'], e['end_time']
        if st <= now <= en: ongoing.append(e)
        elif now < st: scheduled.append(e)
        else: ended.append(e)
    return ongoing, scheduled, ended

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        row = exec_sql('SELECT id,username,role,password FROM users WHERE username=%s',(username,), fetch=True, one=True)
        if row and row['password']==password:
            session['user']={'id':row['id'],'username':row['username'],'role':row['role']}
            return redirect(url_for('admin' if row['role']=='admin' else 'index'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    rows = exec_sql('SELECT * FROM elections ORDER BY start_time DESC', fetch=True)
    ongoing, scheduled, ended = classify_elections(rows)
    return render_template('index.html', ongoing=ongoing, scheduled=scheduled, ended=ended, title='Elections')

@app.route('/vote/<int:election_id>', methods=['GET','POST'])
@login_required
def vote(election_id):
    e = exec_sql('SELECT * FROM elections WHERE id=%s',(election_id,), fetch=True, one=True)
    if not e:
        abort(404)
    now = now_utc()
    if not (e['start_time'] <= now <= e['end_time']):
        return redirect(url_for('index'))
    candidates = exec_sql('SELECT * FROM candidates WHERE election_id=%s ORDER BY id',(election_id,), fetch=True)
    if request.method == 'POST':
        cid = int(request.form.get('candidate_id'))
        uid = session['user']['id']
        exists = exec_sql('SELECT id FROM votes WHERE voter_id=%s AND election_id=%s',(uid,election_id), fetch=True, one=True)
        if not exists:
            exec_sql('INSERT INTO votes(voter_id,candidate_id,election_id) VALUES (%s,%s,%s)',(uid,cid,election_id))
            exec_sql('UPDATE candidates SET votes=votes+1 WHERE id=%s',(cid,))
        return render_template('vote.html', e=e, candidates=candidates, voted=True)
    return render_template('vote.html', e=e, candidates=candidates)

@app.route('/admin')
@admin_required
def admin():
    rows = exec_sql('SELECT * FROM elections ORDER BY start_time DESC', fetch=True)
    ongoing, scheduled, ended = classify_elections(rows)
    return render_template('index.html', ongoing=ongoing, scheduled=scheduled, ended=ended, title='Admin')

@app.route('/schedule', methods=['GET','POST'])
@admin_required
def schedule():
    created=False
    if request.method=='POST':
        title=request.form['title'].strip()
        category=request.form['category'].strip()
        limit=int(request.form['candidate_limit'])
        st=parse_ist_local_to_utc(request.form['start_time'])
        en=parse_ist_local_to_utc(request.form['end_time'])
        exec_sql('INSERT INTO elections(title,category,start_time,end_time,candidate_limit) VALUES (%s,%s,%s,%s,%s)',(title,category,st,en,limit))
        created=True
    return render_template('schedule.html', created=created)

@app.route('/results')
@admin_required
def results():
    sql = (
    "SELECT e.title AS election_title, c.name AS candidate_name, c.votes AS votes "
    "FROM candidates c JOIN elections e ON e.id=c.election_id "
    "WHERE e.end_time < NOW() ORDER BY e.end_time DESC, votes DESC, candidate_name"
    )
    rows = exec_sql(sql, fetch=True)
    return render_template('results.html', rows=rows)

@app.route('/export.xlsx')
@admin_required
def export_excel():
    rows = exec_sql('SELECT * FROM elections ORDER BY start_time DESC', fetch=True)
    ongoing, scheduled, ended = classify_elections(rows)
    wb = Workbook()
    for name, data in (('Ongoing',ongoing),('Scheduled',scheduled),('Ended',ended)):
        ws = wb.create_sheet(title=name)
        ws.append(['ID','Title','Category','Start (UTC)','End (UTC)','Candidate Limit'])
        for e in data:
            ws.append([e['id'], e['title'], e['category'], e['start_time'], e['end_time'], e['candidate_limit']])
    if 'Sheet' in wb.sheetnames: del wb['Sheet']
    bio=BytesIO(); wb.save(bio); bio.seek(0)
    return send_file(bio, as_attachment=True, download_name='elections.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__=='__main__':
    app.run(debug=True, port=5000)