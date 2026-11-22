from fractions import Fraction

from app.config import CHOICES

from .citywide import controlled_rounding


def expand(calibrated):
    quotas, totals, meta = {}, {}, {}
    unknown = 0
    for name, layer in calibrated['layers'].items():
        unobserved = layer['population'] if layer['status']=='zero_response' else 0
        quotas[name] = {key:Fraction(layer['quotas'][key]) for key in CHOICES}
        totals[name] = layer['population']-unobserved
        meta[name] = dict(population=layer['population'],unobserved=unobserved,status=layer['status'])
        unknown += unobserved
    cells, city = controlled_rounding(quotas,totals)
    layers, total = {}, dict.fromkeys(CHOICES,0)
    for name,row in cells.items():
        layers[name] = {**row,**meta[name]}
        for key,value in row['integers'].items():
            total[key] += value
    return dict(layers=layers, totals=total, city=city, unknown=unknown, estimated=sum(total.values()))
