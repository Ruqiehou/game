from __future__ import annotations

from dataclasses import dataclass

from ck_engine.world.world_state import World


@dataclass
class PersonalityProfile:
    aggression: float = 0.5
    greed: float = 0.5
    honor: float = 0.5
    zeal: float = 0.5
    boldness: float = 0.5
    compassion: float = 0.5
    sociability: float = 0.5
    vengeance: float = 0.5

    def warlike_score(self) -> float:
        return max(
            0.0,
            min(
                1.5,
                self.aggression * 0.4
                + self.boldness * 0.3
                + self.vengeance * 0.2
                - self.compassion * 0.1,
            ),
        )

    def intrigue_score(self) -> float:
        return max(
            0.0,
            min(1.5, (1.0 - self.honor) * 0.5 + self.greed * 0.2 + self.vengeance * 0.3),
        )

    def diplomat_score(self) -> float:
        return max(
            0.0,
            min(1.5, self.compassion * 0.3 + self.sociability * 0.4 + self.honor * 0.3),
        )


class AiPersonality:
    @staticmethod
    def profile_of(world: World, who: int) -> PersonalityProfile:
        p = PersonalityProfile()
        c = world.character(who)
        if not c:
            return p
        for tid in c.traits:
            if tid == 1:
                p.boldness += 0.3
                p.aggression += 0.1
            elif tid == 2:
                p.honor -= 0.25
                p.greed += 0.1
                p.vengeance += 0.1
            elif tid == 3:
                p.honor += 0.3
                p.compassion += 0.15
            elif tid == 4:
                p.greed += 0.4
                p.compassion -= 0.1
            elif tid == 5:
                p.compassion += 0.25
                p.greed -= 0.15
                p.sociability += 0.15
            elif tid == 6:
                p.aggression += 0.2
                p.boldness += 0.25
            elif tid == 7:
                p.boldness -= 0.2
                p.aggression -= 0.1
            elif tid == 8:
                p.zeal += 0.15
                p.sociability += 0.1
                p.aggression -= 0.05
            elif tid == 9:
                p.aggression += 0.3
                p.greed += 0.2
                p.boldness += 0.2
                p.vengeance += 0.1
            elif tid == 10:
                p.honor += 0.35
                p.aggression -= 0.2
                p.sociability += 0.1
            elif tid == 11:
                p.compassion -= 0.3
                p.vengeance += 0.3
                p.aggression += 0.15
            elif tid == 12:
                p.sociability += 0.35
                p.compassion += 0.1
        attrs = world.effective_attrs(who)
        if attrs:
            p.aggression += (attrs.martial - 8) * 0.03
            p.greed += (attrs.stewardship - 8) * 0.02
            p.zeal += (attrs.learning - 8) * 0.02
            p.sociability += (attrs.diplomacy - 8) * 0.03
            p.vengeance += (attrs.intrigue - 8) * 0.02
            p.boldness -= (c.stress / 400.0) * 0.2
            p.compassion -= (c.stress / 400.0) * 0.1
        age = c.age_at(world.date)
        if age < 25:
            p.boldness += 0.1
            p.aggression += 0.05
        elif age > 55:
            p.boldness -= 0.1
            p.aggression -= 0.05
            p.honor += 0.05
        for k in (
            "aggression",
            "greed",
            "honor",
            "zeal",
            "boldness",
            "compassion",
            "sociability",
            "vengeance",
        ):
            setattr(p, k, max(0.0, min(1.5, getattr(p, k))))
        return p

    @staticmethod
    def describe(p: PersonalityProfile) -> str:
        if p.warlike_score() > 0.8:
            return "好战"
        if p.intrigue_score() > 0.8:
            return "阴险"
        if p.diplomat_score() > 0.8:
            return "圆滑"
        if p.greed > 0.9:
            return "贪婪"
        if p.zeal > 0.9:
            return "虔诚"
        return "务实"
