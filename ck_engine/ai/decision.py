from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from ck_engine.ai.personality import AiPersonality
from ck_engine.core import NONE_ID
from ck_engine.military.army import ArmyStatus, UnitType
from ck_engine.military.war import WarManager
from ck_engine.politics.diplomacy import CasusBelli, DiplomacySystem
from ck_engine.politics.schemes import SchemeKind, SchemeSystem
from ck_engine.world.character import Gender
from ck_engine.world.world_state import World


@dataclass
class AiAction:
    kind: str
    owner: int = 0
    target: int = 0
    location: int = 0
    army_id: int = 0
    destination: int = 0
    levies: int = 0
    amount: float = 0.0
    cb: Optional[CasusBelli] = None
    scheme_kind: Optional[SchemeKind] = None


class AiDirector:
    @staticmethod
    def monthly_actions(
        world: World,
        wars: WarManager,
        diplomacy: DiplomacySystem,
        schemes: SchemeSystem,
        skip_ids: set = None,
    ) -> List[AiAction]:
        skip_ids = skip_ids or set()
        actions: List[AiAction] = []
        rulers = [c.id for c in world.rulers()]
        for ruler in rulers:
            if ruler in skip_ids:
                continue
            profile = AiPersonality.profile_of(world, ruler)
            at_war = any(w.involves(ruler) for w in wars.active_wars())
            c = world.character(ruler)
            if not c:
                continue

            # 婚姻
            if not c.is_married() and c.is_adult(world.date) and random.random() < 0.35:
                spouse = find_spouse_candidate(world, ruler)
                if spouse:
                    actions.append(AiAction(kind="marry", owner=ruler, target=spouse))
            for child_id in c.children:
                ch = world.character(child_id)
                if (
                    ch
                    and ch.is_alive()
                    and ch.is_adult(world.date)
                    and not ch.is_married()
                    and random.random() < 0.2
                ):
                    spouse = find_spouse_candidate(world, child_id)
                    if spouse:
                        actions.append(AiAction(kind="marry", owner=child_id, target=spouse))

            # 战争调度
            if at_war:
                enemy = None
                for w in wars.active_wars():
                    if w.involves(ruler):
                        enemy = (
                            w.defender_primary
                            if w.is_attacker(ruler)
                            else w.attacker_primary
                        )
                        break
                if enemy is not None:
                    if not wars.armies_of(ruler):
                        loc = capital_of(world, ruler)
                        if loc:
                            actions.append(
                                AiAction(
                                    kind="raise_army",
                                    owner=ruler,
                                    location=loc,
                                    levies=estimate_levies(world, ruler),
                                )
                            )
                    else:
                        target_loc = capital_of(world, enemy)
                        if target_loc:
                            for aid in wars.armies_of(ruler):
                                army = wars.army(aid)
                                if (
                                    army
                                    and army.status == ArmyStatus.IDLE
                                    and army.location != target_loc
                                ):
                                    actions.append(
                                        AiAction(
                                            kind="move_army",
                                            owner=ruler,
                                            army_id=aid,
                                            destination=target_loc,
                                        )
                                    )

            # 宣战（不对 skip 玩家乱宣也可，但允许；同盟/停战由 diplomacy 拦截）
            if (
                not at_war
                and profile.aggression > 0.55
                and random.random() < profile.aggression * 0.12
            ):
                target = find_war_target(world, wars, diplomacy, ruler, skip_ids=skip_ids)
                if target and target not in skip_ids:
                    cb = (
                        CasusBelli.RIVALRY
                        if diplomacy.flags(ruler, target).rival
                        else (
                            CasusBelli.CLAIM
                            if diplomacy.claims_of(ruler)
                            else CasusBelli.CONQUEST
                        )
                    )
                    actions.append(
                        AiAction(kind="declare_war", owner=ruler, target=target, cb=cb)
                    )
                    loc = capital_of(world, ruler)
                    if loc:
                        actions.append(
                            AiAction(
                                kind="raise_army",
                                owner=ruler,
                                location=loc,
                                levies=estimate_levies(world, ruler),
                            )
                        )

            # 同盟
            if profile.honor > 0.55 and random.random() < 0.08:
                ally = find_ally_candidate(world, diplomacy, ruler)
                if ally:
                    actions.append(AiAction(kind="form_alliance", owner=ruler, target=ally))

            # 送礼
            if profile.compassion > 0.55 and random.random() < 0.1 and c.gold >= 30:
                others = [r for r in rulers if r != ruler]
                if others:
                    actions.append(
                        AiAction(
                            kind="send_gift",
                            owner=ruler,
                            target=random.choice(others),
                            amount=15.0,
                        )
                    )

            # 阴谋
            if profile.honor < 0.45 and random.random() < 0.12:
                already = any(s.owner == ruler for s in schemes.schemes.values())
                if not already:
                    target = find_scheme_target(world, ruler)
                    if target:
                        kind = (
                            SchemeKind.MURDER
                            if profile.aggression > 0.6
                            else (
                                SchemeKind.SWAY
                                if random.random() < 0.5
                                else SchemeKind.FABRICATE_HOOK
                            )
                        )
                        actions.append(
                            AiAction(
                                kind="start_scheme",
                                owner=ruler,
                                target=target,
                                scheme_kind=kind,
                            )
                        )

            if random.random() < 0.1 and c.gold >= 20:
                actions.append(AiAction(kind="hold_feast", owner=ruler))

            if profile.compassion > 0.45 and random.random() < 0.15:
                others = [r for r in rulers if r != ruler]
                if others:
                    actions.append(
                        AiAction(
                            kind="improve_relations",
                            owner=ruler,
                            target=random.choice(others),
                        )
                    )

            if profile.greed > 0.5 and random.random() < 0.1:
                actions.append(AiAction(kind="develop", owner=ruler))

            if at_war and random.random() < 0.15 and c.gold >= 25:
                for aid in wars.armies_of(ruler):
                    actions.append(
                        AiAction(kind="recruit_knights", owner=ruler, army_id=aid)
                    )
        return actions

    @staticmethod
    def apply_actions(
        world: World,
        wars: WarManager,
        diplomacy: DiplomacySystem,
        schemes: SchemeSystem,
        actions: List[AiAction],
    ) -> None:
        for act in actions:
            if act.kind == "raise_army":
                if not wars.armies_of(act.owner):
                    aid = wars.raise_army(act.owner, act.location, act.levies)
                    army = wars.army(aid)
                    if army:
                        army.add_men(UnitType.HEAVY_INFANTRY, act.levies // 10)
                        army.add_men(UnitType.ARCHERS, act.levies // 12)
                        army.add_men(UnitType.LIGHT_CAVALRY, act.levies // 20)
                    c = world.character(act.owner)
                    if c:
                        world.push_log(f"{c.name} 征召了 {act.levies} 人 (军团 {aid})")
            elif act.kind == "move_army":
                army = wars.army(act.army_id)
                if not army:
                    continue
                path = world.map.path(army.location, act.destination)
                if path:
                    army.set_path(path)
                    dest = world.map.get(act.destination)
                    dname = dest.name if dest else "?"
                    world.push_log(f"{army.name} 向 {dname} 进军")
            elif act.kind == "declare_war":
                if not act.cb:
                    continue
                if not diplomacy.can_declare_war(act.owner, act.target, world.date.year):
                    continue
                if diplomacy.are_allied(act.owner, act.target):
                    continue
                if any(
                    w.involves(act.owner) or w.involves(act.target)
                    for w in wars.active_wars()
                ):
                    continue
                attacker = world.character(act.owner)
                if not attacker or attacker.prestige < act.cb.prestige_cost():
                    continue
                attacker.add_prestige(-act.cb.prestige_cost())
                an = attacker.name
                dn = world.character(act.target).name if world.character(act.target) else "?"
                wid = wars.declare_war(
                    act.cb,
                    act.owner,
                    act.target,
                    world.date,
                    f"{an} 对 {dn} 的{act.cb.name_zh()}",
                )
                diplomacy.set_at_war(act.owner, act.target, True)
                diplomacy.add_war_exhaustion(act.owner)
                diplomacy.add_war_exhaustion(act.target)
                # 同盟自动参战（攻方盟友加入进攻）
                war = wars.war(wid)
                if war:
                    for ally in diplomacy.allies_of(act.owner):
                        if ally != act.target and not war.involves(ally):
                            from ck_engine.military.war import WarParticipant

                            war.participants.append(
                                WarParticipant(
                                    character=ally,
                                    is_attacker=True,
                                    joined=world.date,
                                )
                            )
                            diplomacy.set_at_war(ally, act.target, True)
                world.push_log(f"宣战！{act.cb.name_zh()} (战争 {wid})")
            elif act.kind == "marry":
                if world.marry(act.owner, act.target):
                    diplomacy.flags_mut(act.owner, act.target).marriage_pact = True
            elif act.kind == "improve_relations":
                world.modify_opinion(act.owner, act.target, 10)
                world.modify_opinion(act.target, act.owner, 5)
            elif act.kind == "form_alliance":
                if diplomacy.flags(act.owner, act.target).allied:
                    continue
                diplomacy.form_alliance(act.owner, act.target, world.date)
                world.modify_opinion(act.owner, act.target, 20)
                world.modify_opinion(act.target, act.owner, 20)
                a = world.character(act.owner)
                b = world.character(act.target)
                if a and b:
                    world.push_log(f"{a.name} 与 {b.name} 结成同盟")
            elif act.kind == "send_gift":
                c = world.character(act.owner)
                if c and c.gold >= act.amount:
                    c.add_gold(-act.amount)
                    gain = DiplomacySystem.gift_opinion_gain(act.amount)
                    world.modify_opinion(act.target, act.owner, gain)
                    t = world.character(act.target)
                    if t:
                        world.push_log(f"{c.name} 向 {t.name} 赠礼 {act.amount:.0f} 金")
            elif act.kind == "start_scheme" and act.scheme_kind:
                sid = schemes.start(act.scheme_kind, act.owner, act.target, world.date)
                o = world.character(act.owner)
                t = world.character(act.target)
                if o and t:
                    world.push_log(
                        f"{o.name} 对 {t.name} 启动阴谋「{act.scheme_kind.name_zh()}」(#{sid})"
                    )
            elif act.kind == "hold_feast":
                c = world.character(act.owner)
                if c and c.gold >= 20:
                    c.add_gold(-20)
                    c.add_prestige(15)
                    c.add_stress(-10)
                    world.push_log(f"{c.name} 举办了宴会")
            elif act.kind == "develop":
                c = world.character(act.owner)
                if c and c.gold >= 10:
                    c.add_gold(-10)
                    c.add_prestige(5)
                cap = capital_of(world, act.owner)
                if cap:
                    county = world.map.get(cap)
                    if county and county.development < county.terrain.development_cap():
                        county.development += 1
                        world.push_log(f"领地 {county.name} 发展度提升")
            elif act.kind == "recruit_knights":
                c = world.character(act.owner)
                army = wars.army(act.army_id)
                if c and army and c.gold >= 25:
                    c.add_gold(-25)
                    army.add_men(UnitType.HEAVY_CAVALRY, 40)
                    army.add_men(UnitType.HEAVY_INFANTRY, 80)
                    world.push_log(f"{c.name} 为军团补充了精锐")


def find_spouse_candidate(world: World, who: int) -> Optional[int]:
    c = world.character(who)
    if not c:
        return None
    need = Gender.FEMALE if c.gender == Gender.MALE else Gender.MALE
    candidates = []
    for o in world.alive_characters():
        if (
            o.id != who
            and o.gender == need
            and not o.is_married()
            and o.is_adult(world.date)
            and o.age_at(world.date) < 40
            and o.dynasty != c.dynasty
        ):
            attrs = world.effective_attrs(o.id)
            score = attrs.total() if attrs else 0
            candidates.append((score, o.id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def find_war_target(
    world: World, wars: WarManager, diplomacy: DiplomacySystem, who: int, skip_ids: set = None,
) -> Optional[int]:
    skip_ids = skip_ids or set()
    my_power = estimate_levies(world, who) + wars.total_men_of(who)
    best = None
    best_p = 10**9
    for r in world.rulers():
        if r.id == who or r.id in skip_ids:
            continue
        if not diplomacy.can_declare_war(who, r.id, world.date.year):
            continue
        if diplomacy.are_allied(who, r.id):
            continue
        if any(w.involves(r.id) for w in wars.active_wars()):
            continue
        their = estimate_levies(world, r.id)
        if my_power > their * 0.85 and their < best_p:
            best_p = their
            best = r.id
    return best


def find_ally_candidate(
    world: World, diplomacy: DiplomacySystem, who: int
) -> Optional[int]:
    best = None
    best_op = -999
    for r in world.rulers():
        if r.id == who:
            continue
        f = diplomacy.flags(who, r.id)
        if f.allied or f.at_war:
            continue
        op = world.opinion(who, r.id)
        if op >= 0 and op > best_op:
            best_op = op
            best = r.id
    return best


def find_scheme_target(world: World, who: int) -> Optional[int]:
    best = None
    best_op = 999
    for c in world.alive_characters():
        if c.id == who or not c.is_adult(world.date):
            continue
        if not (c.is_ruler or c.gold > 80):
            continue
        op = world.opinion(who, c.id)
        if op < best_op:
            best_op = op
            best = c.id
    return best


def capital_of(world: World, who: int) -> Optional[int]:
    c = world.character(who)
    if not c:
        return None
    t = world.title(c.primary_title)
    if not t:
        return None
    if t.capital != NONE_ID:
        return t.capital
    return t.counties[0] if t.counties else None


def estimate_levies(world: World, who: int) -> int:
    c = world.character(who)
    if not c:
        return 0
    total = 0
    for tid in c.held_titles:
        t = world.title(tid)
        if not t:
            continue
        for cid in t.counties:
            county = world.map.get(cid)
            if county:
                total += county.monthly_levies()
    return max(100, total)
