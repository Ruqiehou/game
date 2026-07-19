from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ck_engine.world.world_state import World


@dataclass
class Effect:
    kind: str
    amount: float = 0.0
    text: str = ""

    def apply(self, world: World, who: int) -> None:
        c = world.character(who)
        if not c:
            return
        if self.kind == "gold":
            c.add_gold(self.amount)
        elif self.kind == "prestige":
            c.add_prestige(self.amount)
        elif self.kind == "piety":
            c.piety = max(0.0, c.piety + self.amount)
        elif self.kind == "stress":
            c.add_stress(int(self.amount))
        elif self.kind == "health":
            c.health += self.amount
        elif self.kind == "trait":
            tid = int(self.amount)
            if tid not in c.traits:
                c.traits.append(tid)
        elif self.kind == "log" and self.text:
            world.push_log(self.text)


@dataclass
class EventChoice:
    id: int
    text: str
    effects: List[Effect]
    ai_weight: float = 5.0


@dataclass
class EventDef:
    id: int
    title: str
    description: str
    weight: float
    cooldown_days: int
    major: bool
    choices: List[EventChoice]
    requires_ruler: bool = True
    requires_adult: bool = True
    min_gold: float = 0.0
    requires_married: bool = False


@dataclass
class EventInstance:
    event_id: int
    character: int
    title: str
    description: str
    choices: List[EventChoice]


@dataclass
class EventEngine:
    catalog: List[EventDef] = field(default_factory=list)
    pending: List[EventInstance] = field(default_factory=list)
    cooldowns: Dict[Tuple[int, int], int] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.catalog:
            self.catalog = builtin_events()

    def tick_cooldowns(self) -> None:
        self.cooldowns = {k: v - 1 for k, v in self.cooldowns.items() if v > 1}

    def _eligible(self, world: World, who: int, ev: EventDef) -> bool:
        c = world.character(who)
        if not c or not c.is_alive():
            return False
        if ev.requires_ruler and not c.is_ruler:
            return False
        if ev.requires_adult and not c.is_adult(world.date):
            return False
        if c.gold < ev.min_gold:
            return False
        if ev.requires_married and not c.is_married():
            return False
        return True

    def daily_check(self, world: World, characters: List[int]) -> None:
        for who in characters:
            for ev in self.catalog:
                key = (ev.id, who)
                if key in self.cooldowns:
                    continue
                if not self._eligible(world, who, ev):
                    continue
                p = max(0.005, min(0.35, ev.weight * 0.02))
                if random.random() < p:
                    self.pending.append(
                        EventInstance(
                            event_id=ev.id,
                            character=who,
                            title=ev.title,
                            description=ev.description,
                            choices=list(ev.choices),
                        )
                    )
                    self.cooldowns[key] = ev.cooldown_days
                    if ev.major:
                        break

    def resolve_choice(self, world: World, instance: EventInstance, choice_id: int) -> None:
        choice = next((c for c in instance.choices if c.id == choice_id), None)
        if not choice:
            return
        for eff in choice.effects:
            eff.apply(world, instance.character)
        c = world.character(instance.character)
        name = c.name if c else "?"
        line = f"{name} 事件「{instance.title}」选择：{choice.text}"
        self.history.append(line)
        world.push_log(line)

    def auto_resolve_all(self, world: World) -> None:
        pending = list(self.pending)
        self.pending.clear()
        for inst in pending:
            best = max(inst.choices, key=lambda c: c.ai_weight)
            self.resolve_choice(world, inst, best.id)


def builtin_events() -> List[EventDef]:
    def choice(cid: int, text: str, effects: List[Effect], w: float = 5.0) -> EventChoice:
        return EventChoice(id=cid, text=text, effects=effects, ai_weight=w)

    return [
        EventDef(
            1,
            "丰收之年",
            "领地迎来大丰收，农民献上额外税赋。",
            3.0,
            365,
            False,
            [
                choice(0, "收下贡赋", [Effect("gold", 25), Effect("prestige", 5)], 10),
                choice(1, "减免租税以收买民心", [Effect("prestige", 15), Effect("piety", 10)], 5),
            ],
        ),
        EventDef(
            2,
            "宫廷丑闻",
            "朝中流传关于你的闲言碎语。",
            2.0,
            180,
            False,
            [
                choice(0, "置之不理", [Effect("stress", 15)], 5),
                choice(1, "严厉追查", [Effect("stress", 5), Effect("gold", -10), Effect("prestige", 5)], 8),
            ],
        ),
        EventDef(
            3,
            "狩猎意外",
            "狩猎时坐骑受惊，你险些摔伤。",
            1.5,
            400,
            True,
            [
                choice(0, "强撑着继续", [Effect("health", -0.5), Effect("prestige", 10)], 4),
                choice(1, "立即返回疗伤", [Effect("health", -0.2), Effect("stress", 5)], 10),
            ],
        ),
        EventDef(
            4,
            "虔诚的捐赠",
            "主教请求你资助修建教堂。",
            2.0,
            300,
            False,
            [
                choice(0, "慷慨解囊", [Effect("gold", -30), Effect("piety", 40), Effect("prestige", 10)], 6),
                choice(1, "婉拒", [Effect("piety", -10)], 4),
            ],
            min_gold=30,
        ),
        EventDef(
            5,
            "封臣的抱怨",
            "一位封臣公开抱怨赋税过重。",
            2.5,
            200,
            False,
            [
                choice(0, "安抚许诺", [Effect("gold", -15), Effect("stress", 5)], 7),
                choice(1, "威胁镇压", [Effect("prestige", 5), Effect("stress", 10)], 5),
            ],
        ),
        EventDef(
            6,
            "婚姻生活",
            "与配偶共度宁静的夜晚。",
            2.0,
            120,
            False,
            [
                choice(0, "享受温存", [Effect("stress", -10), Effect("prestige", 2)], 10),
                choice(1, "讨论政务", [Effect("prestige", 5)], 6),
            ],
            requires_married=True,
        ),
        EventDef(
            7,
            "流浪骑士求职",
            "一位骑士请求加入你的宫廷。",
            2.2,
            240,
            False,
            [
                choice(0, "收为家臣", [Effect("gold", -20), Effect("prestige", 8), Effect("log", text="宫廷迎来新骑士")], 8),
                choice(1, "打发走", [], 3),
            ],
            min_gold=20,
        ),
        EventDef(
            8,
            "瘟疫阴影",
            "附近村落出现疫病。",
            1.2,
            500,
            True,
            [
                choice(0, "封闭宫廷", [Effect("gold", -25), Effect("stress", 10)], 9),
                choice(1, "组织救治", [Effect("gold", -40), Effect("piety", 20), Effect("health", -0.3)], 6),
                choice(2, "置若罔闻", [Effect("health", -0.8), Effect("stress", 20)], 2),
            ],
        ),
        EventDef(
            9,
            "边境劫掠",
            "强盗侵扰边境村庄。",
            2.3,
            180,
            False,
            [
                choice(0, "派兵清剿", [Effect("gold", -15), Effect("prestige", 12)], 9),
                choice(1, "提高通行税补偿", [Effect("gold", 10), Effect("prestige", -5)], 4),
            ],
        ),
        EventDef(
            10,
            "学者来访",
            "一位学者带来稀有抄本。",
            1.8,
            320,
            False,
            [
                choice(0, "购入抄本", [Effect("gold", -25), Effect("piety", 5), Effect("trait", 8)], 7),
                choice(1, "婉言谢绝", [], 4),
            ],
            min_gold=25,
        ),
        EventDef(
            11,
            "节日庆典",
            "臣民请求举办丰年节。",
            2.0,
            200,
            False,
            [
                choice(0, "大办特办", [Effect("gold", -20), Effect("prestige", 15), Effect("stress", -8)], 8),
                choice(1, "象征性支持", [Effect("gold", -5), Effect("prestige", 5)], 6),
            ],
            min_gold=15,
        ),
        EventDef(
            12,
            "决斗挑战",
            "一位傲慢贵族要求决斗。",
            1.3,
            450,
            True,
            [
                choice(0, "亲自应战", [Effect("health", -0.4), Effect("prestige", 20), Effect("trait", 1)], 5),
                choice(1, "派骑士代战", [Effect("gold", -10), Effect("prestige", 5)], 9),
                choice(2, "息事宁人", [Effect("prestige", -10), Effect("stress", 8)], 3),
            ],
        ),
        EventDef(
            13,
            "商路开通",
            "商会提议开辟新商路。",
            1.7,
            360,
            False,
            [
                choice(0, "投资商路", [Effect("gold", -40), Effect("prestige", 8)], 7),
                choice(1, "征收路权税", [Effect("gold", 15), Effect("prestige", -3)], 5),
            ],
            min_gold=40,
        ),
        EventDef(
            14,
            "神秘访客",
            "戴兜帽的陌生人带来可疑情报。",
            1.6,
            280,
            False,
            [
                choice(0, "购买情报", [Effect("gold", -15), Effect("prestige", 5)], 7),
                choice(1, "逮捕审讯", [Effect("stress", 5), Effect("trait", 2)], 4),
                choice(2, "驱逐出城", [], 5),
            ],
        ),
        EventDef(
            15,
            "诗人献辞",
            "游吟诗人创作了赞美你的史诗。",
            1.8,
            300,
            False,
            [
                choice(0, "重金赏赐", [Effect("gold", -12), Effect("prestige", 18)], 8),
                choice(1, "口头嘉奖", [Effect("prestige", 6)], 5),
            ],
        ),
    ]
