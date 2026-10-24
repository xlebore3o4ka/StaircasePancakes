HIDE_X = -9999
HIDE_Y = -9999

FREE_SPAWNS = [
    {"x": 128,   "y": 36},
    {"x": 1279,  "y": 36},
    {"x": 2505,  "y": 36},
    {"x": 3888,  "y": 36},
    {"x": -1263, "y": 36},
    {"x": 128,   "y": 549},
    {"x": 1361,  "y": 36},
]

ZONES = [
    {
        "name": "zone_1",
        "weight": 2,
        "instances": [
            {"n": 1, "objects": [
                {"id": "z1_0_1", "dx": 500, "dy": 124},
                {"id": "z1_1_1", "dx": 82,  "dy": 20},
                {"id": "z1_2_1", "dx": 545, "dy": 124},
                {"id": "z1_3_1", "dx": 455, "dy": 201},
            ]},
            {"n": 2, "objects": [
                {"id": "z1_0_2", "dx": 500, "dy": 124},
                {"id": "z1_1_2", "dx": 82,  "dy": 20},
                {"id": "z1_2_2", "dx": 545, "dy": 124},
                {"id": "z1_3_2", "dx": 455, "dy": 201},
            ]},
            {"n": 3, "objects": [
                {"id": "z1_0_3", "dx": 500, "dy": 124},
                {"id": "z1_1_3", "dx": 82,  "dy": 20},
                {"id": "z1_2_3", "dx": 545, "dy": 124},
                {"id": "z1_3_3", "dx": 455, "dy": 201},
            ]},
        ],
    },
    {
        "name": "zone_2",
        "weight": 1,
        "instances": [
            {"n": 1, "objects": [
                {"id": "z2_0_1", "dx": 50,  "dy": 274},
                {"id": "z2_1_1", "dx": 435, "dy": 574},
                {"id": "z2_2_1", "dx": 820, "dy": 274},
                {"id": "z2_3_1", "dx": 47,  "dy": 198},
                {"id": "z2_4_1", "dx": 52,  "dy": 436},
                {"id": "z2_5_1", "dx": 175, "dy": 574},
                {"id": "z2_6_1", "dx": 658, "dy": 574},
                {"id": "z2_7_1", "dx": 820, "dy": 290},
            ]},
            {"n": 2, "objects": [
                {"id": "z2_0_2", "dx": 50,  "dy": 274},
                {"id": "z2_1_2", "dx": 435, "dy": 574},
                {"id": "z2_2_2", "dx": 820, "dy": 274},
                {"id": "z2_3_2", "dx": 47,  "dy": 198},
                {"id": "z2_4_2", "dx": 52,  "dy": 436},
                {"id": "z2_5_2", "dx": 175, "dy": 574},
                {"id": "z2_6_2", "dx": 658, "dy": 574},
                {"id": "z2_7_2", "dx": 820, "dy": 290},
            ]},
            {"n": 3, "objects": [
                {"id": "z2_0_3", "dx": 50,  "dy": 274},
                {"id": "z2_1_3", "dx": 435, "dy": 574},
                {"id": "z2_2_3", "dx": 820, "dy": 274},
                {"id": "z2_3_3", "dx": 47,  "dy": 198},
                {"id": "z2_4_3", "dx": 52,  "dy": 436},
                {"id": "z2_5_3", "dx": 175, "dy": 574},
                {"id": "z2_6_3", "dx": 658, "dy": 574},
                {"id": "z2_7_3", "dx": 820, "dy": 290},
            ]},
            {"n": 4, "objects": [
                {"id": "z2_0_4", "dx": 50,  "dy": 274},
                {"id": "z2_1_4", "dx": 435, "dy": 574},
                {"id": "z2_2_4", "dx": 820, "dy": 274},
                {"id": "z2_3_4", "dx": 47,  "dy": 198},
                {"id": "z2_4_4", "dx": 52,  "dy": 436},
                {"id": "z2_5_4", "dx": 175, "dy": 574},
                {"id": "z2_6_4", "dx": 658, "dy": 574},
                {"id": "z2_7_4", "dx": 820, "dy": 290},
            ]},
            {"n": 5, "objects": [
                {"id": "z2_0_5", "dx": 50,  "dy": 274},
                {"id": "z2_1_5", "dx": 435, "dy": 574},
                {"id": "z2_2_5", "dx": 820, "dy": 274},
                {"id": "z2_3_5", "dx": 47,  "dy": 198},
                {"id": "z2_4_5", "dx": 52,  "dy": 436},
                {"id": "z2_5_5", "dx": 175, "dy": 574},
                {"id": "z2_6_5", "dx": 658, "dy": 574},
                {"id": "z2_7_5", "dx": 820, "dy": 290},
            ]},
        ],
    },
    {
        "name": "zone_3",
        "weight": 1,
        "instances": [
            {"n": 1, "objects": [
                {"id": "z3_0_1", "dx": 380, "dy": 394},
                {"id": "z3_1_1", "dx": 104, "dy": 205},
                {"id": "z3_2_1", "dx": 111, "dy": 125},
                {"id": "z3_3_1", "dx": 104, "dy": 296},
                {"id": "z3_4_1", "dx": 655, "dy": 205},
            ]},
        ],
    },
]


def _place(ctx, inst, ax, ay, label):
    for obj in inst["objects"]:
        h = ctx.by_id(obj["id"])
        if h is None:
            ctx.log(f"[{label}] нет объекта {obj['id']}")
            continue
        ctx.move_to(h, x=ax + obj["dx"], y=ay + obj["dy"], dur=0, ease="linear")


def _hide(ctx, inst, label=""):
    for obj in inst["objects"]:
        h = ctx.by_id(obj["id"])
        if h is None:
            ctx.log(f"[{label}] hide: нет объекта {obj['id']}")
            continue
        ctx.move_to(h, x=HIDE_X, y=HIDE_Y, dur=0, ease="linear")


def on_load(ctx):
    remaining = {i: list(z["instances"]) for i, z in enumerate(ZONES)}

    for spawn_i, sp in enumerate(FREE_SPAWNS):
        pool = [(i, ZONES[i]) for i in remaining if remaining[i]]
        if not pool:
            ctx.log(f"spawn #{spawn_i}: свободных копий больше нет")
            continue

        total = sum(z["weight"] for _, z in pool)
        roll = ctx.random.uniform(0, total)
        acc = 0.0
        chosen_i = pool[-1][0]
        for i, z in pool:
            acc += z["weight"]
            if roll <= acc:
                chosen_i = i
                break

        inst = remaining[chosen_i].pop(0)
        zone = ZONES[chosen_i]
        _place(ctx, inst, sp["x"], sp["y"], zone["name"])
        ctx.log(
            f"spawn #{spawn_i} ({sp['x']},{sp['y']}) → "
            f"{zone['name']} n={inst['n']}"
        )

    for i, insts in remaining.items():
        for inst in insts:
            _hide(ctx, inst, ZONES[i]["name"])
            ctx.log(f"hide {ZONES[i]['name']} n={inst['n']}")