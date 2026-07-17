"""游戏状态序列化与玩家操作。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ck_engine.ai.personality import AiPersonality
from ck_engine.core import NONE_ID
from ck_engine.game.simulation import GameSimulation
from ck_engine.military.army import ArmyStatus, UnitType
from ck_engine.politics.diplomacy import CasusBelli
from ck_engine.ui.map_layout import SEA_BAND, layout_for, points_to_svg


class GameAPI:
    def __init__(self) -> None:
        self.sim = GameSimulation()
        self.player_id = self._default_player()
        self.selected_county: Optional[int] = None
        self.selected_army: Optional[int] = None
        self.messages: List[str] = ["欢迎。点击地图省份查看详情，使用侧栏下达指令。"]

    def _default_player(self) -> int:
        for c in self.sim.world.alive_characters():
            if "哈罗德" in c.name:
                return c.id
        rulers = list(self.sim.world.rulers())
        return rulers[0].id if rulers else 1

    def notify(self, msg: str) -> None:
        self.messages.append(msg)
        if len(self.messages) > 80:
            self.messages = self.messages[-60:]

    def snapshot(self) -> Dict[str, Any]:
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

        return {
            "date": str(w.date),
            "tick": w.tick,
            "player": player_info,
            "playable": playable,
            "counties": counties,
            "edges": edge_list,
            "armies": armies,
            "wars": wars,
            "rulers": rulers,
            "log": log,
            "messages": self.messages[-12:],
            "selected_county": self.selected_county,
            "selected_army": self.selected_army,
            "sea": SEA_BAND,
            "viewbox": "0 0 820 720",
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
        kind = payload.get("action")
        try:
            if kind == "select_county":
                self.selected_county = int(payload["county_id"])
            elif kind == "select_army":
                self.selected_army = int(payload["army_id"])
            elif kind == "set_player":
                self.player_id = int(payload["character_id"])
                self.selected_army = None
                self.notify(f"切换玩家为 {self._name(self.player_id)}")
            elif kind == "advance":
                days = int(payload.get("days", 1))
                days = max(1, min(365, days))
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
            elif kind == "new_game":
                self.sim = GameSimulation()
                self.player_id = self._default_player()
                self.selected_county = None
                self.selected_army = None
                self.messages = ["新局开始。"]
            else:
                self.notify(f"未知操作: {kind}")
        except Exception as e:  # noqa: BLE001 — 返回给前端
            self.notify(f"操作失败: {e}")
        return self.snapshot()

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
        self.sim.world.push_log(f"宣战！{name} (#{wid})")
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
        self.sim.world.push_log(f"{player.name} 举办了宴会")
        self.notify("举办宴会：威望+15，压力-10")
