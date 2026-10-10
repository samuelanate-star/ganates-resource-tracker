import json
from evidence_engine import canonical, digest, overlap
import os, secrets, csv, io
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template, flash, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Text, select, func, update
app=Flask(__name__)
secret=os.environ.get('SECRET_KEY')
if not secret or len(secret)<32: raise RuntimeError('Set SECRET_KEY to at least 32 random characters')
app.secret_key=secret
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','1')=='1',PERMANENT_SESSION_LIFETIME=timedelta(hours=8),MAX_CONTENT_LENGTH=65536)
url=os.environ.get('DATABASE_URL','sqlite:///resourceflow.db')
if url.startswith(('postgres://','postgresql://')): url='postgresql+psycopg://'+url.split('://',1)[1]
engine=create_engine(url,pool_pre_ping=True)
m=MetaData()
u=Table('users',m,Column('id',Integer,primary_key=True),Column('name',String(120)),Column('email',String(200),unique=True),Column('password',Text),Column('role',String(20)),Column('manager',Integer),Column('version',Integer,default=1))
p=Table('projects',m,Column('id',Integer,primary_key=True),Column('name',String(120)),Column('goal',Text))
t=Table('tasks',m,Column('id',Integer,primary_key=True),Column('project',Integer),Column('owner',Integer),Column('title',String(200)),Column('acceptance',Text),Column('weight',Float))
e=Table('entries',m,Column('id',Integer,primary_key=True),Column('user',Integer),Column('task',Integer),Column('day',String(10)),Column('hours',Float),Column('increment',Float),Column('outcome',Text),Column('evidence',Text),Column('blocker',Text),Column('status',String(25)),Column('note',Text),Column('reviewer',Integer),Column('reviewed',String(40)))
a=Table('audit',m,Column('id',Integer,primary_key=True),Column('actor',Integer),Column('action',Text),Column('created',String(40)))
ev=Table('evidence_versions',m,Column('id',Integer,primary_key=True),Column('entry',Integer),Column('payload',Text),Column('sha256',String(64)),Column('created',String(40)),Column('actor',Integer))
cr=Table('research_criteria',m,Column('id',Integer,primary_key=True),Column('task',Integer),Column('key',String(100)),Column('description',Text),Column('weight',Float))
m.create_all(engine)
with engine.begin() as c:
 if not c.execute(select(u.c.id)).first():
  pw=os.environ.get('ADMIN_PASSWORD','')
  if len(pw)<12: raise RuntimeError('First run needs ADMIN_PASSWORD of at least 12 characters')
  c.execute(u.insert().values(name='Project Manager',email=os.environ.get('ADMIN_EMAIL','').lower().strip(),password=generate_password_hash(pw),role='pm',version=1))
def rows(table):
 with engine.connect() as c:return [dict(x) for x in c.execute(select(table)).mappings()]
def audit(c,action): c.execute(a.insert().values(actor=session.get('uid'),action=action,created=datetime.utcnow().isoformat()))
def current():
 with engine.connect() as c:r=c.execute(select(u).where(u.c.id==session.get('uid',-1))).mappings().first()
 return dict(r) if r and r['version']==session.get('version') else None
@app.before_request
def guard():
 session.setdefault('csrf',secrets.token_hex(24))
 if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf',''),session['csrf']):abort(400)
@app.after_request
def headers(r):
 r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY';r.headers['Cache-Control']='no-store';r.headers['Referrer-Policy']='same-origin';return r
def auth(fn):
 @wraps(fn)
 def inner(*args,**kw):
  if not current():return redirect('/login')
  return fn(*args,**kw)
 return inner
def val(key,limit=2000):
 v=request.form.get(key,'').strip()
 if len(v)>limit:raise ValueError('Text is too long')
 return v
@app.errorhandler(ValueError)
def invalid(err):flash(str(err));return redirect('/')
@app.route('/health')
def health():return {'status':'ok'}
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with engine.connect() as c:r=c.execute(select(u).where(u.c.email==val('email',200).lower())).mappings().first()
  # Signed-session throttle prevents accidental rapid retries; host should rate-limit login for public launch.
  if session.get('tries',0)>=10 and datetime.utcnow().timestamp()-session.get('last_try',0)<300:flash('Please wait five minutes before retrying.');return redirect('/login')
  if r and check_password_hash(r['password'],val('password')):
   session.clear();session.update(uid=r['id'],version=r['version'],csrf=secrets.token_hex(24));session.permanent=True;return redirect('/')
  session['tries']=session.get('tries',0)+1;session['last_try']=datetime.utcnow().timestamp();flash('Email or password is incorrect.')
 return render_template('index.html',view='login',me=None)
@app.post('/logout')
def logout():session.clear();return redirect('/login')
@app.route('/password',methods=['POST'])
@auth
def password():
 me=current();pw=val('new_password')
 if not check_password_hash(me['password'],val('old_password')) or len(pw)<12:raise ValueError('Check current password; new password must be at least 12 characters.')
 with engine.begin() as c:c.execute(update(u).where(u.c.id==me['id']).values(password=generate_password_hash(pw),version=me['version']+1));audit(c,'Password changed')
 session.clear();return redirect('/login')
@app.route('/')
@auth
def home():
 me=current();users=rows(u);tasks=rows(t);projects=rows(p);entries=rows(e)
 allowed={x['id'] for x in users if me['role']=='pm' or x['id']==me['id'] or (me['role']=='manager' and x['manager']==me['id'])}
 entries=[x for x in entries if x['user'] in allowed]
 start=request.args.get('week') or (date.today()-timedelta(days=date.today().weekday())).isoformat()
 try:d=date.fromisoformat(start)
 except ValueError:d=date.today()-timedelta(days=date.today().weekday())
 d=d-timedelta(days=d.weekday());end=d+timedelta(days=6)
 weekly=[x for x in entries if d.isoformat()<=x['day']<=end.isoformat()]
 summaries=[]
 for person in users:
  if person['id'] not in allowed or person['role']!='resource':continue
  es=[x for x in weekly if x['user']==person['id']]
  summaries.append(dict(name=person['name'],days=len({x['day'] for x in es}),hours=sum(x['hours'] for x in es),verified=sum(x['hours'] for x in es if x['status'] in ['verified','billable']),billable=sum(x['hours'] for x in es if x['status']=='billable')))
 progress=[]
 for pr in projects:
  ts=[x for x in tasks if x['project']==pr['id']];weight=sum(x['weight'] for x in ts)
  visible=[x for x in ts if x['owner'] in allowed]
  if me['role']!='pm' and not visible:continue
  # Full project progress is only visible to PM; others see their scoped tasks.
  if me['role']!='pm':ts=visible;weight=sum(x['weight'] for x in ts)
  claimed=verified=0
  for task in ts:
   es=[x for x in entries if x['task']==task['id']]
   claimed+=task['weight']*sum(x['increment'] for x in es if x['status']!='rejected')
   verified+=task['weight']*sum(x['increment'] for x in es if x['status'] in ['verified','billable'])
  progress.append(dict(name=pr['name'],goal=pr['goal'],claimed=round(claimed/weight,1) if weight else 0,verified=round(verified/weight,1) if weight else 0))
 return render_template('index.html',view='home',me=me,users=users,tasks=tasks,projects=projects,entries=sorted(weekly,key=lambda x:(x['day'],x['id']),reverse=True),summaries=summaries,progress=progress,week=d.isoformat(),end=end.isoformat(),names={x['id']:x['name'] for x in users},titles={x['id']:x['title'] for x in tasks},audits=rows(a)[-30:][::-1] if me['role']=='pm' else [])
@app.route('/daily',methods=['GET','POST'])
@auth
def daily():
 me=current()
 if me['role']!='resource':abort(403)
 tasks=[x for x in rows(t) if x['owner']==me['id']]
 if request.method=='POST':
  taskid=int(val('task'));day=date.fromisoformat(val('day'));hours=float(val('hours'));inc=float(val('increment'))
  if day>date.today() or not 0<hours<=24 or not 0<=inc<=100:raise ValueError('Use a valid work date, 0–24 hours and 0–100% increment.')
  if not val('outcome') or not val('evidence'):raise ValueError('Describe the contribution and supply evidence or a ticket reference.')
  with engine.begin() as c:
   # Lock owner so concurrent submissions cannot bypass progress/hour limits.
   c.execute(select(u.c.id).where(u.c.id==me['id']).with_for_update()).first()
   task=c.execute(select(t).where(t.c.id==taskid,t.c.owner==me['id'])).mappings().first()
   if not task:abort(403)
   total=c.execute(select(func.coalesce(func.sum(e.c.increment),0)).where(e.c.task==taskid,e.c.status!='rejected')).scalar()
   h=c.execute(select(func.coalesce(func.sum(e.c.hours),0)).where(e.c.user==me['id'],e.c.day==day.isoformat(),e.c.status!='rejected')).scalar()
   if total+inc>100.000001 or h+hours>24:raise ValueError('Task increments cannot exceed 100%, or daily hours exceed 24. Check previous submissions.')
   inserted=c.execute(e.insert().values(user=me['id'],task=taskid,day=day.isoformat(),hours=hours,increment=inc,outcome=val('outcome'),evidence=val('evidence'),blocker=val('blocker'),status='submitted',note=''))
   if val('evidence_bundle',20000):
    try:payload=canonical(json.loads(val('evidence_bundle',20000)))
    except json.JSONDecodeError:raise ValueError('Use valid evidence JSON.')
    c.execute(ev.insert().values(entry=inserted.inserted_primary_key[0],payload=payload,sha256=digest(payload),created=datetime.utcnow().isoformat(),actor=me['id']))
   audit(c,f'Daily contribution submitted: task {taskid}')
  flash('Update submitted for line-manager review.');return redirect('/')
 return render_template('index.html',view='daily',me=me,tasks=tasks,today=date.today().isoformat())
@app.post('/setup/<kind>')
@auth
def setup(kind):
 if current()['role']!='pm':abort(403)
 with engine.begin() as c:
  if kind=='user':
   role=val('role');manager=int(val('manager') or 0);pw=val('password');email=val('email',200).lower()
   if role not in ['manager','resource'] or len(pw)<12 or '@' not in email or not val('name',120):raise ValueError('Supply name, email, role and a password of at least 12 characters.')
   if c.execute(select(u.c.id).where(u.c.email==email)).first():raise ValueError('Email already exists.')
   if role=='resource' and not c.execute(select(u.c.id).where(u.c.id==manager,u.c.role=='manager')).first():raise ValueError('Assign a line manager first.')
   c.execute(u.insert().values(name=val('name',120),email=email,password=generate_password_hash(pw),role=role,manager=manager,version=1))
  elif kind=='project':
   if not val('name',120) or not val('goal'):raise ValueError('Project name and goal are required.')
   c.execute(p.insert().values(name=val('name',120),goal=val('goal')))
  elif kind=='task':
   owner=int(val('owner'));pr=int(val('project'));weight=float(val('weight'))
   if not c.execute(select(u.c.id).where(u.c.id==owner,u.c.role=='resource')).first() or not c.execute(select(p.c.id).where(p.c.id==pr)).first() or not 0<weight<=1000 or not val('title',200) or not val('acceptance'):raise ValueError('Supply a resource, project, positive weight, title and acceptance criteria.')
   c.execute(t.insert().values(owner=owner,project=pr,title=val('title',200),acceptance=val('acceptance'),weight=weight))
  elif kind=='reset':
   uid=int(val('user'));pw=val('password');target=c.execute(select(u).where(u.c.id==uid)).mappings().first()
   if not target or len(pw)<12:raise ValueError('Select user and use at least 12 characters.')
   c.execute(update(u).where(u.c.id==uid).values(password=generate_password_hash(pw),version=target['version']+1))
  else:abort(404)
  audit(c,f'Admin setup: {kind}')
 flash('Saved.');return redirect('/')
@app.post('/review/<int:entry>')
@auth
def review(entry):
 me=current();action=val('action');note=val('note')
 with engine.begin() as c:
  r=c.execute(select(e).where(e.c.id==entry).with_for_update()).mappings().first()
  if not r:abort(404)
  owner=c.execute(select(u).where(u.c.id==r['user'])).mappings().first()
  if action in ['verified','rejected']:
   if me['role']!='manager' or owner['manager']!=me['id'] or r['status']!='submitted':abort(403)
   if not note:raise ValueError('Add a review note explaining the decision.')
   if action=='verified' and research_report(c,r)['warnings'] and request.form.get('research_ack')!='yes':raise ValueError('Open the evidence review and acknowledge its research warnings before verifying.')
  elif action=='billable':
   if me['role']!='pm' or r['status']!='verified':abort(403)
   if not note:raise ValueError('Add an invoice eligibility note.')
  else:abort(400)
  c.execute(update(e).where(e.c.id==entry).values(status=action,note=note,reviewer=me['id'],reviewed=datetime.utcnow().isoformat()));audit(c,f'Entry {entry}: {r["status"]} → {action}; {note}')
 flash('Review saved.');return redirect('/?week='+r['day'])
@app.get('/export')
@auth
def export():
 if current()['role']!='pm':abort(403)
 start=date.fromisoformat(request.args.get('week',date.today().isoformat()));start-=timedelta(days=start.weekday());end=start+timedelta(days=6)
 names={x['id']:x['name'] for x in rows(u)};titles={x['id']:x['title'] for x in rows(t)}
 out=io.StringIO();w=csv.writer(out);w.writerow(['Entry','Resource','Date','Task','Approved hours','Increment %','Contribution','Evidence','Review note'])
 def safe(x):return "'"+x if isinstance(x,str) and x.startswith(('=','+','-','@')) else x
 for x in rows(e):
  if x['status']=='billable' and start.isoformat()<=x['day']<=end.isoformat():w.writerow([safe(v) for v in [x['id'],names[x['user']],x['day'],titles[x['task']],x['hours'],x['increment'],x['outcome'],x['evidence'],x['note']]])
 return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename=invoice-eligible-{start}.csv'})


def research_report(c,entry):
 versions=[dict(x) for x in c.execute(select(ev).where(ev.c.entry==entry['id']).order_by(ev.c.id)).mappings()]
 criteria=[dict(x) for x in c.execute(select(cr).where(cr.c.task==entry['task'])).mappings()]
 warnings=[];matches=[];payload=None;passed=set()
 if not versions: warnings.append('No structured evidence: outcome coverage cannot be calculated.')
 else:
  latest=versions[-1];payload=json.loads(latest['payload'])
  if digest(latest['payload'])!=latest['sha256']: warnings.append('Stored snapshot integrity mismatch.')
  if len(versions)>1: warnings.append('Evidence has revisions; review all versions before approval.')
  warnings.append('Imported evidence is user supplied. Test results and artifact availability are not independently checked.')
  for item in payload['criteria']:
   if item['result']=='pass':passed.add(item['id'])
  latest_ids=select(func.max(ev.c.id)).group_by(ev.c.entry)
  for other in c.execute(select(ev).where(ev.c.id.in_(latest_ids),ev.c.entry!=entry['id'])).mappings():
   linked=c.execute(select(e).where(e.c.id==other['entry'])).mappings().first()
   if linked and linked['status']!='rejected':
    reason=overlap(payload,json.loads(other['payload']))
    if reason:matches.append(dict(entry=other['entry'],reason=reason))
  if matches:warnings.append('Overlapping contribution fingerprints need review. A match does not establish misconduct.')
 keys={x['key'] for x in criteria}
 if passed-keys:warnings.append('Evidence includes unknown criteria; these do not count towards coverage.')
 total=sum(x['weight'] for x in criteria)
 coverage=round(100*sum(x['weight'] for x in criteria if x['key'] in passed)/total,1) if total else None
 verified=set()
 for row in c.execute(select(e).where(e.c.task==entry['task'],e.c.status.in_(['verified','billable']),e.c.id!=entry['id'])).mappings():
  previous=c.execute(select(ev).where(ev.c.entry==row['id']).order_by(ev.c.id.desc())).mappings().first()
  if previous:
   verified.update(x['id'] for x in json.loads(previous['payload'])['criteria'] if x['result']=='pass')
 incremental=round(100*sum(x['weight'] for x in criteria if x['key'] in passed-verified)/total,1) if total else None
 return dict(versions=versions,criteria=criteria,warnings=warnings,matches=matches,payload=payload,coverage=coverage,incremental=incremental)

def research_entry(c,entryid):
 entry=c.execute(select(e).where(e.c.id==entryid)).mappings().first()
 if not entry:abort(404)
 me=current();owner=c.execute(select(u).where(u.c.id==entry['user'])).mappings().first()
 if not (me['role']=='pm' or me['id']==owner['id'] or (me['role']=='manager' and owner['manager']==me['id'])):abort(403)
 return dict(entry)

@app.route('/research/<int:entryid>',methods=['GET','POST'])
@auth
def research(entryid):
 me=current()
 with engine.begin() as c:
  entry=research_entry(c,entryid)
  if request.method=='POST':
   entry=dict(c.execute(select(e).where(e.c.id==entryid).with_for_update()).mappings().first())
   if me['id']!=entry['user'] or entry['status']!='submitted':abort(403)
   try:payload=canonical(json.loads(val('evidence_bundle',20000)))
   except json.JSONDecodeError:raise ValueError('Use valid evidence JSON.')
   c.execute(ev.insert().values(entry=entryid,payload=payload,sha256=digest(payload),created=datetime.utcnow().isoformat(),actor=me['id']))
   audit(c,f'Evidence snapshot appended to entry {entryid}')
   return redirect('/research/'+str(entryid))
  report=research_report(c,entry)
 return render_template('research.html',me=me,entry=entry,report=report,csrf=session['csrf'])

@app.route('/research/criteria/<int:taskid>',methods=['GET','POST'])
@auth
def criteria(taskid):
 if current()['role']!='pm':abort(403)
 with engine.begin() as c:
  task=c.execute(select(t).where(t.c.id==taskid)).mappings().first()
  if not task:abort(404)
  if request.method=='POST':
   if c.execute(select(e.c.id).where(e.c.task==taskid)).first():raise ValueError('Criteria are locked once work is submitted. Create a new task for a changed baseline.')
   key=val('key',100);weight=float(val('weight'))
   if not key or not val('description') or not 0<weight<=100:raise ValueError('Supply a criterion ID, description and positive weight up to 100.')
   if c.execute(select(cr.c.id).where(cr.c.task==taskid,cr.c.key==key)).first():raise ValueError('Criterion ID already exists on this task.')
   c.execute(cr.insert().values(task=taskid,key=key,description=val('description'),weight=weight));audit(c,f'Criterion {key} added to task {taskid}')
  items=[dict(x) for x in c.execute(select(cr).where(cr.c.task==taskid)).mappings()]
 return render_template('criteria.html',task=task,items=items,csrf=session['csrf'])
