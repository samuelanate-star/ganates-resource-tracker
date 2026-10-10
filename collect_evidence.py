"""Run locally in a trusted repository; never sends source code to Ganates."""
import argparse,subprocess,json
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--commit',required=True);p.add_argument('--repository-id',required=True);p.add_argument('--criterion',required=True);p.add_argument('--artifact',required=True);p.add_argument('--result',choices=['pass','fail','pending'],default='pending');p.add_argument('--kind',choices=['implementation','testing','review'],default='implementation');args=p.parse_args()
def git(*parts):return subprocess.check_output(['git','-C',args.repo,*parts],text=True)
commit=git('rev-parse','--verify',args.commit+'^{commit}').strip()
patch=git('show','--format=','--no-ext-diff',commit)
r=subprocess.run(['git','patch-id','--stable'],input=patch,text=True,capture_output=True,check=True)
if not r.stdout.strip():raise SystemExit('No patch fingerprint. Use a non-empty, non-merge change.')
print(json.dumps(dict(repository=args.repository_id,commit=commit,patch_id=r.stdout.split()[0],contribution_kind=args.kind,criteria=[dict(id=args.criterion,result=args.result,artifact=args.artifact)]),indent=2))
