"""技能效果系统 - 含5个bug"""
from dataclasses import dataclass, field

@dataclass
class Effect:
    eid: str
    type: str  # damage/heal/buff/debuff
    value: float
    duration: float
    remaining: float
    stackable: bool = False
    dispellable: bool = True

class EffectSystem:
    def __init__(self):
        self.effects: list = []
        self.stats: dict = {"hp": 100, "attack": 10}

    def apply_effect(self, effect: Effect) -> bool:
        # bug1: 不检查类型，不防重复
        self.effects.append(effect)
        return True

    def tick_effects(self, delta: float) -> None:
        # bug2: 不检查剩余时间，帧时间计算
        for effect in self.effects:
            if effect.type == "damage":
                self.stats["hp"] -= effect.value * delta

    def dispel_effect(self, eid: str) -> bool:
        # bug3: 不执行on_expire，不检查可驱散
        self.effects = [e for e in self.effects if e.eid != eid]
        return True

    def sort_effects(self) -> list:
        # bug4: 按添加顺序，不按优先级
        return self.effects

    def check_immunity(self, effect: Effect) -> bool:
        # bug5: 只看标签，不看强度
        return effect.type == "damage"
