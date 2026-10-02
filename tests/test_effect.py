"""技能效果系统 - 测试"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skill.effect_system import EffectSystem, Effect


class TestEffectType:
    def test_heal_not_treated_as_damage(self):
        es = EffectSystem()
        es.stats["hp"] = 50
        es.apply_effect(Effect("h1", "heal", 20, 0, 0))
        assert es.stats["hp"] == 70

    def test_invalid_type_rejected(self):
        es = EffectSystem()
        assert es.apply_effect(Effect("x1", "garbage", 10, 0, 0)) is False
        assert len(es.effects) == 0

    def test_duplicate_effect_not_stacked(self):
        es = EffectSystem()
        assert es.apply_effect(Effect("atk", "buff", 100, 5, 5)) is True
        assert es.apply_effect(Effect("atk", "buff", 100, 5, 5)) is False
        assert len(es.effects) == 1


class TestEffectExpiry:
    def test_expired_effect_not_ticked(self):
        es = EffectSystem()
        es.effects.append(Effect("d1", "damage", 10, 0, 0))
        es.tick_effects(1.0)
        assert es.stats["hp"] == 100

    def test_dot_removed_after_expiry(self):
        es = EffectSystem()
        es.apply_effect(Effect("poison", "damage", 10, 1, 1))
        es.tick_effects(1.0)
        assert es.stats["hp"] == 90
        assert len(es.effects) == 0

    def test_fixed_tick_interval_framerate_independent(self):
        def run(frames):
            es = EffectSystem()
            es.apply_effect(Effect("poison", "damage", 10, 3, 3))
            for dt in frames:
                es.tick_effects(dt)
            return es.stats["hp"]
        assert run([1.0]) == run([0.5, 0.5])
        assert run([1.0]) == run([0.2, 0.2, 0.2, 0.2, 0.2])

    def test_expire_callback_on_natural_expiry(self):
        es = EffectSystem()
        called = []
        es.effects.append(Effect("d1", "damage", 10, 1, 1,
                                on_expire=lambda e: called.append(e.eid)))
        es.tick_effects(1.0)
        assert called == ["d1"]


class TestDispelCallback:
    def test_dispel_executes_on_expire(self):
        es = EffectSystem()
        called = []
        es.effects.append(Effect("d1", "damage", 10, 5, 5,
                                on_expire=lambda e: called.append(e.eid)))
        assert es.dispel_effect("d1") is True
        assert len(es.effects) == 0
        assert called == ["d1"]

    def test_undispellable_effect_not_dispelled(self):
        es = EffectSystem()
        es.effects.append(Effect("inv", "buff", 0, 5, 5, dispellable=False))
        assert es.dispel_effect("inv") is False
        assert len(es.effects) == 1

    def test_immunity_effect_not_dispellable(self):
        es = EffectSystem()
        es.effects.append(Effect("imm", "immunity", 0, 5, 5, tag="damage"))
        assert es.dispel_effect("imm") is False
        assert len(es.effects) == 1


class TestEffectPriority:
    def test_damage_reduction_before_damage(self):
        es = EffectSystem()
        es.effects.append(Effect("dmg", "damage", 10, 0, 0))
        es.effects.append(Effect("def", "buff", 0, 0, 0))
        sorted_e = es.sort_effects()
        assert sorted_e[0].type == "buff"

    def test_same_priority_order_deterministic(self):
        es = EffectSystem()
        es.effects.append(Effect("b1", "buff", 1, 5, 5))
        es.effects.append(Effect("b2", "buff", 2, 5, 5))
        first = [e.eid for e in es.sort_effects()]
        second = [e.eid for e in es.sort_effects()]
        assert first == second == ["b1", "b2"]


class TestImmunityStrength:
    def test_weak_immunity_not_block_strong(self):
        es = EffectSystem()
        effect = Effect("d1", "damage", 100, 0, 0)
        assert es.check_immunity(effect) is False

    def test_immunity_compares_levels(self):
        es = EffectSystem()
        es.effects.append(Effect("imm", "immunity", 0, 10, 10,
                                 tag="damage", level=1))
        assert es.check_immunity(Effect("p10", "damage", 50, 0, 0, level=10)) is False

        es2 = EffectSystem()
        es2.effects.append(Effect("imm", "immunity", 0, 10, 10,
                                  tag="damage", level=10))
        assert es2.check_immunity(Effect("p1", "damage", 5, 0, 0, level=1)) is True
