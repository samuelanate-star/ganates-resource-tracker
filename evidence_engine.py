"""Offline research evidence matching. Does not establish authorship or hours."""
import json, hashlib

def canonical(bundle):
    if not isinstance(bundle,dict): raise ValueError('Evidence must be a JSON object.')
    required=['repository','contribution_kind','patch_id','commit','criteria']
    if any(not bundle.get(k) for k in required): raise ValueError('Evidence requires repository, contribution_kind, patch_id, commit and criteria.')
    if bundle['contribution_kind'] not in ['implementation','testing','review']: raise ValueError('Unknown contribution kind.')
    if not isinstance(bundle['criteria'],list) or len(bundle['criteria'])>50: raise ValueError('Criteria must be a list of at most 50 items.')
    for item in bundle['criteria']:
        if not isinstance(item,dict) or not item.get('id') or item.get('result') not in ['pass','fail','pending'] or not item.get('artifact'): raise ValueError('Each criterion needs id, pass/fail/pending result and an artifact reference.')
    for key in ['repository','patch_id','commit']:
        if not isinstance(bundle[key],str) or len(bundle[key])>500: raise ValueError('Invalid evidence identifier.')
    return json.dumps(bundle,sort_keys=True,separators=(',',':'))

def digest(text): return hashlib.sha256(text.encode()).hexdigest()

def overlap(left,right):
    if left['repository'].strip().rstrip('/') != right['repository'].strip().rstrip('/'): return None
    if left['patch_id']!=right['patch_id']: return None
    if left['contribution_kind']==right['contribution_kind']: return 'Same stable patch fingerprint and contribution kind; possible duplicate claim.'
    return 'Same patch, different contribution kind; assess whether separate work is evidenced.'
