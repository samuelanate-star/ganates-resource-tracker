import os,tempfile,json,unittest
os.environ.update(SECRET_KEY='x'*40,ADMIN_PASSWORD='ResearchOnly123!',ADMIN_EMAIL='pm@example.test',COOKIE_SECURE='0',DATABASE_URL='sqlite:///'+tempfile.mktemp(suffix='.db'))
import app as mod
from evidence_engine import canonical,overlap
from sqlalchemy import select
from werkzeug.security import generate_password_hash
class ResearchTests(unittest.TestCase):
 def test_workflow(self):
  client=mod.app.test_client()
  with mod.engine.begin() as c:
   manager=c.execute(mod.u.insert().values(name='Manager',email='manager@test',password=generate_password_hash('password12345'),role='manager',version=1)).inserted_primary_key[0]
   dev=c.execute(mod.u.insert().values(name='Developer',email='dev@test',role='resource',manager=manager,version=1)).inserted_primary_key[0]
   outsider=c.execute(mod.u.insert().values(name='Other',email='other@test',role='resource',version=1)).inserted_primary_key[0]
   project=c.execute(mod.p.insert().values(name='Payments',goal='Safe payments')).inserted_primary_key[0]
   task=c.execute(mod.t.insert().values(project=project,owner=dev,title='Validation',acceptance='Tests pass',weight=1)).inserted_primary_key[0]
   c.execute(mod.cr.insert().values(task=task,key='PAY-01',description='Validation passes',weight=1))
  def as_user(uid):
   with client.session_transaction() as s:s.update(uid=uid,version=1,csrf='testcsrf')
  as_user(dev)
  bundle=dict(repository='private-payments',contribution_kind='implementation',patch_id='stable-123',commit='commit-a',criteria=[dict(id='PAY-01',result='pass',artifact='test-run-42')])
  payload=canonical(bundle)
  data=dict(csrf='testcsrf',task=str(task),day=mod.date.today().isoformat(),hours='2',increment='40',outcome='Validation implemented',evidence='PR 42',evidence_bundle=payload)
  self.assertEqual(client.post('/daily',data=data).status_code,302)
  with mod.engine.connect() as c:
   entry=dict(c.execute(select(mod.e)).mappings().first());eid=entry['id'];report=mod.research_report(c,entry);self.assertEqual(report['coverage'],100)
  self.assertEqual(client.get(f'/research/{eid}').status_code,200)
  bundle['commit']='commit-rebased';self.assertTrue(overlap(json.loads(payload),bundle))
  self.assertEqual(client.post(f'/research/{eid}',data=dict(csrf='testcsrf',evidence_bundle=canonical(bundle))).status_code,302)
  as_user(outsider);self.assertEqual(client.get(f'/research/{eid}').status_code,403)
  as_user(manager)
  client.post(f'/review/{eid}',data=dict(csrf='testcsrf',action='verified',note='Checked'))
  with mod.engine.connect() as c:self.assertEqual(c.execute(select(mod.e.c.status)).scalar(),'submitted')
  self.assertEqual(client.get(f'/research/{eid}').status_code,200)
  client.post(f'/review/{eid}',data=dict(csrf='testcsrf',action='verified',note='Evidence reviewed',research_ack='yes'))
  with mod.engine.connect() as c:self.assertEqual(c.execute(select(mod.e.c.status)).scalar(),'verified')
  as_user(dev);self.assertEqual(client.post(f'/research/{eid}',data=dict(csrf='testcsrf',evidence_bundle=payload)).status_code,403)
  as_user(1);self.assertEqual(client.get('/').status_code,200)
  client.post(f'/review/{eid}',data=dict(csrf='testcsrf',action='billable',note='Agreed scope'))
  self.assertEqual(client.get('/export').status_code,200)
  client.post(f'/research/criteria/{task}',data=dict(csrf='testcsrf',key='NEW',weight='1',description='New'))
  with mod.engine.connect() as c:self.assertEqual(len(c.execute(select(mod.cr)).all()),1)
  with mod.engine.begin() as c:
   second=c.execute(mod.e.insert().values(user=dev,task=task,day=mod.date.today().isoformat(),hours=1,increment=10,outcome='Second claim',evidence='PR43',status='submitted')).inserted_primary_key[0]
   c.execute(mod.ev.insert().values(entry=second,payload=payload,sha256='wrong',created='test',actor=dev))
   report=mod.research_report(c,dict(c.execute(select(mod.e).where(mod.e.c.id==second)).mappings().first()))
   self.assertEqual(len(report['matches']),1);self.assertEqual(report['incremental'],0);self.assertTrue(any('integrity' in w for w in report['warnings']))
  # Write representative rendered screen for visual inspection.
  as_user(manager)
  open('/home/user/work/research_screen.html','w').write(client.get(f'/research/{second}').text)
if __name__=='__main__':unittest.main()
