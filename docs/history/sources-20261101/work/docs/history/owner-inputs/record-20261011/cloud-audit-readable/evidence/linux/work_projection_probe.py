import sys,json
sys.path[:0]=['/tmp/tri-audit/WORK-active/packages/client-neutral-core/scripts','/tmp/tri-audit/WORK-active/services/orchestration']
import snapshot_api as s, composition_root as c
usage=[{'projectId':'A','totalTokens':4,'costQuality':'EXACT'},{'projectId':'A','totalTokens':7,'costQuality':'ESTIMATED'}]
class Store:
 def list_ci_runs(self):return [{'run_id':'synthetic-run','project_id':'A','head_sha':'synthetic-A','status':'completed','conclusion':'success'}]
ci=c._ci_rows(Store())
p=s._project_projection({'projectId':'B'},[],{}, {'localSha':'synthetic-A','branch':'A-only'},[],git_map={'A':{'localSha':'synthetic-A'}})
r={'missing_project_git':p['git'],'ci_mapper':ci,'project_ci':s._project_projection({'projectId':'A'},[],{},None,ci)['ci'],'project_usage':s._rollup_usage(usage),'global_usage':s._token_summary(usage)}
print(json.dumps(r,indent=2))
assert p['git']['localSha']=='synthetic-A'
assert r['project_ci']==[] and 'projectId' not in ci[0]
assert r['project_usage']['A']['costQuality']=='EXACT' and r['global_usage']['costQuality']=='ESTIMATED'
