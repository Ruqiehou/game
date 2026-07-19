"""游戏状态序列化与玩家操作。"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ck_engine.ai.personality import AiPersonality
from ck_engine.core import NONE_ID
from ck_engine.game.simulation import GameSimulation
from ck_engine.military.army import ArmyStatus, UnitType
from ck_engine.politics.diplomacy import CasusBelli
from ck_engine.core.balance import (
    FACTION_APPEASE_GOLD,
    FACTION_APPEASE_PLAYER,
    FACTION_FEAST_APPEASE,
    FEAST_GOLD,
    FEAST_PRESTIGE,
    FEAST_STRESS,
    IMPROVE_RELATIONS_GOLD,
    SUPPLY_LOW_THRESHOLD,
    SUPPLY_MOVE_SLOW_THRESHOLD,
)
from ck_engine.ui.map_layout import layout_for, points_to_svg, sea_band, viewbox


class GameAPI:
    def __init__(self) -> None:
        self.sim = GameSimulation()
        self.player_id = self._default_player()
        self.sim.player_ids = {self.player_id}
        self.selected_county: Optional[int] = None
        self.selected_army: Optional[int] = None
        self.messages: List[str] = ["欢迎。点击地图省份查看详情，使用侧栏下达指令。"]
        self.save_path = Path(__file__).resolve().parents[2] / "saves" / "autosave.json"
        self._lock = threading.Lock()

    def _default_player(self) -> int:
        for c in self.sim.world.alive_characters():
            if "哈罗德" in c.name:
                return c.id
        rulers = list(self.sim.world.rulers())
        return rulers[0].id if rulers else 1

    def _sync_player(self) -> None:
        self.sim.player_ids = {self.player_id}

    def notify(self, msg: str) -> None:
        self.messages.append(msg)
        if len(self.messages) > 80:
            self.messages = self.messages[-60:]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> Dict[str, Any]:
        w = self.sim.world
        player = w.character(self.player_id)
        counties = []
        for county in w.map.iter():
            layout = layout_for(county.name)
            holder = w.character(county.holder)
            color = self._holder_color(county.holder)
            armies_here = [
                a.id
                for a in self.sim.wars.armies.values()
                if a.is_active() and a.location == county.id
            ]
            siege = self.sim.sieges.active_at(county.id)
            counties.append(
                {
                    "id": county.id,
                    "name": county.name,
                    "terrain": county.terrain.name,
                    "development": county.development,
                    "control": round(county.control, 1),
                    "levies": county.monthly_levies(),
                    "tax": round(county.monthly_tax(), 2),
                    "fort": county.fort_level,
                    "holder_id": county.holder if county.holder != NONE_ID else None,
                    "holder_name": holder.name if holder else "无主",
                    "color": color,
                    "cx": layout["cx"],
                    "cy": layout["cy"],
                    "points": points_to_svg(layout["points"]),
                    "neighbors": list(county.neighbors),
                    "armies": armies_here,
                    "siege": (
                        {
                            "progress": round(siege.progress, 1),
                            "required": round(siege.required_progress(), 1),
                            "attacker": siege.attacker,
                        }
                        if siege
                        else None
                    ),
                    "is_player": bool(holder and holder.id == self.player_id),
                }
            )

        edges = set()
        for county in w.map.iter():
            for n in county.neighbors:
                a, b = sorted((county.id, n))
                edges.add((a, b))
        edge_list = []
        by_id = {c["id"]: c for c in counties}
        for a, b in edges:
            ca, cb = by_id.get(a), by_id.get(b)
            if ca and cb:
                edge_list.append(
                    {"x1": ca["cx"], "y1": ca["cy"], "x2": cb["cx"], "y2": cb["cy"]}
                )

        armies = []
        for a in self.sim.wars.armies.values():
            if not a.is_active():
                continue
            loc = w.map.get(a.location)
            owner = w.character(a.owner)
            layout = layout_for(loc.name) if loc else {"cx": 0, "cy": 0}
            supply = round(a.supply, 1)
            in_enemy = False
            if loc:
                for war in self.sim.wars.active_wars():
                    if not war.involves(a.owner):
                        continue
                    enemies = {
                        p.character
                        for p in war.participants
                        if war.is_attacker(p.character) != war.is_attacker(a.owner)
                    }
                    if loc.holder in enemies:
                        in_enemy = True
                        break
            armies.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "owner_id": a.owner,
                    "owner_name": owner.name if owner else "?",
                    "location": a.location,
                    "location_name": loc.name if loc else "?",
                    "men": a.total_men(),
                    "status": a.status.name,
                    "morale": round(a.morale, 1),
                    "supply": supply,
                    "supply_low": supply < SUPPLY_LOW_THRESHOLD,
                    "supply_slow": supply < SUPPLY_MOVE_SLOW_THRESHOLD,
                    "in_enemy": in_enemy,
                    "cx": layout["cx"],
                    "cy": layout["cy"] - 18,
                    "is_player": a.owner == self.player_id,
                    "path": list(a.path),
                }
            )

        wars = []
        for war in self.sim.wars.wars.values():
            atk = w.character(war.attacker_primary)
            dfd = w.character(war.defender_primary)
            months = war.months_elapsed(w.date) if war.active else 0
            atk_exh = self.sim.diplomacy.war_exhaustion.get(war.attacker_primary, 0.0)
            def_exh = self.sim.diplomacy.war_exhaustion.get(war.defender_primary, 0.0)
            can_wp = False
            if war.active and war.involves(self.player_id):
                can_wp = war.can_white_peace(w.date, atk_exh, def_exh) or (
                    months >= 12 or (months >= 6 and abs(war.warscore) <= 40)
                )
            wars.append(
                {
                    "id": war.id,
                    "name": war.name,
                    "active": war.active,
                    "warscore": war.warscore,
                    "cb": war.cb.name_zh(),
                    "attacker": atk.name if atk else "?",
                    "defender": dfd.name if dfd else "?",
                    "involves_player": war.involves(self.player_id),
                    "months": months,
                    "can_white_peace": can_wp,
                }
            )

        rulers = []
        for r in w.rulers():
            attrs = w.effective_attrs(r.id)
            title = w.title(r.primary_title)
            profile = AiPersonality.profile_of(w, r.id)
            rulers.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "title": title.name if title else "无",
                    "gold": round(r.gold, 1),
                    "prestige": round(r.prestige, 1),
                    "martial": attrs.martial if attrs else 0,
                    "income": round(w.monthly_income_of(r.id), 1),
                    "men": self.sim.wars.total_men_of(r.id),
                    "persona": AiPersonality.describe(profile),
                    "is_player": r.id == self.player_id,
                }
            )

        log = w.log[-30:]
        player_info = None
        if player:
            title = w.title(player.primary_title)
            attrs = w.effective_attrs(player.id)
            player_info = {
                "id": player.id,
                "name": player.name,
                "title": title.name if title else "无",
                "gold": round(player.gold, 1),
                "prestige": round(player.prestige, 1),
                "piety": round(player.piety, 1),
                "stress": player.stress,
                "health": round(player.health, 2),
                "attrs": {
                    "diplomacy": attrs.diplomacy if attrs else 0,
                    "martial": attrs.martial if attrs else 0,
                    "stewardship": attrs.stewardship if attrs else 0,
                    "intrigue": attrs.intrigue if attrs else 0,
                    "learning": attrs.learning if attrs else 0,
                    "prowess": attrs.prowess if attrs else 0,
                },
                "income": round(w.monthly_income_of(player.id), 1),
                "men": self.sim.wars.total_men_of(player.id),
            }

        playable = [
            {"id": r.id, "name": r.name, "title": (w.title(r.primary_title).name if w.title(r.primary_title) else "")}
            for r in w.rulers()
        ]

        factions = []
        for f in self.sim.factions.factions.values():
            if f.target_liege != self.player_id:
                continue
            factions.append(
                {
                    "id": f.id,
                    "kind": f.kind.name_zh() if hasattr(f.kind, "name_zh") else f.kind.name,
                    "members": len(f.members),
                    "power": round(f.power, 1),
                    "discontent": round(f.discontent, 1),
                    "ultimatum": f.ultimatum_sent,
                }
            )

        player_exh = round(self.sim.diplomacy.war_exhaustion.get(self.player_id, 0.0), 1)

        return {
            "date": str(w.date),
            "season": w.date.season().name,
            "tick": w.tick,
            "player": player_info,
            "player_war_exhaustion": player_exh,
            "playable": playable,
            "counties": counties,
            "edges": edge_list,
            "armies": armies,
            "wars": wars,
            "factions": factions,
            "rulers": rulers,
            "log": log,
            "messages": self.messages[-12:],
            "selected_county": self.selected_county,
            "selected_army": self.selected_army,
            "sea": sea_band(),
            "viewbox": viewbox(),
            "supply_low_threshold": SUPPLY_LOW_THRESHOLD,
        }

    def _holder_color(self, holder_id: int) -> str:
        if holder_id == NONE_ID:
            return "#4a5568"
        w = self.sim.world
        c = w.character(holder_id)
        if not c:
            return "#4a5568"
        d = w.dynasties.get(c.dynasty)
        if d and d.color:
            r, g, b = d.color
            return f"rgb({r},{g},{b})"
        # 按 id 生成稳定色
        hue = (holder_id * 47) % 360
        return f"hsl({hue} 55% 42%)"

    # ---------- 操作 ----------
    def action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            return self._action_unlocked(payload)

    def _action_unlocked(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        kind = payload.get("action")
        try:
            if kind == "select_county":
                self.selected_county = int(payload["county_id"])
            elif kind == "select_army":
                self.selected_army = int(payload["army_id"])
            elif kind == "set_player":
                self.player_id = int(payload["character_id"])
                self._sync_player()
                self.selected_army = None
                self.notify(f"切换玩家为 {self._name(self.player_id)}")
            elif kind == "advance":
                days = int(payload.get("days", 1))
                days = max(1, min(365, days))
                self._sync_player()
                self.sim.run_days(days)
                self.notify(f"时间推进 {days} 天 → {self.sim.world.date}")
            elif kind == "raise_army":
                self._raise_army(int(payload["county_id"]))
            elif kind == "move_army":
                self._move_army(int(payload["army_id"]), int(payload["county_id"]))
            elif kind == "disband_army":
                self._disband_army(int(payload["army_id"]))
            elif kind == "declare_war":
                self._declare_war(int(payload["target_id"]))
            elif kind == "improve_relations":
                self._improve(int(payload["target_id"]))
            elif kind == "hold_feast":
                self._feast()
            elif kind == "appease_faction":
                self._appease_faction(int(payload["faction_id"]))
            elif kind == "white_peace":
                self._white_peace(int(payload["war_id"]))
            elif kind == "save":
                self._save(payload.get("name"))
            elif kind == "load":
                self._load(payload.get("name"))
            elif kind == "delete_save":
                self._delete_save(str(payload["name"]))
            elif kind == "new_game":
                self.sim = GameSimulation()
                self.player_id = self._default_player()
                self._sync_player()
                self.selected_county = None
                self.selected_army = None
                self.messages = ["新局开始。"]
            else:
                self.notify(f"未知操作: {kind}")
        except Exception as e:  # noqa: BLE001 — 返回给前端
            self.notify(f"操作失败: {e}")
        return self._snapshot_unlocked()

    def _name(self, cid: int) -> str:
        c = self.sim.world.character(cid)
        return c.name if c else "?"

    def _raise_army(self, county_id: int) -> None:
        county = self.sim.world.map.get(county_id)
        if not county:
            raise ValueError("省份不存在")
        if county.holder != self.player_id:
            # 允许在自己任意领地征召：若点到别人地，用首都
            owned = [
                c.id
                for c in self.sim.world.map.iter()
                if c.holder == self.player_id
            ]
            if not owned:
                raise ValueError("没有可征召的领地")
            if county_id not in owned:
                county_id = owned[0]
                county = self.sim.world.map.get(county_id)
        if self.sim.wars.armies_of(self.player_id):
            raise ValueError("已有野战军，请先解散或用现有军团")
        levies = max(100, county.monthly_levies() * 3)
        # 汇总玩家全部征召
        total = 0
        for c in self.sim.world.map.iter():
            if c.holder == self.player_id:
                total += c.monthly_levies()
        levies = max(200, total)
        aid = self.sim.wars.raise_army(
            self.player_id, county_id, levies, f"{self._name(self.player_id)}的军团"
        )
        army = self.sim.wars.army(aid)
        if army:
            army.add_men(UnitType.HEAVY_INFANTRY, levies // 10)
            army.add_men(UnitType.ARCHERS, levies // 12)
            army.add_men(UnitType.LIGHT_CAVALRY, levies // 20)
        self.selected_army = aid
        self.sim.world.push_log(f"{self._name(self.player_id)} 在 {county.name} 征召 {levies} 人")
        self.notify(f"征召成功：{levies} 人 @ {county.name}")

    def _move_army(self, army_id: int, county_id: int) -> None:
        army = self.sim.wars.army(army_id)
        if not army or not army.is_active():
            raise ValueError("军团不存在")
        if army.owner != self.player_id:
            raise ValueError("只能调动自己的军团")
        path = self.sim.world.map.path(army.location, county_id)
        if not path:
            raise ValueError("无法到达该省份")
        army.set_path(path)
        dest = self.sim.world.map.get(county_id)
        dname = dest.name if dest else "?"
        self.sim.world.push_log(f"{army.name} 向 {dname} 进军")
        self.notify(f"下令进军：{army.name} → {dname}（{len(path)-1} 步）")
        self.selected_army = army_id

    def _disband_army(self, army_id: int) -> None:
        army = self.sim.wars.army(army_id)
        if not army or army.owner != self.player_id:
            raise ValueError("无法解散该军团")
        army.status = ArmyStatus.DISBANDED
        army.stacks.clear()
        self.selected_army = None
        self.notify(f"已解散 {army.name}")

    def _declare_war(self, target_id: int) -> None:
        if target_id == self.player_id:
            raise ValueError("不能对自己宣战")
        dip = self.sim.diplomacy
        if dip.are_allied(self.player_id, target_id):
            raise ValueError("同盟无法宣战")
        if not dip.can_declare_war(self.player_id, target_id, self.sim.world.date.year):
            raise ValueError("外交上无法宣战（同盟/停战/已交战）")
        if any(
            w.involves(self.player_id) or w.involves(target_id)
            for w in self.sim.wars.active_wars()
        ):
            raise ValueError("一方已在战争中")
        player = self.sim.world.character(self.player_id)
        target = self.sim.world.character(target_id)
        if not player or not target:
            raise ValueError("目标无效")
        cb = CasusBelli.RIVALRY if dip.flags(self.player_id, target_id).rival else CasusBelli.CONQUEST
        cost = cb.prestige_cost()
        if player.prestige < cost:
            raise ValueError(f"威望不足（需要 {cost}）")
        player.add_prestige(-cost)
        name = f"{player.name} 对 {target.name} 的{cb.name_zh()}"
        wid = self.sim.wars.declare_war(cb, self.player_id, target_id, self.sim.world.date, name)
        dip.set_at_war(self.player_id, target_id, True)
        war = self.sim.wars.war(wid)
        if war:
            from ck_engine.military.war import WarParticipant

            for ally in dip.allies_of(self.player_id):
                if ally != target_id and not war.involves(ally):
                    war.participants.append(
                        WarParticipant(character=ally, is_attacker=True, joined=self.sim.world.date)
                    )
                    dip.set_at_war(ally, target_id, True)
        self.sim.world.push_log(f"宣战！{name} (#{wid})")
        dip.add_war_exhaustion(self.player_id)
        dip.add_war_exhaustion(target_id)
        self.notify(f"已对 {target.name} 宣战")

    def _improve(self, target_id: int) -> None:
        player = self.sim.world.character(self.player_id)
        if not player or player.gold < 10:
            raise ValueError("金币不足（需要 10）")
        player.add_gold(-10)
        self.sim.world.modify_opinion(target_id, self.player_id, 15)
        self.sim.world.modify_opinion(self.player_id, target_id, 5)
        self.notify(f"改善与 {self._name(target_id)} 的关系")

    def _feast(self) -> None:
        player = self.sim.world.character(self.player_id)
        if not player or player.gold < 20:
            raise ValueError("金币不足（需要 20）")
        player.add_gold(-20)
        player.add_prestige(15)
        player.add_stress(-10)
        # 宴会也安抚针对玩家的派系
        for f in list(self.sim.factions.factions.values()):
            if f.target_liege == self.player_id:
                for mid in list(f.members):
                    self.sim.world.modify_opinion(mid, self.player_id, 8)
                self.sim.factions.appease(f.id, 10.0)
        self.sim.world.push_log(f"{player.name} 举办了宴会")
        self.notify("举办宴会：威望+15，压力-10，派系不满下降")

    def _appease_faction(self, faction_id: int) -> None:
        f = self.sim.factions.factions.get(faction_id)
        if not f:
            raise ValueError("派系不存在")
        if f.target_liege != self.player_id:
            raise ValueError("只能安抚针对自己的派系")
        player = self.sim.world.character(self.player_id)
        cost = 25
        if not player or player.gold < cost:
            raise ValueError(f"金币不足（需要 {cost}）")
        player.add_gold(-cost)
        for mid in f.members:
            self.sim.world.modify_opinion(mid, self.player_id, 12)
        ok = self.sim.factions.appease(faction_id, 30.0)
        if not ok or faction_id not in self.sim.factions.factions:
            self.notify("派系已解散")
            self.sim.world.push_log(f"{player.name} 成功安抚并解散了一个派系")
        else:
            left = self.sim.factions.factions[faction_id]
            self.notify(f"派系不满降至 {left.discontent:.0f}")
            self.sim.world.push_log(f"{player.name} 安抚了派系，不满下降")

    def _white_peace(self, war_id: int) -> None:
        from ck_engine.military.war import WarResult

        w = self.sim.wars.war(war_id)
        if not w or not w.active:
            raise ValueError("战争不存在或已结束")
        if not w.involves(self.player_id):
            raise ValueError("只能提议自己参与的战争白和")
        atk_exh = self.sim.diplomacy.war_exhaustion.get(w.attacker_primary, 0.0)
        def_exh = self.sim.diplomacy.war_exhaustion.get(w.defender_primary, 0.0)
        # 玩家可主动提议：条件略宽于自动白和
        months = w.months_elapsed(self.sim.world.date)
        if months < 6 and abs(w.warscore) > 40:
            raise ValueError("战况未僵持，无法白和")
        if not w.can_white_peace(self.sim.world.date, atk_exh, def_exh) and months < 12:
            raise ValueError("战争时间太短或条件不足")
        self.sim.wars.end_war(war_id, WarResult.WHITE_PEACE)
        self.sim.diplomacy.set_at_war(w.attacker_primary, w.defender_primary, False)
        self.sim.diplomacy.set_truce(
            w.attacker_primary, w.defender_primary, self.sim.world.date.year + 3
        )
        an = self.sim.world.character(w.attacker_primary)
        dn = self.sim.world.character(w.defender_primary)
        self.sim.world.push_log(
            f"白和：{(an.name if an else '?')} 与 {(dn.name if dn else '?')} 停战"
        )
        self.notify("已达成白和")

    def _save_file(self, name: Any = None) -> Path:
        if name is None or str(name).strip() == "":
            return self.save_path
        safe = Path(str(name)).name
        if not safe.endswith(".json"):
            safe = f"{safe}.json"
        return self.save_path.parent / safe

    def _delete_save(self, name: str) -> None:
        path = self._save_file(name)
        if path.stem == "autosave":
            raise ValueError("不能删除自动存档")
        if not path.exists():
            raise ValueError("存档不存在")
        path.unlink()
        self.notify(f"已删除存档 → {path.name}")

    def _save(self, name: Any = None) -> None:
        """完整快照：日期、玩家、人物、省份、头衔、战争、外交、派系、阴谋、军团、围城。"""
        w = self.sim.world
        sim = self.sim
        data = {
            "date": [w.date.year, w.date.month, w.date.day],
            "tick": w.tick,
            "player_id": self.player_id,
            "characters": {
                str(c.id): {
                    "gold": c.gold,
                    "prestige": c.prestige,
                    "piety": c.piety,
                    "stress": c.stress,
                    "health": c.health,
                    "life": c.life.name,
                    "held_titles": list(c.held_titles),
                    "primary_title": c.primary_title,
                    "is_ruler": c.is_ruler,
                    "father": c.father,
                    "mother": c.mother,
                    "spouses": list(c.spouses),
                    "children": list(c.children),
                    "traits": list(c.traits),
                    "opinion_cache": dict(c.opinion_cache),
                }
                for c in w.characters.values()
            },
            "counties": {
                str(c.id): {"holder": c.holder, "control": c.control, "development": c.development}
                for c in w.map.iter()
            },
            "titles": {
                str(t.id): {"holder": t.holder, "de_facto_liege": t.de_facto_liege, "de_facto_vassals": list(t.de_facto_vassals)}
                for t in w.titles.values()
            },
            "wars": [
                {
                    "id": war.id, "name": war.name, "cb": war.cb.name,
                    "attacker_primary": war.attacker_primary, "defender_primary": war.defender_primary,
                    "start": [war.start.year, war.start.month, war.start.day],
                    "warscore": war.warscore, "active": war.active,
                    "result": war.result.name,
                    "participants": [{"character": p.character, "is_attacker": p.is_attacker, "joined": [p.joined.year, p.joined.month, p.joined.day]} for p in war.participants],
                }
                for war in sim.wars.wars.values()
            ],
            "armies": [
                {
                    "id": a.id, "owner": a.owner, "name": a.name, "location": a.location,
                    "commander": a.commander, "status": a.status.name, "morale": a.morale,
                    "supply": a.supply,
                    "path": list(a.path), "stacks": [{"unit_type": s.unit_type.name, "men": s.men} for s in a.stacks],
                }
                for a in sim.wars.armies.values() if a.status != ArmyStatus.DISBANDED
            ],
            "sieges": [
                {
                    "id": s.id, "county": s.county, "attacker_army": s.attacker_army,
                    "attacker": s.attacker, "defender": s.defender, "fort_level": s.fort_level,
                    "garrison": s.garrison, "progress": s.progress, "started": [s.started.year, s.started.month, s.started.day] if s.started else None,
                }
                for s in sim.sieges.sieges.values() if s.active
            ],
            "diplomacy": {
                "relations": {f"{k[0]},{k[1]}": {"allied": v.allied, "at_war": v.at_war, "rival": v.rival, "marriage_pact": v.marriage_pact, "non_aggression": v.non_aggression} for k, v in sim.diplomacy.relations.items()},
                "treaties": [{"a": t.a, "b": t.b, "kind": t.kind.name, "start": [t.start.year, t.start.month, t.start.day], "expires_year": t.expires_year} for t in sim.diplomacy.treaties],
                "claims": {str(k): [{"title": c.title, "county": c.county, "strength": c.strength, "pressed": c.pressed} for c in v] for k, v in sim.diplomacy.claims.items()},
                "truce_until": {f"{k[0]},{k[1]}": v for k, v in sim.diplomacy.truce_until.items()},
                "war_exhaustion": dict(sim.diplomacy.war_exhaustion),
            },
            "factions": [
                {
                    "id": f.id, "kind": f.kind.name, "target_liege": f.target_liege,
                    "members": list(f.members), "power": f.power, "discontent": f.discontent,
                }
                for f in sim.factions.factions.values()
            ],
            "schemes": [
                {
                    "id": s.id, "kind": s.kind.name, "owner": s.owner, "target": s.target,
                    "progress": s.progress, "secrecy": s.secrecy,
                    "started": [s.started.year, s.started.month, s.started.day] if s.started else None,
                    "exposed": s.exposed,
                }
                for s in sim.schemes.schemes.values()
                if not s.exposed and not s.is_complete()
            ],
            "councils": {
                str(rid): {
                    "chancellor": c.chancellor,
                    "marshal": c.marshal,
                    "steward": c.steward,
                    "spymaster": c.spymaster,
                    "chaplain": c.chaplain,
                    "tasks": {pos.name: task.name for pos, task in c.tasks.items()},
                }
                for rid, c in sim.councils.by_ruler.items()
            },
            "log": w.log[-100:],
            "messages": self.messages[-20:],
        }
        path = self._save_file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if name is None:
            self.save_path = path
        self.notify(f"已存档 → {path.name}")

    def _load(self, name: Any = None) -> None:
        path = self._save_file(name)
        if not path.exists():
            raise ValueError("没有存档")
        data = json.loads(path.read_text(encoding="utf-8"))
        # 新开局再覆盖动态状态，保证 ID 一致
        self.sim = GameSimulation()
        w = self.sim.world
        sim = self.sim
        from ck_engine.core import GameDate
        from ck_engine.world.character import LifeState
        from ck_engine.military.war import War, WarParticipant, WarResult
        from ck_engine.military.army import Army, ArmyStatus, UnitType
        from ck_engine.military.siege import Siege
        from ck_engine.politics.diplomacy import CasusBelli, Treaty, TreatyKind, Claim, RelationFlags
        from ck_engine.politics.factions import Faction, FactionKind
        from ck_engine.politics.schemes import Scheme, SchemeKind
        from ck_engine.politics.council import Council, CouncilPosition, CouncilTask

        y, m, d = data["date"]
        w.date = GameDate(y, m, d)
        w.tick = int(data.get("tick", 0))
        for cid, row in data.get("characters", {}).items():
            c = w.character(int(cid))
            if not c:
                continue
            c.gold = row["gold"]
            c.prestige = row["prestige"]
            c.piety = row.get("piety", c.piety)
            c.stress = row.get("stress", 0)
            c.health = row.get("health", c.health)
            c.father = row.get("father", c.father)
            c.mother = row.get("mother", c.mother)
            c.spouses = list(row.get("spouses", []))
            c.children = list(row.get("children", []))
            c.traits = list(row.get("traits", []))
            c.opinion_cache = {int(k): v for k, v in row.get("opinion_cache", {}).items()}
            if row.get("life") == "DEAD":
                c.life = LifeState.DEAD
                c.is_ruler = False
            else:
                c.held_titles = list(row.get("held_titles", []))
                c.primary_title = row.get("primary_title", c.primary_title)
                c.is_ruler = bool(row.get("is_ruler", c.is_ruler))
        for tid, row in data.get("titles", {}).items():
            t = w.title(int(tid))
            if t:
                t.holder = row["holder"]
                t.de_facto_liege = row.get("de_facto_liege", t.de_facto_liege)
                t.de_facto_vassals = list(row.get("de_facto_vassals", []))
        for cid, row in data.get("counties", {}).items():
            county = w.map.get(int(cid))
            if county:
                county.holder = row["holder"]
                county.control = row.get("control", county.control)
                county.development = row.get("development", county.development)

        # 恢复战争
        sim.wars.wars.clear()
        sim.wars.next_war = 1
        for row in data.get("wars", []):
            war = War(
                id=row["id"], name=row["name"], cb=CasusBelli[row["cb"]],
                attacker_primary=row["attacker_primary"], defender_primary=row["defender_primary"],
                start=GameDate(*row["start"]), warscore=row["warscore"], active=row["active"],
                result=WarResult[row["result"]],
            )
            war.participants = [
                WarParticipant(character=p["character"], is_attacker=p["is_attacker"], joined=GameDate(*p["joined"]))
                for p in row.get("participants", [])
            ]
            sim.wars.wars[war.id] = war
            sim.wars.next_war = max(sim.wars.next_war, war.id + 1)

        # 恢复军团
        sim.wars.armies.clear()
        sim.wars.next_army = 1
        for row in data.get("armies", []):
            army = Army(
                id=row["id"], owner=row["owner"], name=row["name"],
                location=row["location"], commander=row["commander"],
            )
            army.status = ArmyStatus[row["status"]]
            army.morale = row.get("morale", 100.0)
            army.supply = row.get("supply", army.supply)
            army.path = list(row.get("path", []))
            for s in row.get("stacks", []):
                army.add_men(UnitType[s["unit_type"]], s["men"])
            sim.wars.armies[army.id] = army
            sim.wars.next_army = max(sim.wars.next_army, army.id + 1)

        # 恢复围城
        sim.sieges.sieges.clear()
        sim.sieges.next_id = 1
        for row in data.get("sieges", []):
            started = GameDate(*row["started"]) if row.get("started") else None
            siege = Siege(
                id=row["id"], county=row["county"], attacker_army=row["attacker_army"],
                attacker=row["attacker"], defender=row["defender"], fort_level=row["fort_level"],
                garrison=row["garrison"], started=started,
            )
            siege.progress = row.get("progress", 0.0)
            sim.sieges.sieges[siege.id] = siege
            sim.sieges.next_id = max(sim.sieges.next_id, siege.id + 1)

        # 恢复外交
        sim.diplomacy.relations.clear()
        for k, v in data.get("diplomacy", {}).get("relations", {}).items():
            a, b = map(int, k.split(","))
            sim.diplomacy.relations[(a, b)] = RelationFlags(
                allied=v.get("allied", False), at_war=v.get("at_war", False),
                rival=v.get("rival", False), marriage_pact=v.get("marriage_pact", False),
                non_aggression=v.get("non_aggression", False),
            )
        sim.diplomacy.treaties.clear()
        for row in data.get("diplomacy", {}).get("treaties", []):
            sim.diplomacy.treaties.append(Treaty(
                a=row["a"], b=row["b"], kind=TreatyKind[row["kind"]],
                start=GameDate(*row["start"]), expires_year=row["expires_year"],
            ))
        sim.diplomacy.claims.clear()
        for k, v in data.get("diplomacy", {}).get("claims", {}).items():
            sim.diplomacy.claims[int(k)] = [
                Claim(claimant=int(k), title=c["title"], county=c.get("county"), strength=c.get("strength", 50), pressed=c.get("pressed", False))
                for c in v
            ]
        sim.diplomacy.truce_until.clear()
        for k, v in data.get("diplomacy", {}).get("truce_until", {}).items():
            a, b = map(int, k.split(","))
            sim.diplomacy.truce_until[(a, b)] = v
        sim.diplomacy.war_exhaustion = {int(k): v for k, v in data.get("diplomacy", {}).get("war_exhaustion", {}).items()}

        # 恢复派系
        sim.factions.factions.clear()
        sim.factions.next_id = 1
        for row in data.get("factions", []):
            faction = Faction(
                id=row["id"], kind=FactionKind[row["kind"]], target_liege=row["target_liege"],
                members=list(row["members"]), power=row["power"], discontent=row["discontent"],
            )
            sim.factions.factions[faction.id] = faction
            sim.factions.next_id = max(sim.factions.next_id, faction.id + 1)

        # 恢复阴谋
        sim.schemes.schemes.clear()
        sim.schemes.next_id = 1
        for row in data.get("schemes", []):
            started = GameDate(*row["started"]) if row.get("started") else None
            scheme = Scheme(
                id=row["id"], kind=SchemeKind[row["kind"]], owner=row["owner"], target=row["target"],
                started=started,
            )
            scheme.progress = row.get("progress", 0.0)
            scheme.secrecy = row.get("secrecy", 100.0)
            scheme.exposed = bool(row.get("exposed", False))
            sim.schemes.schemes[scheme.id] = scheme
            sim.schemes.next_id = max(sim.schemes.next_id, scheme.id + 1)

        # 恢复内阁
        sim.councils.by_ruler.clear()
        for rid, row in data.get("councils", {}).items():
            council = Council.empty(int(rid))
            council.chancellor = row.get("chancellor", council.chancellor)
            council.marshal = row.get("marshal", council.marshal)
            council.steward = row.get("steward", council.steward)
            council.spymaster = row.get("spymaster", council.spymaster)
            council.chaplain = row.get("chaplain", council.chaplain)
            tasks = {}
            for pos_name, task_name in row.get("tasks", {}).items():
                try:
                    tasks[CouncilPosition[pos_name]] = CouncilTask[task_name]
                except KeyError:
                    continue
            if tasks:
                council.tasks = tasks
            sim.councils.by_ruler[int(rid)] = council

        w.log = list(data.get("log", []))
        self.messages = list(data.get("messages", ["读档完成"]))
        self.player_id = int(data.get("player_id", self._default_player()))
        self._sync_player()
        self.selected_county = None
        self.selected_army = None
        if name is None:
            self.save_path = path
        self.notify(f"已读档 ← {path.name}")
