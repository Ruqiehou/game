"""关键路径单测：白和、补给、占领封臣链、派系安抚、存档。"""

from __future__ import annotations

import unittest

from ck_engine.core import GameDate, Season
from ck_engine.game.simulation import GameSimulation
from ck_engine.military.army import Army, ArmyStatus, UnitType
from ck_engine.military.battle import BattleSimulator
from ck_engine.military.war import WarResult
from ck_engine.politics.diplomacy import CasusBelli
from ck_engine.politics.factions import FactionKind
from ck_engine.ui.api import GameAPI
from ck_engine.world.title import TitleTier


class TestWhitePeace(unittest.TestCase):
    def test_auto_white_peace_after_stalemate(self):
        s = GameSimulation()
        rulers = list(s.world.rulers())
        a, b = rulers[0].id, rulers[1].id
        wid = s.wars.declare_war(CasusBelli.CONQUEST, a, b, s.world.date, "t")
        w = s.wars.war(wid)
        assert w is not None
        w.warscore = 5
        w.start = GameDate(1064, 1, 1)
        s.world.date = GameDate(1066, 1, 1)
        s.diplomacy.war_exhaustion[a] = 45
        s.diplomacy.war_exhaustion[b] = 45
        s.tick_wars()
        w = s.wars.war(wid)
        assert w is not None
        self.assertFalse(w.active)
        self.assertEqual(w.result, WarResult.WHITE_PEACE)


class TestSupplyAndSeason(unittest.TestCase):
    def test_enemy_territory_drains_supply(self):
        s = GameSimulation()
        rulers = list(s.world.rulers())
        owner = rulers[0].id
        enemy = rulers[1].id
        enemy_county = next(c for c in s.world.map.iter() if c.holder == enemy)
        aid = s.wars.raise_army(owner, enemy_county.id, 1000, "raid")
        army = s.wars.army(aid)
        assert army is not None
        army.supply = 50.0
        # 标记交战，使敌境生效
        s.diplomacy.set_at_war(owner, enemy, True)
        from ck_engine.politics.diplomacy import CasusBelli

        s.wars.declare_war(CasusBelli.CONQUEST, owner, enemy, s.world.date, "x")
        s._tick_army_supply(winter=False)
        self.assertLess(army.supply, 50.0)

    def test_friendly_supply_recovers(self):
        s = GameSimulation()
        r = list(s.world.rulers())[0]
        home = next(c for c in s.world.map.iter() if c.holder == r.id)
        aid = s.wars.raise_army(r.id, home.id, 500, "home")
        army = s.wars.army(aid)
        assert army is not None
        army.supply = 40.0
        s._tick_army_supply(winter=False)
        self.assertGreater(army.supply, 40.0)

    def test_winter_slows_move(self):
        army = Army(id=1, owner=1, name="t", location=1)
        army.add_men(UnitType.LEVIES, 100)
        army.set_path([2, 3])
        # 强制 0 概率，应停滞
        self.assertIsNone(army.advance_move(move_chance=0.0, rng=__import__("random").Random(0)))
        self.assertEqual(army.location, 1)
        self.assertEqual(len(army.path), 2)

    def test_battle_season_mod_accepted(self):
        a = Army(id=1, owner=1, name="a", location=1)
        b = Army(id=2, owner=2, name="b", location=1)
        a.add_men(UnitType.LEVIES, 1000)
        b.add_men(UnitType.LEVIES, 1000)
        rng = __import__("random").Random(42)
        r = BattleSimulator.resolve(a, b, 10, 10, 1.0, rng=rng, season_mod=0.8)
        self.assertIsInstance(r.attacker_won, bool)


class TestOccupyVassalLink(unittest.TestCase):
    def test_occupy_sets_holder_and_liege(self):
        s = GameSimulation()
        conqueror = list(s.world.rulers())[0]
        foreign = next(c for c in s.world.map.iter() if c.holder != conqueror.id)
        tid = foreign.owner_title
        s.world.occupy_county(foreign.id, conqueror.id)
        t = s.world.title(tid)
        assert t is not None
        self.assertEqual(t.holder, conqueror.id)
        self.assertEqual(foreign.holder, conqueror.id)
        primary = s.world.title(conqueror.primary_title)
        if primary and primary.tier > TitleTier.COUNTY:
            self.assertEqual(t.de_facto_liege, primary.id)


class TestFactionAppease(unittest.TestCase):
    def test_appease_lowers_or_dissolves(self):
        s = GameSimulation()
        r = list(s.world.rulers())[0]
        fid = s.factions.create(FactionKind.LIBERTY, r.id)
        s.factions.join(fid, 999)
        f = s.factions.factions[fid]
        f.discontent = 40
        f.power = 20
        s.factions.appease(fid, 40)
        self.assertNotIn(fid, s.factions.factions)


class TestBankruptcy(unittest.TestCase):
    def test_disband_when_broke(self):
        s = GameSimulation()
        r = list(s.world.rulers())[0]
        loc = next(c for c in s.world.map.iter() if c.holder == r.id)
        aid = s.wars.raise_army(r.id, loc.id, 5000, "big")
        r.gold = 0
        s.tick_month()
        army = s.wars.army(aid)
        assert army is not None
        self.assertEqual(army.status, ArmyStatus.DISBANDED)


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip(self):
        api = GameAPI()
        api.sim.run_days(60)
        before = str(api.sim.world.date)
        api._save()
        api._load()
        self.assertEqual(str(api.sim.world.date), before)


class TestSeasonHelper(unittest.TestCase):
    def test_winter_month(self):
        self.assertEqual(GameDate(1066, 12, 1).season(), Season.WINTER)
        self.assertEqual(GameDate(1066, 6, 1).season(), Season.SUMMER)


class TestScenarioJson(unittest.TestCase):
    def test_load_1066(self):
        from ck_engine.game.scenario import Scenario1066

        w = Scenario1066.build()
        self.assertEqual(str(w.date), "1066-01-01")
        self.assertEqual(sum(1 for _ in w.map.iter()), 14)
        self.assertGreaterEqual(len(list(w.rulers())), 4)
        names = {r.name for r in w.rulers()}
        self.assertIn("哈罗德·戈德温森", names)
        self.assertIn("威廉·征服者", names)


if __name__ == "__main__":
    unittest.main()
