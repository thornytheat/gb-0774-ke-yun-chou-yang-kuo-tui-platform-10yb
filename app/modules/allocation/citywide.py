"""两级整数取整：层内守底进位，全市对齐配额。

每层每个问项只取精确配额的整数底或底加一（与本层配额相差不足一人），
全市每个问项的合计与全市精确配额（各层配额之和）相差同样不足一人，
各层合计等于本层出票基数，各问项分层合计等于全市整数。

全市整数先按全市精确配额以最大余数规则取得（并列按直达、换乘、其他顺序）；
各层进位再以精确分数费用的最小费用流解出，使层内进位余数总和最大（让利最小）。
若个别极端结构下全市最大余数列合计不可行，退而在全市偏差不足一人的列合计
范围内求解，仍保证两级偏差均不足一人。全程精确分数运算，结果确定可复算。
"""

from fractions import Fraction

from app.config import CHOICES
from app.errors import SurveyProblem

from .remainders import largest_remainders


def controlled_rounding(quotas, totals):
    """quotas: {分层: {问项: Fraction 精确配额}}；totals: {分层: 本层出票基数整数}。

    返回 (layers, city)：每层与全市两级各自的整数、整数底、补 1 问项和余数。
    """
    names = sorted(quotas)
    choices = list(CHOICES)
    floors, remainders, need = {}, {}, {}
    for name in names:
        exact = quotas[name]
        if any(exact[key] < 0 for key in choices) or sum(exact.values()) != totals[name]:
            raise SurveyProblem('BAD_QUOTA', '配额与分层人口不一致')
        floors[name] = {key: int(exact[key]) for key in choices}
        remainders[name] = {key: exact[key] - floors[name][key] for key in choices}
        need[name] = totals[name] - sum(floors[name].values())
    city_exact = {key: sum(quotas[name][key] for name in names) for key in choices}
    city_integers = largest_remainders(city_exact, sum(totals.values()))['integers']
    columns = {key: city_integers[key] - sum(floors[name][key] for name in names) for key in choices}
    try:
        up = _layer_rounding(names, choices, remainders, need, columns)
    except SurveyProblem as exc:
        if exc.code != 'QUOTA_CONFLICT':
            raise
        columns = _city_columns(names, choices, remainders, need)
        city_integers = {key: sum(floors[name][key] for name in names) + columns[key] for key in choices}
        up = _layer_rounding(names, choices, remainders, need, columns)
    layers = {}
    for name in names:
        integers = {key: floors[name][key] + up[name][key] for key in choices}
        layers[name] = dict(integers=integers, floors=floors[name],
                            winners=[key for key in choices if up[name][key]],
                            remainders={key: str(remainders[name][key]) for key in choices})
    city_floors = {key: int(city_exact[key]) for key in choices}
    city = dict(quotas={key: str(city_exact[key]) for key in choices},
                integers=city_integers, floors=city_floors,
                winners=[key for key in choices if city_integers[key] > city_floors[key]],
                remainders={key: str(city_exact[key] - city_floors[key]) for key in choices})
    return layers, city


def _layout(names, choices):
    size = 1 + len(names) + len(choices) + 1
    layer_node = {name: 1 + index for index, name in enumerate(names)}
    choice_node = {key: 1 + len(names) + index for index, key in enumerate(choices)}
    return size, 0, size - 1, layer_node, choice_node


def _city_columns(names, choices, remainders, need):
    """兜底：在全市偏差不足一人的范围内，求各问项应进位的层数（列合计增量）。

    每列先铺余数和下限（费用 -1，必然饱和），再为余数和小数部分提供一格
    进位容量（费用为小数部分的相反数），使全市进位落在全市余数最大的问项上。
    """
    size, source, sink, layer_node, choice_node = _layout(names, choices)
    edges, sink_edges = [], []
    for name in names:
        edges.append((source, layer_node[name], need[name], Fraction()))
    for name in names:
        for key in choices:
            if remainders[name][key] > 0:
                edges.append((layer_node[name], choice_node[key], 1, Fraction()))
    for key in choices:
        exact = sum(remainders[name][key] for name in names)
        base = int(exact)
        sink_edges.append((key, len(edges)))
        edges.append((choice_node[key], sink, base, Fraction(-1)))
        if exact > base:
            sink_edges.append((key, len(edges)))
            edges.append((choice_node[key], sink, 1, base - exact))
    used = _min_cost_flow(size, edges, source, sink, sum(need.values()))
    columns = dict.fromkeys(choices, 0)
    for key, index in sink_edges:
        columns[key] += used[index]
    return columns


def _layer_rounding(names, choices, remainders, need, columns):
    """在全市列合计既定下，求层内进位余数总和最大的 0-1 进位矩阵。"""
    size, source, sink, layer_node, choice_node = _layout(names, choices)
    edges, cell_edges = [], {}
    for name in names:
        edges.append((source, layer_node[name], need[name], Fraction()))
    for name in names:
        for key in choices:
            if remainders[name][key] > 0:
                cell_edges[(name, key)] = len(edges)
                edges.append((layer_node[name], choice_node[key], 1, -remainders[name][key]))
    for key in choices:
        edges.append((choice_node[key], sink, columns[key], Fraction()))
    used = _min_cost_flow(size, edges, source, sink, sum(need.values()))
    up = {name: dict.fromkeys(choices, 0) for name in names}
    for (name, key), index in cell_edges.items():
        up[name][key] = used[index]
    return up


def _min_cost_flow(size, edges, source, sink, target):
    """连续最短路最小费用流。容量为整数、费用为精确分数，松弛顺序固定，结果确定。"""
    graph = [[] for _ in range(size)]
    refs = []
    for u, v, capacity, cost in edges:
        refs.append((u, len(graph[u]), capacity))
        graph[u].append([v, capacity, cost, len(graph[v])])
        graph[v].append([u, 0, -cost, len(graph[u]) - 1])
    flow = 0
    while flow < target:
        dist = [None] * size
        dist[source] = Fraction()
        parent = [None] * size
        for _ in range(size):
            relaxed = False
            for u in range(size):
                if dist[u] is None:
                    continue
                for index, (v, capacity, cost, _) in enumerate(graph[u]):
                    if capacity > 0 and (dist[v] is None or dist[u] + cost < dist[v]):
                        dist[v] = dist[u] + cost
                        parent[v] = (u, index)
                        relaxed = True
            if not relaxed:
                break
        if parent[sink] is None:
            raise SurveyProblem('QUOTA_CONFLICT', '分层配额与全市配额无法同时对齐')
        node, amount = sink, target - flow
        while node != source:
            u, index = parent[node]
            amount = min(amount, graph[u][index][1])
            node = u
        node = sink
        while node != source:
            u, index = parent[node]
            edge = graph[u][index]
            edge[1] -= amount
            graph[node][edge[3]][1] += amount
            node = u
        flow += amount
    return [capacity - graph[u][index][1] for u, index, capacity in refs]
