from app.config import LEGACY_SPEC, SPEC
from app.errors import SurveyProblem
from app.modules.allocation import legacy as legacy_allocation
from app.modules.allocation.service import expand
from app.modules.balance import legacy as legacy_balance
from app.modules.balance.service import review
from app.modules.frame.service import align
from app.modules.returns.service import collect
from app.modules.weights.service import calibration

STAGES = ('returns','frame','weights','allocation','balance')

# 各规则版本的扩推与对账口径；旧版本归档复算时沿用原口径
VERSIONS = {LEGACY_SPEC: (legacy_allocation.expand, legacy_balance.review),
            SPEC: (expand, review)}


def run(tables, until='balance', version=SPEC):
    if version not in VERSIONS:
        raise SurveyProblem('BAD_VERSION','规则版本不受支持',409)
    expand_stage, review_stage = VERSIONS[version]
    outputs = {'returns':collect(tables['returns'])}
    steps = (
        ('frame', lambda: align(outputs['returns'],tables['frame'])),
        ('weights', lambda: calibration(outputs['frame'])),
        ('allocation', lambda: expand_stage(outputs['weights'])),
        ('balance', lambda: review_stage(outputs['returns'],outputs['frame'],outputs['weights'],outputs['allocation'])),
    )
    for key, execute in steps:
        if until in outputs:
            break
        outputs[key] = execute()
    return outputs
