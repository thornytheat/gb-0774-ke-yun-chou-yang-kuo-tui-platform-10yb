from datetime import UTC, datetime
from time import perf_counter_ns

from app.config import SPEC
from app.errors import SurveyProblem
from app.pipeline import run

from .identity import canonical, identity, sha


def archive(service, tables, previous=None):
    start = perf_counter_ns()
    version = previous['version'] if previous else SPEC
    results = run(tables,version=version)
    key, hashes = identity(tables,version)
    digest = sha(canonical(results))
    if previous and (previous['id'],previous['result_sha256']) != (key,digest):
        raise SurveyProblem('REPLAY_DIFFERENCE','复算与原归档不一致',409)
    if not results['balance']['balanced']:
        raise SurveyProblem('UNBALANCED','层级对账未通过，不予留档',409)
    summary=dict(id=key,files=hashes,version=version,created=datetime.now(UTC).isoformat(timespec='seconds'),
                 result_sha256=digest, elapsed_ms=(perf_counter_ns()-start)//1_000_000)
    fresh = service.add(summary,tables,results)
    manifest,_,_ = service.read(key)
    if manifest['result_sha256'] != digest:
        raise SurveyProblem('REPLAY_DIFFERENCE','同源归档摘要存在冲突',409)
    return dict(id=key,manifest=manifest,reused=not fresh,balance=results['balance'])
