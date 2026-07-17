from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict, List

from ck_engine.ai import AiDirector, AiPersonality
from ck_engine.core import NONE_ID
from ck_engine.events import EventEngine
from ck_engine.game.scenario import Scenario1066
from ck_engine.military import (
    ArmyStatus,
    BattleSimulator,
    SiegeManager,
    WarManager,
    WarResult,
)
from ck_engine.politics import (
    CasusBelli,
    CouncilRegistry,
    DiplomacySystem,
    FactionKind,
    FactionSystem,
    RealmLaw,
    SchemeKind,
    SchemeSystem,
)
from ck_engine.world import TitleTier, World


class GameSimulation:
    def __init__(self) -> None:
        self.world: World = Scenario1066.build()
        self.wars = WarManager()
        self.sieges = SiegeManager()
        self.events = EventEngine()
        self.factions = FactionSystem()
        self.schemes = SchemeSystem()
        self.diplomacy = DiplomacySystem()
        self.councils = CouncilRegistry()
        self.realm_laws: Dict[int, RealmLaw] = {}
        self.player_ids: set = set()
        self.bootstrap()

    def bootstrap(self) -> None:
        william = next(
            (c.id for c in self.world.alive_characters() if "威廉·征服者" in c.name),
            None,
        )
        harold = next(
            (c.id for c in self.world.alive_characters() if "哈罗德" in c.name),
            None,
        )
        if william and harold:
            self.diplomacy.set_rival(william, harold)
            eng = next(
                (t.id for t in self.world.titles.values() if "英格兰" in t.name),
                None,
            )
            if eng:
                self.diplomacy.add_claim(william, eng, strength=80)
        edwin = next((c.id for c in self.world.alive_characters() if "埃德温" in c.name), None)
        morcar = next((c.id for c in self.world.alive_characters() if "莫卡" in c.name), None)
        if edwin and morcar:
            self.diplomacy.form_alliance(edwin, morcar, self.world.date)
        for r in list(self.world.rulers()):
            self.ensure_council(r.id)
            self.realm_laws.setdefault(r.id, RealmLaw.feudal_default())

    def ensure_council(self, ruler: int) -> None:
        candidates = []
        for c in self.world.alive_characters():
            if c.id == ruler or not c.is_adult(self.world.date):
                continue
            a = self.world.effective_attrs(c.id)
            if not a:
                continue
            candidates.append(
                (c.id, a.diplomacy, a.martial, a.stewardship, a.intrigue, a.learning)
            )
        council = self.councils.get_or_create(ruler)
        if not council.members():
            council.auto_appoint(candidates)

    def run_days(self, days: int) -> None:
        for _ in range(days):
            self.tick_day()

    def tick_day(self) -> None:
        self.world.date = self.world.date.advance_one_day()
        self.world.tick += 1
        self.wars.tick_movement()
        self.resolve_encounters()
        self.tick_sieges()
        self.wars.disband_empty()
        self.events.tick_cooldowns()
        if self.world.date.is_month_start():
            self.tick_month()
        if self.world.date.is_year_start():
            self.world.push_log(f"—— {self.world.date.year} 年来临 ——")
            for line in self.diplomacy.expire_treaties(self.world.date.year, world=self.world):
                self.world.push_log(line)

    def tick_month(self) -> None:
        self.world.process_health()
        self.world.process_monthly_economy()
        self.world.process_fertility()

        for rid in [r.id for r in self.world.rulers()]:
            law = self.realm_laws.get(rid)
            if law and law.crown_authority.tax_bonus() > 0:
                income = self.world.monthly_income_of(rid) * law.crown_authority.tax_bonus()
                c = self.world.character(rid)
                if c:
                    c.add_gold(income)

        self.tick_councils()
        chars = [
            c.id
            for c in self.world.alive_characters()
            if c.is_ruler or c.is_adult(self.world.date)
        ][:50]
        self.events.daily_check(self.world, chars)
        self.events.auto_resolve_all(self.world)
        self.tick_factions()
        self.tick_schemes()
        actions = AiDirector.monthly_actions(
            self.world,
            self.wars,
            self.diplomacy,
            self.schemes,
            skip_ids=set(self.player_ids),
        )
        AiDirector.apply_actions(
            self.world, self.wars, self.diplomacy, self.schemes, actions
        )
        self.tick_wars()
        # 先结算战争疲劳增减，再对非交战者衰减
        at_war_ids = set()
        for w in self.wars.active_wars():
            at_war_ids.add(w.attacker_primary)
            at_war_ids.add(w.defender_primary)
        self.diplomacy.tick_war_exhaustion(except_ids=at_war_ids)
        self.try_start_sieges()

        # 军队维护费：破产时强制解散部分军团
        by_owner: Dict[int, List] = {}
        for army in self.wars.armies.values():
            if army.is_active():
                by_owner.setdefault(army.owner, []).append(army)
        for owner, armies in by_owner.items():
            c = self.world.character(owner)
            if not c:
                continue
            cost = sum(a.monthly_maintenance() for a in armies)
            # 维护费略抬高，避免常备军无代价
            cost *= 1.25
            if c.gold >= cost:
                c.add_gold(-cost)
                continue
            # 掏空国库并每月最多解散一支最大军团
            c.add_gold(-c.gold)
            armies.sort(key=lambda a: a.total_men(), reverse=True)
            dis = armies[0]
            dis.status = ArmyStatus.DISBANDED
            dis.stacks.clear()
            self.world.push_log(f"{c.name} 国库空虚，被迫解散 {dis.name}")

        for r in list(self.world.rulers()):
            self.ensure_council(r.id)
            self.realm_laws.setdefault(r.id, RealmLaw.feudal_default())

    def tick_councils(self) -> None:
        skill_map: Dict[int, tuple] = {}
        for c in self.world.alive_characters():
            a = self.world.effective_attrs(c.id)
            if a:
                skill_map[c.id] = (
                    a.diplomacy,
                    a.martial,
                    a.stewardship,
                    a.intrigue,
                    a.learning,
                )
        for rid in [r.id for r in self.world.rulers()]:
            council = self.councils.get_or_create(rid)
            effect = council.monthly_effect(skill_map)
            c = self.world.character(rid)
            if c:
                c.add_gold(effect.gold)
                c.add_prestige(effect.prestige)
                c.piety = max(0.0, c.piety + effect.piety)
            if effect.control_gain > 0 and c:
                for tid in list(c.held_titles):
                    t = self.world.title(tid)
                    if not t:
                        continue
                    for cid in t.counties:
                        county = self.world.map.get(cid)
                        if county:
                            county.control = min(100.0, county.control + effect.control_gain * 0.2)
            if effect.development_chance > 0 and random.random() < 0.05 and c:
                if c.held_titles:
                    t = self.world.title(c.held_titles[0])
                    if t and t.counties:
                        county = self.world.map.get(t.counties[0])
                        if county and county.development < county.terrain.development_cap():
                            county.development += 1
            if effect.claim_progress >= 20 and random.random() < 0.15 and c:
                owned = set()
                for tid in c.held_titles:
                    t = self.world.title(tid)
                    if t:
                        owned.update(t.counties)
                target = next(
                    (co for co in self.world.map.iter() if co.id not in owned),
                    None,
                )
                if target:
                    self.diplomacy.add_claim(rid, target.owner_title, target.id, 50)
                    self.world.push_log(f"{c.name} 伪造了对 {target.name} 的宣称")
            # 破坏阴谋：压低以本君主为目标的活跃阴谋进度
            if any("破坏敌对阴谋" in line for line in effect.logs):
                spy = council.spymaster
                spy_skill = skill_map.get(spy, (8, 8, 8, 8, 8))[3]
                for scheme in list(self.schemes.schemes.values()):
                    if not scheme.exposed and not scheme.is_complete() and scheme.target == rid:
                        scheme.progress = max(0.0, scheme.progress - spy_skill * 0.4)
                        scheme.secrecy = max(0.0, scheme.secrecy - spy_skill * 0.2)

    def tick_factions(self) -> None:
        vassal_pairs = []
        for t in self.world.titles.values():
            if t.holder == NONE_ID or t.de_facto_liege == NONE_ID:
                continue
            lt = self.world.title(t.de_facto_liege)
            if not lt or lt.holder == NONE_ID or lt.holder == t.holder:
                continue
            op = self.world.opinion(t.holder, lt.holder)
            law = self.realm_laws.get(lt.holder)
            if law:
                op += law.crown_authority.vassal_opinion_penalty()
            vassal_pairs.append((t.holder, lt.holder, op))

        mil: Dict[int, float] = {}
        liege_pow: Dict[int, float] = {}
        for r in self.world.rulers():
            p = float(estimate_power(self.world, r.id))
            mil[r.id] = p
            liege_pow[r.id] = p
        for v, _, _ in vassal_pairs:
            mil.setdefault(v, float(estimate_power(self.world, v)))

        self.factions.recompute_power(mil, liege_pow)
        opinions = {v: op for v, _, op in vassal_pairs}
        self.factions.tick_discontent(opinions)
        events = self.factions.monthly_ai(vassal_pairs, random.random)
        for ev in events:
            if ev.kind == "formed":
                founder = self.world.character(ev.founder)
                liege = self.world.character(ev.liege)
                fk = ev.faction_kind.name_zh() if ev.faction_kind else "派系"
                if founder and liege:
                    self.world.push_log(f"{founder.name} 针对 {liege.name} 组建了{fk}")
            elif ev.kind == "joined":
                who = self.world.character(ev.who)
                if who:
                    self.world.push_log(f"{who.name} 加入了派系")
            elif ev.kind == "ultimatum":
                liege = self.world.character(ev.liege)
                text = ev.faction_kind.ultimatum_text() if ev.faction_kind else "要求"
                if liege:
                    self.world.push_log(
                        f"派系向 {liege.name} 发出最后通牒：{text}（{len(ev.members)} 人）"
                    )
                f = self.factions.factions.get(ev.faction_id)
                if f:
                    f.discontent = min(100.0, f.discontent + 20)
            elif ev.kind == "revolt":
                liege = self.world.character(ev.liege)
                fk = ev.faction_kind.name_zh() if ev.faction_kind else "叛乱"
                if liege:
                    self.world.push_log(f"叛乱爆发！{fk} vs {liege.name}")
                if ev.members:
                    leader = ev.members[0]
                    cb = (
                        CasusBelli.DEPOSE_LIEGE
                        if ev.faction_kind
                        in (FactionKind.CLAIMANT, FactionKind.POPULAR)
                        else CasusBelli.INDEPENDENCE
                    )
                    if self.diplomacy.can_declare_war(leader, ev.liege, self.world.date.year):
                        self.wars.declare_war(
                            cb, leader, ev.liege, self.world.date, f"{fk}叛乱"
                        )
                        self.diplomacy.set_at_war(leader, ev.liege, True)
                self.factions.dissolve(ev.faction_id)
            elif ev.kind == "dissolved":
                self.world.push_log(f"派系解散：{ev.reason}")

    def tick_schemes(self) -> None:
        intrigue = {}
        for c in self.world.alive_characters():
            a = self.world.effective_attrs(c.id)
            if a:
                intrigue[c.id] = a.intrigue
        for council in self.councils.by_ruler.values():
            if council.spymaster != NONE_ID:
                intrigue[council.ruler] = intrigue.get(council.ruler, 8) + 2
        outcomes = self.schemes.monthly_tick(intrigue, random.random)
        for o in outcomes:
            if o.kind == "success" and o.scheme_kind:
                owner = self.world.character(o.owner)
                target = self.world.character(o.target)
                on = owner.name if owner else "?"
                tn = target.name if target else "?"
                kind = o.scheme_kind
                if kind == SchemeKind.MURDER:
                    self.world.push_log(f"阴谋成功：{on} 暗杀了 {tn}！")
                    self.world.on_death(o.target)
                    if owner:
                        owner.add_stress(20)
                        owner.add_prestige(-15)
                elif kind == SchemeKind.SWAY:
                    self.world.modify_opinion(o.target, o.owner, 25)
                    self.world.push_log(f"{on} 成功拉拢了 {tn}")
                elif kind == SchemeKind.FABRICATE_HOOK:
                    self.world.modify_opinion(o.target, o.owner, -10)
                    self.world.push_log(f"{on} 掌握了 {tn} 的把柄")
                    if owner:
                        owner.add_prestige(10)
                elif kind == SchemeKind.ABDUCT:
                    self.world.push_log(f"{on} 绑架了 {tn}")
                    if target:
                        target.add_stress(30)
                elif kind == SchemeKind.SEDUCE:
                    self.world.modify_opinion(o.target, o.owner, 30)
                    self.world.push_log(f"{on} 与 {tn} 产生私情")
                elif kind == SchemeKind.CLAIM_FABRICATION:
                    self.world.push_log(f"{on} 完成对 {tn} 相关宣称的伪造")
            elif o.kind == "exposed":
                owner = self.world.character(o.owner)
                target = self.world.character(o.target)
                on = owner.name if owner else "?"
                tn = target.name if target else "?"
                self.world.push_log(f"阴谋败露！{on} 对 {tn} 的密谋被发现")
                self.world.modify_opinion(o.target, o.owner, -40)
                if owner:
                    owner.add_prestige(-25)
                    owner.add_stress(15)

    def resolve_encounters(self) -> None:
        # 按位置分组军队，O(n)
        by_loc: Dict[int, List[tuple]] = defaultdict(list)
        for a in self.wars.armies.values():
            if a.is_active():
                by_loc[a.location].append((a.id, a.owner, a.total_men()))

        for loc, loc_armies in by_loc.items():
            if len(loc_armies) < 2:
                continue
            # 按所有者分组：owner -> [(army_id, men), ...]
            by_owner: Dict[int, List[tuple]] = defaultdict(list)
            for aid, owner, men in loc_armies:
                by_owner[owner].append((aid, men))

            owners = list(by_owner.keys())
            for i in range(len(owners)):
                for j in range(i + 1, len(owners)):
                    oa, ob = owners[i], owners[j]
                    enemies = any(
                        (w.is_attacker(oa) and not w.is_attacker(ob) and w.involves(ob))
                        or (w.is_attacker(ob) and not w.is_attacker(oa) and w.involves(oa))
                        for w in self.wars.active_wars()
                    )
                    if not enemies:
                        continue
                    # 每对阵营只打最大规模的一对军队
                    a_id = max(by_owner[oa], key=lambda row: row[1])[0]
                    b_id = max(by_owner[ob], key=lambda row: row[1])[0]
                    army_a = self.wars.armies.get(a_id)
                    army_b = self.wars.armies.get(b_id)
                    if not army_a or not army_b:
                        continue
                    self._resolve_battle_pair(army_a, army_b)

    def _resolve_battle_pair(self, army_a, army_b) -> None:
        atk_m = (self.world.effective_attrs(army_a.commander) or type("A", (), {"martial": 8})()).martial
        def_m = (self.world.effective_attrs(army_b.commander) or type("A", (), {"martial": 8})()).martial
        county = self.world.map.get(army_a.location)
        width = county.terrain.combat_width() if county else 1.0
        result = BattleSimulator.resolve(army_a, army_b, atk_m, def_m, width)
        an = self.world.character(army_a.owner)
        bn = self.world.character(army_b.owner)
        self.world.push_log(
            f"战斗！{(an.name if an else '?')} vs {(bn.name if bn else '?')} — {result.description}"
        )
        for w in list(self.wars.active_wars()):
            if w.involves(army_a.owner) and w.involves(army_b.owner):
                if w.is_attacker(army_a.owner):
                    w.apply_warscore(result.warscore_change)
                else:
                    w.apply_warscore(-result.warscore_change)
        loser = army_b if result.attacker_won else army_a
        self._retreat_army(loser)

    def _retreat_army(self, army) -> None:
        """败军撤退：优先友方领地，其次中立，避开敌方。"""
        county = self.world.map.get(army.location)
        if not county or not county.neighbors:
            army.status = ArmyStatus.RETREATING
            return
        enemy_holders = set()
        for w in self.wars.active_wars():
            if not w.involves(army.owner):
                continue
            for p in w.participants:
                if w.is_attacker(p.character) != w.is_attacker(army.owner):
                    enemy_holders.add(p.character)
        friendly: List[int] = []
        neutral: List[int] = []
        hostile: List[int] = []
        for nid in county.neighbors:
            n = self.world.map.get(nid)
            if not n:
                continue
            if n.holder == army.owner:
                friendly.append(nid)
            elif n.holder in enemy_holders:
                hostile.append(nid)
            else:
                neutral.append(nid)
        dest = (friendly or neutral or hostile or list(county.neighbors))[0]
        army.location = dest
        army.path.clear()
        army.status = ArmyStatus.RETREATING

    def try_start_sieges(self) -> None:
        snapshots = [
            (a.id, a.owner, a.location)
            for a in self.wars.armies.values()
            if a.is_active() and a.status == ArmyStatus.IDLE
        ]
        for aid, owner, loc in snapshots:
            county = self.world.map.get(loc)
            if not county or county.holder in (NONE_ID, owner):
                continue
            enemies = any(
                w.involves(owner)
                and w.involves(county.holder)
                and w.is_attacker(owner) != w.is_attacker(county.holder)
                for w in self.wars.active_wars()
            )
            if not enemies or self.sieges.active_at(loc):
                continue
            sid = self.sieges.start(
                loc,
                aid,
                owner,
                county.holder,
                county.fort_level,
                max(50, county.levies // 4),
                self.world.date,
            )
            army = self.wars.army(aid)
            if army:
                army.status = ArmyStatus.SIEGING
            o = self.world.character(owner)
            self.world.push_log(
                f"{(o.name if o else '?')} 开始围攻 {county.name} (围城 #{sid})"
            )

    def tick_sieges(self) -> None:
        men, martial, locs = {}, {}, {}
        for a in self.wars.armies.values():
            men[a.id] = a.total_men()
            locs[a.id] = a.location
            attrs = self.world.effective_attrs(a.commander)
            martial[a.id] = attrs.martial if attrs else 8
        for ev in self.sieges.tick_day(men, martial, locs):
            if ev.kind == "captured":
                county = self.world.map.get(ev.county)
                attacker = self.world.character(ev.attacker)
                cn = county.name if county else "?"
                an = attacker.name if attacker else "?"
                self.world.push_log(f"{an} 攻陷了 {cn}！")
                self.world.occupy_county(ev.county, ev.attacker)
                for w in list(self.wars.active_wars()):
                    if w.involves(ev.attacker) and w.involves(ev.defender):
                        if w.is_attacker(ev.attacker):
                            w.apply_warscore(25)
                        else:
                            w.apply_warscore(-25)
                s = self.sieges.sieges.get(ev.siege_id)
                if s:
                    army = self.wars.army(s.attacker_army)
                    if army and army.status == ArmyStatus.SIEGING:
                        army.status = ArmyStatus.IDLE
                if attacker:
                    attacker.add_prestige(10)
                    attacker.add_gold(5)
            elif ev.kind == "lifted":
                county = self.world.map.get(ev.county)
                cn = county.name if county else "?"
                self.world.push_log(f"围攻 {cn} 解除：{ev.reason}")
                s = self.sieges.sieges.get(ev.siege_id)
                if s:
                    army = self.wars.army(s.attacker_army)
                    if army and army.status == ArmyStatus.SIEGING:
                        army.status = ArmyStatus.IDLE

    def tick_wars(self) -> None:
        for wid in [w.id for w in self.wars.active_wars()]:
            w = self.wars.war(wid)
            if not w:
                continue
            self.diplomacy.add_war_exhaustion(w.attacker_primary, 1.0)
            self.diplomacy.add_war_exhaustion(w.defender_primary, 0.8)
            if w.warscore > 0:
                w.apply_warscore(-1)
            elif w.warscore < 0:
                w.apply_warscore(1)
            if w.can_enforce() or w.warscore >= 100:
                self.wars.end_war(wid, WarResult.ATTACKER_VICTORY)
                self.diplomacy.set_at_war(w.attacker_primary, w.defender_primary, False)
                self.diplomacy.set_truce(
                    w.attacker_primary, w.defender_primary, self.world.date.year + 5
                )
                an = self.world.character(w.attacker_primary)
                dn = self.world.character(w.defender_primary)
                self.world.push_log(
                    f"战争结束：{(an.name if an else '?')} 战胜 {(dn.name if dn else '?')}，强制执行和约"
                )
                if an:
                    an.add_prestige(w.cb.attacker_prestige_on_win())
                    an.add_gold(30)
                if dn:
                    dn.add_prestige(-30)
                    dn.add_gold(-20)
                if w.cb in (
                    CasusBelli.CONQUEST,
                    CasusBelli.CLAIM,
                    CasusBelli.DE_JURE,
                ):
                    self.transfer_one_county(w.defender_primary, w.attacker_primary)
            elif w.can_surrender() or w.warscore <= -100:
                self.wars.end_war(wid, WarResult.DEFENDER_VICTORY)
                self.diplomacy.set_at_war(w.attacker_primary, w.defender_primary, False)
                self.diplomacy.set_truce(
                    w.attacker_primary, w.defender_primary, self.world.date.year + 5
                )
                an = self.world.character(w.attacker_primary)
                dn = self.world.character(w.defender_primary)
                self.world.push_log(
                    f"战争结束：{(dn.name if dn else '?')} 击退 {(an.name if an else '?')}"
                )
                if dn:
                    dn.add_prestige(40)
                if an:
                    an.add_prestige(-20)
            else:
                atk_exh = self.diplomacy.war_exhaustion.get(w.attacker_primary, 0.0)
                def_exh = self.diplomacy.war_exhaustion.get(w.defender_primary, 0.0)
                if w.can_white_peace(self.world.date, atk_exh, def_exh):
                    self.wars.end_war(wid, WarResult.WHITE_PEACE)
                    self.diplomacy.set_at_war(w.attacker_primary, w.defender_primary, False)
                    self.diplomacy.set_truce(
                        w.attacker_primary, w.defender_primary, self.world.date.year + 3
                    )
                    an = self.world.character(w.attacker_primary)
                    dn = self.world.character(w.defender_primary)
                    self.world.push_log(
                        f"白和：{(an.name if an else '?')} 与 {(dn.name if dn else '?')} 停战"
                    )
                    if an:
                        an.add_prestige(-5)
                    if dn:
                        dn.add_prestige(5)

    def transfer_one_county(self, frm: int, to: int) -> None:
        loser = self.world.character(frm)
        if not loser:
            return
        for tid in list(loser.held_titles):
            t = self.world.title(tid)
            if t and t.tier == TitleTier.COUNTY and t.counties:
                # 走占领路径，确保 holder + 封臣链同步
                for cid in list(t.counties):
                    self.world.occupy_county(cid, to)
                self.world.push_log(f"和约割让：{t.name}")
                return

    def print_status(self) -> None:
        print(f"日期: {self.world.date}")
        print(
            f"人物: {sum(1 for _ in self.world.alive_characters())} 存活 / "
            f"{len(self.world.characters)} 总计"
        )
        print(f"统治者: {sum(1 for _ in self.world.rulers())}")
        print(f"伯爵领: {len(self.world.map.counties)}")
        print(f"进行中战争: {sum(1 for _ in self.wars.active_wars())}")
        print(f"进行中围城: {sum(1 for _ in self.sieges.active_sieges())}")
        print(f"活跃派系: {len(self.factions.factions)}")
        print(f"进行中阴谋: {len(self.schemes.schemes)}")
        print()
        print("—— 主要统治者 ——")
        for r in self.world.rulers():
            attrs = self.world.effective_attrs(r.id)
            title = self.world.title(r.primary_title)
            tname = title.name if title else "无"
            income = self.world.monthly_income_of(r.id)
            men = self.wars.total_men_of(r.id)
            martial = attrs.martial if attrs else 0
            profile = AiPersonality.profile_of(self.world, r.id)
            persona = AiPersonality.describe(profile)
            print(
                f"  {r.name} | {tname} | 金:{r.gold:.0f} 威望:{r.prestige:.0f} | "
                f"军略:{martial} | 月入:{income:.1f} | 野战军:{men} | [{persona}]"
            )

    def print_recent_log(self, n: int = 40) -> None:
        print("\n—— 最近日志 ——")
        for line in self.world.log[-n:]:
            print(f"  {line}")

    def print_wars(self) -> None:
        print("\n—— 战争 ——")
        if not self.wars.wars:
            print("  （无）")
            return
        for w in self.wars.wars.values():
            status = "进行中" if w.active else "已结束"
            an = self.world.character(w.attacker_primary)
            dn = self.world.character(w.defender_primary)
            print(
                f"  [{status}] {w.name} | "
                f"{(an.name if an else '?')} vs {(dn.name if dn else '?')} | "
                f"分数:{w.warscore} | {w.cb.name_zh()}"
            )

    def print_politics(self) -> None:
        print("\n—— 派系 ——")
        if not self.factions.factions:
            print("  （无）")
        for f in self.factions.factions.values():
            liege = self.world.character(f.target_liege)
            print(
                f"  {f.kind.name_zh()} → {(liege.name if liege else '?')} | "
                f"成员:{len(f.members)} 力量:{f.power:.0f} 不满:{f.discontent:.0f}"
            )
        print("\n—— 条约 ——")
        if not self.diplomacy.treaties:
            print("  （无）")
        for t in self.diplomacy.treaties:
            a = self.world.character(t.a)
            b = self.world.character(t.b)
            print(
                f"  {t.kind.name_zh()} | {(a.name if a else '?')} — "
                f"{(b.name if b else '?')} | 至 {t.expires_year}"
            )
        print("\n—— 阴谋 ——")
        if not self.schemes.schemes:
            print("  （无）")
        for s in self.schemes.schemes.values():
            o = self.world.character(s.owner)
            t = self.world.character(s.target)
            print(
                f"  {s.kind.name_zh()} | {(o.name if o else '?')} → "
                f"{(t.name if t else '?')} | 进度:{s.progress:.0f}% 隐秘:{s.secrecy:.0f}"
            )

    def print_dynasties(self) -> None:
        print("\n—— 王朝 ——")
        for d in self.world.dynasties.values():
            alive = sum(
                1
                for m in d.members
                if self.world.character(m) and self.world.character(m).is_alive()
            )
            head = self.world.character(d.head)
            print(
                f"  {d.name} | 族长:{(head.name if head else '无')} | "
                f"成员:{len(d.members)} (存活{alive}) | 格言:{d.motto}"
            )


def estimate_power(world: World, who: int) -> int:
    c = world.character(who)
    if not c:
        return 50
    total = 0
    for tid in c.held_titles:
        t = world.title(tid)
        if not t:
            continue
        for cid in t.counties:
            county = world.map.get(cid)
            if county:
                total += county.monthly_levies()
    return max(50, total)
