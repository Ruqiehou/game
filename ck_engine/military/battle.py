from __future__ import annotations

import random
from dataclasses import dataclass

from ck_engine.military.army import Army, ArmyStatus


@dataclass
class BattleResult:
    attacker_won: bool
    attacker_losses: int
    defender_losses: int
    warscore_change: int
    description: str


class BattleSimulator:
    @staticmethod
    def resolve(
        attacker: Army,
        defender: Army,
        atk_martial: int,
        def_martial: int,
        terrain_width: float,
        rng: random.Random | None = None,
        season_mod: float = 1.0,
    ) -> BattleResult:
        rng = rng or random.Random()
        atk_pow = attacker.combat_power() * (1.0 + (atk_martial - 8) * 0.04)
        def_pow = defender.combat_power() * (1.0 + (def_martial - 8) * 0.04)
        # 季节修正：冬季/秋季略降总体战力，冬季防守方略优
        season_mod = max(0.7, min(1.15, season_mod))
        atk_pow *= season_mod
        def_pow *= season_mod * (1.05 if season_mod < 0.95 else 1.0)
        # 地形压缩优势
        ratio = (atk_pow + 1.0) / (def_pow + 1.0)
        ratio = ratio ** terrain_width
        noise = rng.uniform(0.85, 1.15)
        score = ratio * noise

        attacker_won = score >= 1.0
        loss_scale = 1.15 if season_mod < 0.95 else 1.0  # 恶劣季节伤亡更高
        base_loss_a = int(attacker.total_men() * rng.uniform(0.08, 0.22) * loss_scale)
        base_loss_d = int(defender.total_men() * rng.uniform(0.08, 0.22) * loss_scale)
        if attacker_won:
            base_loss_d = int(base_loss_d * 1.6)
            base_loss_a = int(base_loss_a * 0.7)
        else:
            base_loss_a = int(base_loss_a * 1.6)
            base_loss_d = int(base_loss_d * 0.7)

        def apply_losses(army: Army, total: int) -> int:
            remaining = total
            killed = 0
            for s in army.stacks:
                if remaining <= 0:
                    break
                share = max(1, int(total * (s.men / max(1, army.total_men()))))
                k = s.take_casualties(min(share, remaining))
                killed += k
                remaining -= k
            army.morale = max(10.0, army.morale - 15.0)
            return killed

        a_loss = apply_losses(attacker, base_loss_a)
        d_loss = apply_losses(defender, base_loss_d)
        attacker.status = ArmyStatus.IDLE
        defender.status = ArmyStatus.IDLE
        warscore = int(max(5, min(40, abs(score - 1.0) * 40 + 10)))
        if not attacker_won:
            warscore = -warscore
        desc = (
            f"{'进攻方' if attacker_won else '防守方'}胜利 "
            f"(损 {a_loss}/{d_loss}，比分 {score:.2f})"
        )
        return BattleResult(
            attacker_won=attacker_won,
            attacker_losses=a_loss,
            defender_losses=d_loss,
            warscore_change=warscore,
            description=desc,
        )
