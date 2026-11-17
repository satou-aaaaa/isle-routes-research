"""盤面の形（六角形19枚・頂点54・辺72・港9）と、資源・数字の並べ方。

座標は「とがった頭」の六角形の軸座標 (q, r)。頂点と辺は通し番号で持つ。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# 資源（一般語で呼ぶ）
WOOD, BRICK, WOOL, GRAIN, ORE = range(5)
RESOURCES = (WOOD, BRICK, WOOL, GRAIN, ORE)
RES_NAMES = ("wood", "brick", "wool", "grain", "ore")
DESERT = -1

# 基本セットの地形の枚数（森4・丘3・牧草地4・畑4・山3・砂漠1）
TERRAIN_COUNTS = {WOOD: 4, BRICK: 3, WOOL: 4, GRAIN: 4, ORE: 3, DESERT: 1}
# 数字チップ18枚（7なし、2と12は1枚ずつ）
NUMBER_TOKENS = (2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12)
# 港9か所: 3:1 が4つ、各資源の 2:1 が1つずつ。GENERIC は 3:1
GENERIC = 5
PORT_KINDS = (GENERIC, GENERIC, GENERIC, GENERIC, WOOD, BRICK, WOOL, GRAIN, ORE)

HEX_COORDS = tuple((q, r) for q in range(-2, 3) for r in range(-2, 3) if abs(q + r) <= 2)
HEX_DIRS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))


def dice_ways(n: int) -> int:
    """2つのサイコロの合計が n になる組み合わせの数（36通り中）。"""
    return 6 - abs(7 - n) if 2 <= n <= 12 else 0


@dataclass(frozen=True)
class Topology:
    hex_vertices: tuple[tuple[int, ...], ...]  # 六角形ごとの頂点6つ
    vertex_hexes: tuple[tuple[int, ...], ...]  # 頂点ごとに接する六角形
    vertex_neighbors: tuple[tuple[int, ...], ...]  # 頂点ごとの隣の頂点
    vertex_edges: tuple[tuple[int, ...], ...]  # 頂点ごとに接する辺
    edges: tuple[tuple[int, int], ...]  # 辺 = 頂点2つ
    coastal_edges: tuple[int, ...]  # 海に面した辺（外周を一周する順）
    vertex_xy: tuple[tuple[float, float], ...]  # 描画用の座標
    hex_xy: tuple[tuple[float, float], ...]


def _hex_center(q: int, r: int) -> tuple[float, float]:
    return (math.sqrt(3) * (q + r / 2), 1.5 * r)


def _build_topology() -> Topology:
    key_to_vid: dict[tuple[int, int], int] = {}
    vertex_xy: list[tuple[float, float]] = []
    hex_vertices = []
    for q, r in HEX_COORDS:
        cx, cy = _hex_center(q, r)
        vids = []
        for k in range(6):
            ang = math.radians(60 * k - 30)
            x, y = cx + math.cos(ang), cy + math.sin(ang)
            key = (round(x * 1000), round(y * 1000))
            if key not in key_to_vid:
                key_to_vid[key] = len(vertex_xy)
                vertex_xy.append((x, y))
            vids.append(key_to_vid[key])
        hex_vertices.append(tuple(vids))

    nv = len(vertex_xy)
    vertex_hexes: list[list[int]] = [[] for _ in range(nv)]
    edge_set: dict[tuple[int, int], int] = {}
    edge_hex_count: dict[int, int] = {}
    for h, vids in enumerate(hex_vertices):
        for v in vids:
            vertex_hexes[v].append(h)
        for k in range(6):
            a, b = vids[k], vids[(k + 1) % 6]
            e = (min(a, b), max(a, b))
            if e not in edge_set:
                edge_set[e] = len(edge_set)
            eid = edge_set[e]
            edge_hex_count[eid] = edge_hex_count.get(eid, 0) + 1
    edges = tuple(sorted(edge_set, key=edge_set.get))
    vertex_neighbors: list[list[int]] = [[] for _ in range(nv)]
    vertex_edges: list[list[int]] = [[] for _ in range(nv)]
    for eid, (a, b) in enumerate(edges):
        vertex_neighbors[a].append(b)
        vertex_neighbors[b].append(a)
        vertex_edges[a].append(eid)
        vertex_edges[b].append(eid)

    coastal = [e for e, c in edge_hex_count.items() if c == 1]

    def angle(eid: int) -> float:
        a, b = edges[eid]
        mx = (vertex_xy[a][0] + vertex_xy[b][0]) / 2
        my = (vertex_xy[a][1] + vertex_xy[b][1]) / 2
        return math.atan2(my, mx)

    coastal.sort(key=angle)
    return Topology(
        hex_vertices=tuple(hex_vertices),
        vertex_hexes=tuple(tuple(x) for x in vertex_hexes),
        vertex_neighbors=tuple(tuple(x) for x in vertex_neighbors),
        vertex_edges=tuple(tuple(x) for x in vertex_edges),
        edges=edges,
        coastal_edges=tuple(coastal),
        vertex_xy=tuple(vertex_xy),
        hex_xy=tuple(_hex_center(q, r) for q, r in HEX_COORDS),
    )


TOPO = _build_topology()
N_HEX = len(HEX_COORDS)
N_VERTEX = len(TOPO.vertex_xy)
N_EDGE = len(TOPO.edges)

# 港の辺: 外周30辺から、ほぼ等間隔に9つ（となり合う港が頂点を共有しない）
PORT_EDGES = tuple(
    TOPO.coastal_edges[(i * len(TOPO.coastal_edges)) // len(PORT_KINDS)]
    for i in range(len(PORT_KINDS))
)


def _hex_neighbors() -> tuple[tuple[int, ...], ...]:
    index = {c: i for i, c in enumerate(HEX_COORDS)}
    out = []
    for q, r in HEX_COORDS:
        out.append(
            tuple(index[(q + dq, r + dr)] for dq, dr in HEX_DIRS if (q + dq, r + dr) in index)
        )
    return tuple(out)


HEX_NEIGHBORS = _hex_neighbors()


@dataclass(frozen=True)
class Layout:
    """1局ぶんの盤面: 六角形ごとの資源と数字、港の種類。"""

    terrain: tuple[int, ...]  # 資源 or DESERT
    number: tuple[int, ...]  # 数字（砂漠は 0）
    ports: tuple[int, ...]  # PORT_EDGES と同じ順の港の種類
    desert: int

    def vertex_port(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for eid, kind in zip(PORT_EDGES, self.ports, strict=True):
            for v in TOPO.edges[eid]:
                out[v] = kind
        return out


def random_layout(rng: random.Random) -> Layout:
    """地形・数字・港をランダムに並べる。6と8は隣り合わせない。"""
    tiles = [t for t, n in TERRAIN_COUNTS.items() for _ in range(n)]
    while True:
        rng.shuffle(tiles)
        nums = list(NUMBER_TOKENS)
        rng.shuffle(nums)
        number = []
        it = iter(nums)
        for t in tiles:
            number.append(0 if t == DESERT else next(it))
        red = {h for h, n in enumerate(number) if n in (6, 8)}
        if all(not (red & set(HEX_NEIGHBORS[h])) for h in red):
            break
    ports = list(PORT_KINDS)
    rng.shuffle(ports)
    return Layout(
        terrain=tuple(tiles),
        number=tuple(number),
        ports=tuple(ports),
        desert=tiles.index(DESERT),
    )
