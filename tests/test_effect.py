"""技能效果系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skill.effect_system import EffectSystem, Effect

class TestEffectType:
    def test_heal_not_treated_as_damage(self):
        es = EffectSystem()
        es.stats["hp"] = 50
        es.apply_effect(Effect("h1", "heal", 20, 0, 0))
        assert es.stats["hp"] == 70

class TestEffectExpiry:
    def test_expired_effect_not_ticked(self):
        es = EffectSystem()
        es.effects.append(Effect("d1", "damage", 10, 0, 0))
        es.tick_effects(1.0)
        assert es.stats["hp"] == 100

class TestDispelCallback:
    def test_dispel_executes_on_expire(self):
        es = EffectSystem()
        es.effects.append(Effect("d1", "damage", 10, 5, 5))
        es.dispel_effect("d1")
        assert len(es.effects) == 0

class TestEffectPriority:
    def test_damage_reduction_before_damage(self):
        es = EffectSystem()
        es.effects.append(Effect("dmg", "damage", 10, 0, 0))
        es.effects.append(Effect("def", "buff", 0, 0, 0))
        sorted_e = es.sort_effects()
        assert sorted_e[0].type == "buff"

class TestImmunityStrength:
    def test_weak_immunity_not_block_strong(self):
        es = EffectSystem()
        effect = Effect("d1", "damage", 100, 0, 0)
        assert es.check_immunity(effect) == False
