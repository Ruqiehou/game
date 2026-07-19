from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional, Tuple

from ck_engine.core import NONE_ID, AttributeSet, GameDate, builtin_traits
from ck_engine.world.character import Character, Gender, LifeState
from ck_engine.world.dynasty import Dynasty
from ck_engine.world.map import County, MapGraph, Terrain
from ck_engine.world.title import Title, TitleTier


class World:
    def __init__(self, date: Optional[GameDate] = None) -> None:
        self.date = date or GameDate(1066, 10, 14)
        self.tick = 0
        self.characters: Dict[int, Character] = {}
        self.dynasties: Dict[int, Dynasty] = {}
        self.titles: Dict[int, Title] = {}
        self.map = MapGraph()
        self.traits = builtin_traits()
        self.log: List[str] = []
        self.next_char = 1
        self.next_dynasty = 1
        self.next_title = 1
        self.next_county = 1

    def push_log(self, msg: str) -> None:
        line = f"[{self.date}] {msg}"
        self.log.append(line)
        if len(self.log) > 500:
            del self.log[:100]

    # ---------- 创建 ----------
    def create_dynasty(self, name: str) -> int:
        did = self.next_dynasty
        self.next_dynasty += 1
        self.dynasties[did] = Dynasty.new(did, name)
        return did

    def create_character(
        self,
        name: str,
        dynasty: int,
        gender: Gender,
        birth: GameDate,
    ) -> int:
        cid = self.next_char
        self.next_char += 1
        c = Character(id=cid, name=name, dynasty=dynasty, gender=gender, birth=birth)
        c.base_attrs = AttributeSet(
            diplomacy=random.randint(4, 13),
            martial=random.randint(4, 13),
            stewardship=random.randint(4, 13),
            intrigue=random.randint(4, 13),
            learning=random.randint(4, 13),
            prowess=random.randint(4, 13),
        )
        if self.traits:
            for _ in range(random.randint(1, 2)):
                t = random.choice(self.traits).id
                if t not in c.traits:
                    c.traits.append(t)
        d = self.dynasties.get(dynasty)
        if d:
            d.add_member(cid)
            if d.head == NONE_ID:
                d.head = cid
                d.founder = cid
        self.characters[cid] = c
        return cid

    def create_title(self, name: str, tier: TitleTier) -> int:
        tid = self.next_title
        self.next_title += 1
        self.titles[tid] = Title.new(tid, name, tier)
        return tid

    def create_county(self, name: str, terrain: Terrain) -> int:
        cid = self.next_county
        self.next_county += 1
        self.map.insert(County.new(cid, name, terrain))
        return cid

    # ---------- 查询 ----------
    def character(self, cid: int) -> Optional[Character]:
        return self.characters.get(cid)

    def title(self, tid: int) -> Optional[Title]:
        return self.titles.get(tid)

    def alive_characters(self) -> Iterable[Character]:
        return (c for c in self.characters.values() if c.is_alive())

    def rulers(self) -> Iterable[Character]:
        return (c for c in self.characters.values() if c.is_alive() and c.is_ruler)

    def trait_bonus(self, trait_ids: List[int]) -> AttributeSet:
        total = AttributeSet.zero()
        by_id = {t.id: t for t in self.traits}
        for tid in trait_ids:
            t = by_id.get(tid)
            if t:
                total = total.add(t.attr_bonus)
        return total

    def effective_attrs(self, cid: int) -> Optional[AttributeSet]:
        c = self.character(cid)
        if not c:
            return None
        return c.effective_attrs(self.trait_bonus(c.traits))

    # ---------- 关系与封建 ----------
    def set_parents(self, child: int, father: int, mother: int) -> None:
        c = self.character(child)
        if not c:
            return
        c.father = father
        c.mother = mother
        for parent in (father, mother):
            p = self.character(parent)
            if p and child not in p.children:
                p.children.append(child)

    def marry(self, a: int, b: int) -> bool:
        ca, cb = self.character(a), self.character(b)
        if not ca or not cb or not ca.is_alive() or not cb.is_alive():
            return False
        if ca.gender == cb.gender:
            return False
        if b not in ca.spouses:
            ca.spouses.append(b)
        if a not in cb.spouses:
            cb.spouses.append(a)
        self.push_log(f"{ca.name} 与 {cb.name} 成婚")
        return True

    def grant_title(self, title_id: int, holder: int) -> bool:
        t = self.title(title_id)
        h = self.character(holder)
        if not t or not h:
            return False
        old = t.holder
        if old != NONE_ID and old != holder:
            old_c = self.character(old)
            if old_c:
                if title_id in old_c.held_titles:
                    old_c.held_titles.remove(title_id)
                if old_c.primary_title == title_id:
                    old_c.primary_title = old_c.held_titles[0] if old_c.held_titles else NONE_ID
                    old_c.is_ruler = old_c.primary_title != NONE_ID
        t.set_holder(holder)
        if title_id not in h.held_titles:
            h.held_titles.append(title_id)
        h.is_ruler = True
        should_upgrade = h.primary_title == NONE_ID
        if not should_upgrade:
            cur = self.title(h.primary_title)
            should_upgrade = cur is None or t.tier > cur.tier
        if should_upgrade:
            h.primary_title = title_id
        for cid in t.counties:
            county = self.map.get(cid)
            if county:
                county.holder = holder
                county.owner_title = title_id
        self.push_log(f"{h.name} 获得头衔「{t.name}」")
        return True

    def set_vassal(self, vassal_title: int, liege_title: int) -> bool:
        v = self.title(vassal_title)
        l = self.title(liege_title)
        if not v or not l:
            return False
        if v.de_facto_liege != NONE_ID and v.de_facto_liege != liege_title:
            old_liege = self.title(v.de_facto_liege)
            if old_liege and vassal_title in old_liege.de_facto_vassals:
                old_liege.de_facto_vassals.remove(vassal_title)
        v.de_facto_liege = liege_title
        if vassal_title not in l.de_facto_vassals:
            l.de_facto_vassals.append(vassal_title)
        return True

    def clear_vassal_link(self, title_id: int) -> None:
        t = self.title(title_id)
        if not t:
            return
        if t.de_facto_liege != NONE_ID:
            old_liege = self.title(t.de_facto_liege)
            if old_liege and title_id in old_liege.de_facto_vassals:
                old_liege.de_facto_vassals.remove(title_id)
        t.de_facto_liege = NONE_ID

    def attach_county_to_title(self, county_id: int, title_id: int) -> bool:
        t = self.title(title_id)
        c = self.map.get(county_id)
        if not t or not c:
            return False
        if county_id not in t.counties:
            t.counties.append(county_id)
        if t.capital == NONE_ID:
            t.capital = county_id
        c.owner_title = title_id
        c.holder = t.holder
        return True

    def opinion(self, frm: int, to: int) -> int:
        if frm == to:
            return 100
        a, b = self.character(frm), self.character(to)
        if not a or not b:
            return 0
        op = 0
        if a.dynasty != NONE_ID and a.dynasty == b.dynasty:
            op += 15
        op += 10 if a.culture == b.culture else -5
        op += 10 if a.faith == b.faith else -20
        if a.father == to or a.mother == to or b.father == frm or b.mother == frm:
            op += 30
        if to in a.spouses:
            op += 25
        if to in a.children or frm in b.children:
            op += 20
        by_id = {t.id: t for t in self.traits}
        for tid in a.traits:
            t = by_id.get(tid)
            if t:
                op += t.opinion_self
        for tid in b.traits:
            t = by_id.get(tid)
            if t:
                op += t.opinion_others // 2
        attrs = self.effective_attrs(frm)
        if attrs:
            op += (attrs.diplomacy - 8) * 2
        op += a.opinion_cache.get(to, 0)
        return max(-100, min(100, op))

    def modify_opinion(self, frm: int, to: int, delta: int) -> None:
        c = self.character(frm)
        if not c:
            return
        cur = c.opinion_cache.get(to, 0) + delta
        cur = max(-100, min(100, cur))
        if cur == 0:
            c.opinion_cache.pop(to, None)
        else:
            c.opinion_cache[to] = cur
        if len(c.opinion_cache) > 100:
            c.opinion_cache = dict(list(c.opinion_cache.items())[-50:])

    # ---------- 继承 ----------
    def _heir_rows(self, ids: List[int]) -> List[Tuple[int, Gender, int, bool]]:
        rows = []
        for cid in ids:
            ch = self.character(cid)
            if not ch:
                continue
            rows.append((ch.id, ch.gender, ch.birth.to_ordinal(), ch.is_alive()))
        return rows

    def find_heir(self, ruler: int, law: Optional[object] = None) -> Optional[int]:
        c = self.character(ruler)
        if not c:
            return None
        children = self._heir_rows(list(c.children))
        dynasty_ids: List[int] = []
        d = self.dynasties.get(c.dynasty)
        if d:
            dynasty_ids = [m for m in d.members if m != ruler]
        dynasty_members = self._heir_rows(dynasty_ids)

        if law is not None and hasattr(law, "pick_heir"):
            heir = law.pick_heir(children, dynasty_members)
            if heir is not None:
                return heir

        # 默认：男长嗣 → 女长嗣 → 王朝成员
        sons = [r for r in children if r[3] and r[1] == Gender.MALE]
        sons.sort(key=lambda r: r[2])
        if sons:
            return sons[0][0]
        daughters = [r for r in children if r[3] and r[1] == Gender.FEMALE]
        daughters.sort(key=lambda r: r[2])
        if daughters:
            return daughters[0][0]
        for r in dynasty_members:
            if r[3]:
                return r[0]
        return None

    def on_death(self, who: int, law: Optional[object] = None) -> None:
        c = self.character(who)
        if not c or not c.is_alive():
            return
        name = c.name
        titles = list(c.held_titles)
        heir = self.find_heir(who, law=law)
        age = c.age_at(self.date)
        c.kill(self.date)
        self.push_log(f"{name} 去世，享年 {age}")
        if heir is not None:
            heir_c = self.character(heir)
            heir_name = heir_c.name if heir_c else "?"
            # 分割继承：多继承人分伯爵领
            if (
                law is not None
                and getattr(law, "partition_enabled", False)
                and hasattr(law, "partition_titles")
            ):
                living_kids = [
                    cid
                    for cid in c.children
                    if self.character(cid) and self.character(cid).is_alive()
                ]
                heirs = [heir] + [k for k in living_kids if k != heir][:3]
                parts = law.partition_titles(titles, heirs)
                for hid, tids in parts:
                    for tid in tids:
                        self.grant_title(tid, hid)
            else:
                for tid in titles:
                    self.grant_title(tid, heir)
            self.push_log(f"{heir_name} 继承了 {name} 的遗产")
        else:
            for tid in titles:
                t = self.title(tid)
                if t:
                    t.clear_holder()
                    for cid in t.counties:
                        county = self.map.get(cid)
                        if county:
                            county.holder = NONE_ID
            self.push_log(f"{name} 绝嗣，头衔悬空")

    def occupy_county(self, county_id: int, new_holder: int) -> bool:
        """军事占领：同步伯爵领 holder、COUNTY 头衔，并重建 de facto 封臣关系。"""
        county = self.map.get(county_id)
        if not county:
            return False
        county.control = 30.0
        county.holder = new_holder
        tid = county.owner_title
        if tid == NONE_ID:
            return True
        t = self.title(tid)
        if not t or t.tier != TitleTier.COUNTY:
            return True
        self.grant_title(tid, new_holder)
        # 占领后：脱离旧领主，挂到征服者主头衔下（若对方更高阶）
        conqueror = self.character(new_holder)
        if not conqueror:
            return True
        primary = self.title(conqueror.primary_title)
        if primary and primary.id != tid and primary.tier > t.tier:
            self.set_vassal(tid, primary.id)
        else:
            # 征服者自己直领，清掉旧封臣链
            self.clear_vassal_link(tid)
        return True

    # ---------- 经济 ----------
    def monthly_income_of(self, ruler: int) -> float:
        c = self.character(ruler)
        if not c:
            return 0.0
        income = 0.0
        for tid in c.held_titles:
            t = self.title(tid)
            if not t:
                continue
            for cid in t.counties:
                county = self.map.get(cid)
                if county:
                    income += county.monthly_tax()
        attrs = self.effective_attrs(ruler)
        if attrs:
            income *= 1.0 + (attrs.stewardship - 8) * 0.03
        title = self.title(c.primary_title)
        if title:
            income *= 1.0 + title.realm_law.crown_authority.tax_bonus()
        return income

    def process_monthly_economy(self) -> None:
        net_income: Dict[int, float] = {}
        for c in list(self.alive_characters()):
            income = self.monthly_income_of(c.id)
            for tid in c.held_titles:
                t = self.title(tid)
                if not t:
                    continue
                for cid in t.counties:
                    county = self.map.get(cid)
                    if county:
                        income -= county.upkeep()
            net_income[c.id] = income

        # 封臣缴税：按 de facto 层级上缴 10%
        for t in self.titles.values():
            if t.de_facto_liege != NONE_ID and t.holder != NONE_ID:
                liege_t = self.title(t.de_facto_liege)
                if liege_t and liege_t.holder != NONE_ID:
                    tax = net_income.get(t.holder, 0.0) * 0.1
                    net_income[liege_t.holder] = net_income.get(liege_t.holder, 0.0) + tax
                    net_income[t.holder] = net_income.get(t.holder, 0.0) - tax

        for cid, income in net_income.items():
            c = self.character(cid)
            if not c:
                continue
            c.add_gold(income)
            if income > 0:
                c.add_prestige(1.0)

        for county in self.map.counties.values():
            if county.control > 80 and county.development < county.terrain.development_cap():
                if random.random() < 0.05:
                    county.development = min(
                        county.terrain.development_cap(), county.development + 1
                    )
            if county.control < 100:
                county.control = min(100.0, county.control + 1.0)

    def process_health(self) -> None:
        deaths: List[int] = []
        for c in list(self.alive_characters()):
            age = c.age_at(self.date)
            if age > 45:
                c.health -= 0.002 * (age - 45)
            if age > 60:
                c.health -= 0.005
            for tid in c.traits:
                t = next((x for x in self.traits if x.id == tid), None)
                if t:
                    c.health += float(t.health_mod)
            if random.random() < 0.001:
                c.health -= 0.5
                c.add_stress(10)
            if c.health <= 0:
                deaths.append(c.id)
        for did in deaths:
            c = self.character(did)
            law = None
            if c and c.primary_title != NONE_ID:
                t = self.title(c.primary_title)
                if t:
                    law = t.realm_law
            self.on_death(did, law=law)

    def process_fertility(self) -> None:
        couples: List[Tuple[int, int]] = []
        for c in self.alive_characters():
            if c.gender == Gender.MALE and c.is_married() and c.is_adult(self.date):
                for s in c.spouses:
                    couples.append((c.id, s))
        male_names = ["艾德温", "哈罗德", "威廉", "罗伯特", "亨利"]
        female_names = ["玛蒂尔达", "爱丽丝", "埃莉诺", "伊莎贝拉", "阿黛拉"]
        for father_id, mother_id in couples:
            f = self.character(father_id)
            m = self.character(mother_id)
            if not f or not m or not m.is_alive() or m.gender != Gender.FEMALE:
                continue
            if not m.is_adult(self.date) or m.age_at(self.date) > 45:
                continue
            chance = max(0.0, min(0.15, f.fertility * m.fertility * 0.02))
            if random.random() >= chance:
                continue
            gender = Gender.MALE if random.random() < 0.5 else Gender.FEMALE
            dname = self.dynasties.get(f.dynasty)
            dlabel = dname.name if dname else "无名"
            first = random.choice(male_names if gender == Gender.MALE else female_names)
            child_name = f"{first}·{dlabel}"
            child = self.create_character(child_name, f.dynasty, gender, self.date)
            self.set_parents(child, father_id, mother_id)
            fa = self.effective_attrs(father_id)
            ma = self.effective_attrs(mother_id)
            ch = self.character(child)
            if fa and ma and ch:
                ch.base_attrs = AttributeSet(
                    diplomacy=max(1, (fa.diplomacy + ma.diplomacy) // 2 + random.randint(-2, 2)),
                    martial=max(1, (fa.martial + ma.martial) // 2 + random.randint(-2, 2)),
                    stewardship=max(
                        1, (fa.stewardship + ma.stewardship) // 2 + random.randint(-2, 2)
                    ),
                    intrigue=max(1, (fa.intrigue + ma.intrigue) // 2 + random.randint(-2, 2)),
                    learning=max(1, (fa.learning + ma.learning) // 2 + random.randint(-2, 2)),
                    prowess=max(1, (fa.prowess + ma.prowess) // 2 + random.randint(-2, 2)),
                )
                ch.culture = f.culture
                ch.faith = f.faith
            self.push_log(f"新生儿：{child_name}")
