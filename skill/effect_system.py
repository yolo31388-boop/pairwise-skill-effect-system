"""技能效果系统"""
from dataclasses import dataclass
from typing import Callable, Optional

VALID_TYPES = ("damage", "heal", "buff", "debuff", "immunity")

# 类型默认优先级，数值小的先执行（减伤buff先于伤害结算）
TYPE_PRIORITY = {"buff": 0, "immunity": 0, "debuff": 1, "heal": 2, "damage": 3}

TICK_INTERVAL = 1.0  # 固定tick间隔，与帧率无关


@dataclass
class Effect:
    eid: str
    type: str  # damage/heal/buff/debuff/immunity
    value: float
    duration: float
    remaining: float
    stackable: bool = False
    dispellable: bool = True
    priority: Optional[int] = None  # None时使用类型默认优先级
    level: int = 1  # 效果强度等级，用于免疫判定
    tag: str = ""  # immunity效果标记其免疫的效果类型
    on_expire: Optional[Callable[["Effect"], None]] = None


class EffectSystem:
    def __init__(self):
        self.effects: list = []
        self.stats: dict = {"hp": 100, "attack": 10}
        self._tick_accumulator: float = 0.0

    def apply_effect(self, effect: Effect) -> bool:
        # 检查效果类型是否合法
        if effect.type not in VALID_TYPES:
            return False
        # 非叠加效果不允许同名重复
        if not effect.stackable and any(e.eid == effect.eid for e in self.effects):
            return False
        # 即时效果按类型分别处理，持续效果入列表由tick结算
        if effect.remaining <= 0 and effect.duration <= 0:
            if effect.type == "damage":
                self._apply_damage(effect)
            elif effect.type == "heal":
                self._apply_heal(effect)
            else:
                self.effects.append(effect)
            return True
        self.effects.append(effect)
        return True

    def _apply_damage(self, effect: Effect) -> None:
        self.stats["hp"] -= effect.value

    def _apply_heal(self, effect: Effect) -> None:
        self.stats["hp"] += effect.value

    def tick_effects(self, delta: float) -> None:
        # 固定间隔tick：累积帧时间，凑满一个间隔才结算，保证不同帧率强度一致
        self._tick_accumulator += delta
        while self._tick_accumulator >= TICK_INTERVAL:
            self._tick_accumulator -= TICK_INTERVAL
            self._process_tick()

    def _process_tick(self) -> None:
        for effect in self.sort_effects():
            # 只结算剩余时间大于0的效果
            if effect.remaining <= 0:
                continue
            if effect.type == "damage":
                self._apply_damage(effect)
            elif effect.type == "heal":
                self._apply_heal(effect)
            effect.remaining -= TICK_INTERVAL
        # 结算到期效果并执行on_expire回调
        expired = [e for e in self.effects if e.remaining <= 0 and e.duration > 0]
        for effect in expired:
            if effect.on_expire:
                effect.on_expire(effect)
            self.effects.remove(effect)

    def dispel_effect(self, eid: str) -> bool:
        for effect in self.effects:
            if effect.eid == eid:
                # 免疫效果与不可驱散效果不能被驱散
                if effect.type == "immunity" or not effect.dispellable:
                    return False
                # 驱散时执行on_expire回调（如中毒结算剩余伤害）
                if effect.on_expire:
                    effect.on_expire(effect)
                self.effects.remove(effect)
                return True
        return False

    def sort_effects(self) -> list:
        # 按优先级排序（显式priority优先，否则用类型默认）；
        # sorted稳定，同优先级保持添加顺序，结果可复现
        return sorted(
            self.effects,
            key=lambda e: e.priority if e.priority is not None else TYPE_PRIORITY[e.type],
        )

    def check_immunity(self, effect: Effect) -> bool:
        # 免疫需匹配效果类型且免疫等级不低于效果等级
        for e in self.effects:
            if e.type != "immunity":
                continue
            if e.tag and e.tag != effect.type:
                continue
            if e.level >= effect.level:
                return True
        return False
