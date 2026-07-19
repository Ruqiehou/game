"""游戏状态序列化与玩家操作。"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ck_engine.ai.personality import AiPersonality
from ck_engine.core import NONE_ID
from ck_engine.game.simulation import GameSimulation
from ck_engine.military.army import ArmyStatus, UnitType
from ck_engine.politics.council import CouncilPosition, CouncilTask
from ck_engine.politics.diplomacy import CasusBelli, TreatyKind
from ck_engine.politics.laws import CrownAuthority, GenderLaw, SuccessionLaw
from ck_engine.politics.schemes import SchemeKind
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
                    "buildings": list(county.buildings),
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
                "laws": self._player_laws(),
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
            "saves": self._list_saves(),
            "pending_events": [
                {
                    "event_id": inst.event_id,
                    "title": inst.title,
                    "description": inst.description,
                    "choices": [
                        {"id": c.id, "text": c.text, "ai_weight": c.ai_weight}
                        for c in inst.choices
                    ],
                }
                for inst in self.sim.events.pending
                if inst.character == self.player_id
            ],
            "player_schemes": self._player_schemes(),
            "player_council": self._player_council(),
            "player_claims": self._player_claims(),
            "treaties": self._player_treaties(),
            "characters": self._all_characters(),
            "scheme_types": [(k, v) for k, v in [
                ("MURDER", "谋杀"), ("ABDUCT", "绑架"), ("FABRICATE_HOOK", "伪造把柄"),
                ("SWAY", "拉拢"), ("SEDUCE", "引诱"), ("CLAIM_FABRICATION", "伪造宣称"),
            ]],
            "council_positions": [(p.name, p.name_zh()) for p in CouncilPosition.all()],
            "council_tasks": [(t.name, t.name_zh()) for t in CouncilTask],
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

    # ---------- snapshot 辅助 ----------
    def _player_schemes(self) -> List[Dict[str, Any]]:
        out = []
        for s in self.sim.schemes.schemes.values():
            if s.owner != self.player_id or s.exposed or s.is_complete():
                continue
            target = self.sim.world.character(s.target)
            out.append({
                "id": s.id,
                "kind": s.kind.name,
                "kind_zh": s.kind.name_zh(),
                "target_id": s.target,
                "target_name": target.name if target else "?",
                "progress": round(s.progress, 1),
                "secrecy": round(s.secrecy, 1),
            })
        return out

    def _player_council(self) -> Optional[Dict[str, Any]]:
        council = self.sim.councils.get(self.player_id)
        if not council:
            return None
        w = self.sim.world
        members = []
        for pos in CouncilPosition.all():
            who = council.get(pos)
            task = council.task_of(pos)
            ch = w.character(who) if who != NONE_ID else None
            members.append({
                "position": pos.name,
                "position_zh": pos.name_zh(),
                "holder_id": who if who != NONE_ID else None,
                "holder_name": ch.name if ch else "（空缺）",
                "task": task.name,
                "task_zh": task.name_zh(),
            })
        return {"members": members}

    def _player_claims(self) -> List[Dict[str, Any]]:
        out = []
        w = self.sim.world
        for claim in self.sim.diplomacy.claims_of(self.player_id):
            title = w.title(claim.title) if claim.title != NONE_ID else None
            county = w.map.get(claim.county) if claim.county else None
            out.append({
                "title_id": claim.title if claim.title != NONE_ID else None,
                "title_name": title.name if title else None,
                "county_id": claim.county,
                "county_name": county.name if county else None,
                "strength": claim.strength,
                "pressed": claim.pressed,
            })
        return out

    def _player_treaties(self) -> List[Dict[str, Any]]:
        out = []
        w = self.sim.world
        for t in self.sim.diplomacy.treaties:
            if t.a != self.player_id and t.b != self.player_id:
                continue
            other_id = t.b if t.a == self.player_id else t.a
            other = w.character(other_id)
            out.append({
                "kind": t.kind.name,
                "kind_zh": t.kind.name_zh(),
                "other_id": other_id,
                "other_name": other.name if other else "?",
                "expires_year": t.expires_year,
            })
        # 停战
        for (a, b), until in self.sim.diplomacy.truce_until.items():
            if self.player_id not in (a, b):
                continue
            other_id = b if a == self.player_id else a
            other = w.character(other_id)
            if until > w.date.year:
                out.append({
                    "kind": "TRUCE",
                    "kind_zh": "停战",
                    "other_id": other_id,
                    "other_name": other.name if other else "?",
                    "expires_year": until,
                })
        return out

    def _all_characters(self) -> List[Dict[str, Any]]:
        """输出所有存活角色的简要信息，供前端人物详情面板使用。"""
        w = self.sim.world
        out = []
        for c in w.alive_characters():
            attrs = w.effective_attrs(c.id)
            dynasty = w.dynasties.get(c.dynasty)
            title = w.title(c.primary_title) if c.primary_title != NONE_ID else None
            out.append({
                "id": c.id,
                "name": c.name,
                "dynasty_name": dynasty.name if dynasty else "",
                "gender": c.gender.name,
                "age": c.age_at(w.date),
                "is_ruler": c.is_ruler,
                "title": title.name if title else "",
                "gold": round(c.gold, 0),
                "prestige": round(c.prestige, 0),
                "is_married": c.is_married(),
                "spouse_ids": list(c.spouses),
                "attrs": {
                    "diplomacy": attrs.diplomacy if attrs else 0,
                    "martial": attrs.martial if attrs else 0,
                    "stewardship": attrs.stewardship if attrs else 0,
                    "intrigue": attrs.intrigue if attrs else 0,
                    "learning": attrs.learning if attrs else 0,
                    "prowess": attrs.prowess if attrs else 0,
                } if attrs else None,
                "opinion_of_player": w.opinion(c.id, self.player_id),
                "player_opinion": w.opinion(self.player_id, c.id),
                "relation_allied": self.sim.diplomacy.are_allied(self.player_id, c.id),
                "relation_rival": self.sim.diplomacy.flags(self.player_id, c.id).rival,
                "relation_at_war": self.sim.diplomacy.flags(self.player_id, c.id).at_war,
                "relation_marriage": self.sim.diplomacy.flags(self.player_id, c.id).marriage_pact,
                "held_title_ids": list(c.held_titles),
            })
        return out

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
                prev_chunk = self.sim.world.tick // 30
                self._sync_player()
                self.sim.run_days(days)
                new_chunk = self.sim.world.tick // 30
                self.notify(f"时间推进 {days} 天 → {self.sim.world.date}")
                # 自动存档（每 30 天存一次）
                if prev_chunk != new_chunk:
                    try:
                        self._save(None)
                    except Exception:
                        pass
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
            elif kind == "resolve_event":
                self._resolve_event(int(payload["event_id"]), int(payload["choice_id"]))
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
            elif kind == "set_succession_law":
                self._set_succession_law(payload.get("law"))
            elif kind == "set_crown_authority":
                self._set_crown_authority(int(payload.get("level", 0)))
            elif kind == "set_gender_law":
                self._set_gender_law(payload.get("law"))
            elif kind == "start_scheme":
                self._start_scheme(payload.get("scheme_kind"), int(payload["target_id"]))
            elif kind == "form_alliance":
                self._form_alliance(int(payload["target_id"]))
            elif kind == "form_non_aggression":
                self._form_non_aggression(int(payload["target_id"]))
            elif kind == "arrange_marriage":
                self._arrange_marriage(int(payload["target_id"]))
            elif kind == "send_gift":
                self._send_gift(int(payload["target_id"]), float(payload.get("amount", 50)))
            elif kind == "set_rival":
                self._set_rival(int(payload["target_id"]))
            elif kind == "appoint_council":
                self._appoint_council(payload.get("position"), int(payload.get("character_id", NONE_ID)))
            elif kind == "assign_council_task":
                self._assign_council_task(payload.get("position"), payload.get("task"))
            elif kind == "grant_title":
                self._grant_title(int(payload["title_id"]), int(payload["target_id"]))
            elif kind == "develop_county":
                self._develop_county(int(payload["county_id"]))
            elif kind == "recruit_knights":
                self._recruit_knights()
            elif kind == "set_commander":
                self._set_commander(int(payload["army_id"]), int(payload["character_id"]))
            elif kind == "fabricate_claim":
                self._fabricate_claim(int(payload["county_id"]))
            else:
                self.notify(f"未知操作: {kind}")
        except Exception as e:  # noqa: BLE001 — 返回给前端
            self.notify(f"操作失败: {e}")
        return self._snapshot_unlocked()

    def _name(self, cid: int) -> str:
        c = self.sim.world.character(cid)
        return c.name if c else "?"

    def _player_laws(self) -> Dict[str, Any]:
        w = self.sim.world
        player = w.character(self.player_id)
        if not player or player.primary_title == NONE_ID:
            return {
                "succession": None,
                "crown_authority": None,
                "gender_law": None,
            }
        title = w.title(player.primary_title)
        if not title:
            return {
                "succession": None,
                "crown_authority": None,
                "gender_law": None,
            }
        law = title.realm_law
        return {
            "succession": law.succession.name,
            "crown_authority": law.crown_authority.value,
            "gender_law": law.gender_law.name,
        }

    def _set_succession_law(self, law_name: Any) -> None:
        if law_name is None:
            raise ValueError("缺少 law")
        try:
            new_law = SuccessionLaw[law_name]
        except KeyError:
            raise ValueError(f"未知继承法: {law_name}")
        title = self._player_title()
        title.realm_law.succession = new_law
        self.notify(f"继承法已改为：{new_law.name_zh()}")

    def _set_crown_authority(self, level: int) -> None:
        try:
            ca = CrownAuthority(level)
        except ValueError:
            raise ValueError(f"未知王权等级: {level}")
        title = self._player_title()
        title.realm_law.crown_authority = ca
        self.notify(f"王权已改为：{ca.name_zh()}")

    def _set_gender_law(self, law_name: Any) -> None:
        if law_name is None:
            raise ValueError("缺少 law")
        try:
            new_law = GenderLaw[law_name]
        except KeyError:
            raise ValueError(f"未知性别法: {law_name}")
        title = self._player_title()
        title.realm_law.gender_law = new_law
        self.notify(f"性别法已改为：{new_law.name_zh()}")

    def _player_title(self) -> Any:
        w = self.sim.world
        player = w.character(self.player_id)
        if not player or player.primary_title == NONE_ID:
            raise ValueError("玩家无主头衔")
        title = w.title(player.primary_title)
        if not title:
            raise ValueError("主头衔不存在")
        return title

    # ---------- 阴谋 ----------
    def _start_scheme(self, scheme_kind_name: Any, target_id: int) -> None:
        if scheme_kind_name is None:
            raise ValueError("缺少 scheme_kind")
        try:
            kind = SchemeKind[scheme_kind_name]
        except KeyError:
            raise ValueError(f"未知阴谋类型: {scheme_kind_name}")
        if target_id == self.player_id:
            raise ValueError("不能对自己发起阴谋")
        target = self.sim.world.character(target_id)
        if not target or not target.is_alive():
            raise ValueError("目标无效")
        # 已有针对同一目标的同类阴谋则拒绝
        for s in self.sim.schemes.schemes.values():
            if s.owner == self.player_id and s.target == target_id and not s.exposed and not s.is_complete():
                raise ValueError("已有针对该目标的进行中阴谋")
        sid = self.sim.schemes.start(kind, self.player_id, target_id, self.sim.world.date)
        self.sim.world.push_log(f"{self._name(self.player_id)} 开始策划{kind.name_zh()}（目标：{target.name}）")
        self.notify(f"已发起{kind.name_zh()} → {target.name}（#{sid}）")

    # ---------- 外交 ----------
    def _form_alliance(self, target_id: int) -> None:
        if target_id == self.player_id:
            raise ValueError("不能与自己结盟")
        dip = self.sim.diplomacy
        if dip.are_allied(self.player_id, target_id):
            raise ValueError("已是同盟")
        if dip.flags(self.player_id, target_id).at_war:
            raise ValueError("交战中无法结盟")
        player = self.sim.world.character(self.player_id)
        target = self.sim.world.character(target_id)
        if not player or not target:
            raise ValueError("目标无效")
        # 需要好感达标或已有联姻
        op = self.sim.world.opinion(target_id, self.player_id)
        has_marriage = dip.flags(self.player_id, target_id).marriage_pact
        if op < 30 and not has_marriage:
            raise ValueError(f"好感不足（需 30，当前 {op}）或需先联姻")
        dip.form_alliance(self.player_id, target_id, self.sim.world.date)
        self.sim.world.push_log(f"{player.name} 与 {target.name} 缔结同盟")
        self.notify(f"已与 {target.name} 缔结同盟")

    def _form_non_aggression(self, target_id: int) -> None:
        if target_id == self.player_id:
            raise ValueError("无效目标")
        dip = self.sim.diplomacy
        if dip.flags(self.player_id, target_id).non_aggression:
            raise ValueError("已有互不侵犯条约")
        if dip.flags(self.player_id, target_id).at_war:
            raise ValueError("交战中无法签订")
        target = self.sim.world.character(target_id)
        if not target:
            raise ValueError("目标无效")
        f = dip.flags_mut(self.player_id, target_id)
        f.non_aggression = True
        dip.treaties.append(self._make_treaty(target_id, TreatyKind.NON_AGGRESSION, 20))
        self.sim.world.push_log(f"{self._name(self.player_id)} 与 {target.name} 签订互不侵犯条约")
        self.notify(f"已与 {target.name} 签订互不侵犯条约")

    def _make_treaty(self, target_id: int, kind: TreatyKind, years: int):
        from ck_engine.politics.diplomacy import Treaty
        return Treaty(
            a=self.player_id, b=target_id, kind=kind,
            start=self.sim.world.date, expires_year=self.sim.world.date.year + years,
        )

    def _arrange_marriage(self, target_id: int) -> None:
        w = self.sim.world
        player = w.character(self.player_id)
        target = w.character(target_id)
        if not player or not target:
            raise ValueError("目标无效")
        if not target.is_alive():
            raise ValueError("目标已故")
        if player.gender == target.gender:
            raise ValueError("同性无法成婚")
        if player.is_married():
            raise ValueError("玩家已有配偶")
        if target.is_married():
            raise ValueError("目标已有配偶")
        if not target.is_adult(w.date):
            raise ValueError("目标未成年")
        op = w.opinion(target_id, self.player_id)
        if op < 0:
            raise ValueError(f"对方好感不足（当前 {op}）")
        ok = w.marry(self.player_id, target_id)
        if not ok:
            raise ValueError("婚姻失败")
        # 联姻自动设 marriage_pact
        dip = self.sim.diplomacy
        dip.flags_mut(self.player_id, target_id).marriage_pact = True
        dip.treaties.append(self._make_treaty(target_id, TreatyKind.MARRIAGE_PACT, 50))
        self.notify(f"已与 {target.name} 成婚（联姻协定生效）")

    def _send_gift(self, target_id: int, amount: float) -> None:
        if target_id == self.player_id:
            raise ValueError("不能给自己送礼")
        amount = max(1.0, min(500.0, amount))
        player = self.sim.world.character(self.player_id)
        if not player or player.gold < amount:
            raise ValueError(f"金币不足（需要 {amount:.0f}）")
        target = self.sim.world.character(target_id)
        if not target:
            raise ValueError("目标无效")
        player.add_gold(-amount)
        target.add_gold(amount)
        gain = self.sim.diplomacy.gift_opinion_gain(amount)
        self.sim.world.modify_opinion(target_id, self.player_id, gain)
        self.sim.world.modify_opinion(self.player_id, target_id, gain // 3)
        self.notify(f"向 {target.name} 赠送 {amount:.0f} 金（好感 +{gain}）")

    def _set_rival(self, target_id: int) -> None:
        if target_id == self.player_id:
            raise ValueError("无效目标")
        dip = self.sim.diplomacy
        if dip.flags(self.player_id, target_id).rival:
            raise ValueError("已是宿敌")
        target = self.sim.world.character(target_id)
        if not target:
            raise ValueError("目标无效")
        dip.set_rival(self.player_id, target_id)
        dip.set_rival(target_id, self.player_id)
        self.sim.world.modify_opinion(self.player_id, target_id, -30)
        self.sim.world.modify_opinion(target_id, self.player_id, -30)
        self.sim.world.push_log(f"{self._name(self.player_id)} 视 {target.name} 为宿敌")
        self.notify(f"已将 {target.name} 设为宿敌")

    def _fabricate_claim(self, county_id: int) -> None:
        county = self.sim.world.map.get(county_id)
        if not county:
            raise ValueError("省份不存在")
        if county.holder == self.player_id:
            raise ValueError("已是己方领地")
        player = self.sim.world.character(self.player_id)
        if not player or player.gold < 50:
            raise ValueError("金币不足（需要 50）")
        player.add_gold(-50)
        # 找到该省的头衔
        title_id = county.owner_title
        if title_id == NONE_ID:
            # 无头衔则用省份序号造一个虚拟宣称
            self.sim.diplomacy.add_claim(self.player_id, NONE_ID, county_id, 60)
        else:
            self.sim.diplomacy.add_claim(self.player_id, title_id, county_id, 60)
        self.sim.world.push_log(f"{player.name} 伪造了对 {county.name} 的宣称")
        self.notify(f"已伪造对 {county.name} 的宣称（花费 50 金）")

    # ---------- 内阁 ----------
    def _appoint_council(self, position_name: Any, character_id: int) -> None:
        if position_name is None:
            raise ValueError("缺少 position")
        try:
            pos = CouncilPosition[position_name]
        except KeyError:
            raise ValueError(f"未知职位: {position_name}")
        target = self.sim.world.character(character_id)
        if not target or not target.is_alive():
            raise ValueError("人选无效")
        if not target.is_adult(self.sim.world.date):
            raise ValueError("未成年不能入阁")
        council = self.sim.councils.get_or_create(self.player_id)
        # 如果该角色已在其它职位，先移除
        for p in CouncilPosition.all():
            if council.get(p) == character_id:
                council.set(p, NONE_ID)
        council.set(pos, character_id)
        self.notify(f"任命 {target.name} 为{pos.name_zh()}")

    def _assign_council_task(self, position_name: Any, task_name: Any) -> None:
        if position_name is None or task_name is None:
            raise ValueError("缺少 position 或 task")
        try:
            pos = CouncilPosition[position_name]
            task = CouncilTask[task_name]
        except KeyError as e:
            raise ValueError(f"未知参数: {e}")
        council = self.sim.councils.get_or_create(self.player_id)
        council.tasks[pos] = task
        self.notify(f"{pos.name_zh()} 任务改为：{task.name_zh()}")

    # ---------- 头衔 ----------
    def _grant_title(self, title_id: int, target_id: int) -> None:
        w = self.sim.world
        player = w.character(self.player_id)
        target = w.character(target_id)
        if not player or not target:
            raise ValueError("目标无效")
        title = w.title(title_id)
        if not title:
            raise ValueError("头衔不存在")
        if title.holder != self.player_id:
            raise ValueError("该头衔不属于你")
        if title_id == player.primary_title:
            raise ValueError("不能授予主头衔")
        ok = w.grant_title(title_id, target_id)
        if not ok:
            raise ValueError("授予失败")
        # 授予后目标成为封臣
        if player.primary_title != NONE_ID:
            w.set_vassal(title_id, player.primary_title)
        self.notify(f"将「{title.name}」授予 {target.name}")

    # ---------- 经济与军事 ----------
    def _develop_county(self, county_id: int) -> None:
        county = self.sim.world.map.get(county_id)
        if not county:
            raise ValueError("省份不存在")
        if county.holder != self.player_id:
            raise ValueError("不是己方领地")
        player = self.sim.world.character(self.player_id)
        if not player or player.gold < 10:
            raise ValueError("金币不足（需要 10）")
        cap = county.terrain.development_cap()
        if county.development >= cap:
            raise ValueError(f"已达发展上限（{cap}）")
        player.add_gold(-10)
        county.development = min(cap, county.development + 1)
        self.notify(f"{county.name} 发展度 +1（→ {county.development}）")

    def _recruit_knights(self) -> None:
        player = self.sim.world.character(self.player_id)
        if not player or player.gold < 25:
            raise ValueError("金币不足（需要 25）")
        armies = self.sim.wars.armies_of(self.player_id)
        if not armies:
            raise ValueError("无野战军，请先征召")
        army = armies[0]
        player.add_gold(-25)
        army.add_men(UnitType.HEAVY_CAVALRY, 40)
        army.add_men(UnitType.HEAVY_INFANTRY, 80)
        self.notify(f"招募精锐：重骑兵+40 重步兵+80（{army.name}）")

    def _set_commander(self, army_id: int, character_id: int) -> None:
        army = self.sim.wars.army(army_id)
        if not army or army.owner != self.player_id:
            raise ValueError("无法指挥该军团")
        target = self.sim.world.character(character_id)
        if not target or not target.is_alive():
            raise ValueError("人选无效")
        if not target.is_adult(self.sim.world.date):
            raise ValueError("未成年不能指挥")
        army.commander = character_id
        self.notify(f"任命 {target.name} 为 {army.name} 指挥官")

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

    def _resolve_event(self, event_id: int, choice_id: int) -> None:
        inst = next(
            (e for e in self.sim.events.pending if e.event_id == event_id and e.character == self.player_id),
            None,
        )
        if not inst:
            return
        self.sim.events.resolve_choice(self.sim.world, inst, choice_id)
        self.sim.events.pending = [e for e in self.sim.events.pending if e is not inst]
        self.notify(f"已选择事件选项：{inst.title}")

    def _save_file(self, name: Any = None) -> Path:
        if name is None or str(name).strip() == "":
            return self.save_path
        raw = str(name).strip()
        raw = re.sub(r"[\\/:*?\"<>|]+", "_", raw)
        raw = re.sub(r"\s+", "_", raw)
        safe = Path(raw).name[:48] or "autosave"
        if safe.lower().endswith(".json"):
            safe = safe[:-5]
        return self.save_path.parent / f"{safe}.json"

    def _list_saves(self) -> List[Dict[str, Any]]:
        folder = self.save_path.parent
        if not folder.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            row: Dict[str, Any] = {
                "name": path.stem,
                "file": path.name,
                "mtime": int(path.stat().st_mtime),
                "size": path.stat().st_size,
            }
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                date = data.get("date")
                if isinstance(date, list) and len(date) == 3:
                    row["date"] = f"{date[0]:04d}-{date[1]:02d}-{date[2]:02d}"
                row["player_id"] = data.get("player_id")
            except Exception:
                row["broken"] = True
            rows.append(row)
        return rows

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
