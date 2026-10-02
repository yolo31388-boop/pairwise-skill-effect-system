"""技能效果系统 - 修复版

修复内容:
1. apply_effect: 按效果类型分别处理, 防止非叠加效果重复叠加
2. tick_effects: 检查剩余时间, 使用固定tick间隔(帧率无关)
3. dispel_effect: 执行on_expire回调, 检查效果是否可驱散
4. sort_effects: 按优先级排序, 同优先级按添加顺序(结果可复现)
5. check_immunity: 检查效果强度(等级), 免疫效果不可驱散
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

# 固定tick间隔(秒), 与帧率无关
TICK_INTERVAL = 1.0

# 各类型效果的默认执行优先级(数值越小越先执行)
# 减伤/增益必须先于伤害结算, 否则减伤不生效
TYPE_PRIORITY = {
    "buff": 10,
    "debuff": 20,
    "damage": 30,
    "heal": 40,
    "immunity": 50,
}


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
    level: int = 0                  # 效果强度(等级), 用于免疫判定
    tags: tuple = ()                # 效果标签, 用于免疫匹配
    on_expire: Optional[Callable[[], None]] = None  # 到期/驱散回调


class EffectSystem:
    def __init__(self):
        self.effects: list = []
        self.stats: dict = {"hp": 100, "attack": 10}
        self.max_hp: int = 100
        self._tick_accumulator: float = 0.0
        self._sequence: int = 0  # 添加顺序, 作为同优先级的稳定tiebreaker

    # ---------- bug1: 按类型分别处理 + 防重复叠加 ----------
    def apply_effect(self, effect: Effect) -> bool:
        if effect is None or effect.type not in TYPE_PRIORITY:
            return False
        # 免疫效果不可被驱散
        if effect.type == "immunity":
            effect.dispellable = False
        # 防重复: 同名(同eid)且不可叠加的效果已存在时拒绝再次应用
        if not effect.stackable and any(e.eid == effect.eid for e in self.effects):
            return False

        handler = {
            "damage": self._apply_damage,
            "heal": self._apply_heal,
            "buff": self._apply_buff,
            "debuff": self._apply_debuff,
            "immunity": self._apply_immunity,
        }[effect.type]
        handler(effect)

        # 持续效果(remaining > 0)挂到效果列表上由tick驱动;
        # buff/debuff/immunity始终保留以提供修饰/免疫/排序
        if effect.remaining > 0 or effect.type in ("buff", "debuff", "immunity"):
            effect._seq = self._sequence
            self._sequence += 1
            self.effects.append(effect)
        return True

    def _apply_damage(self, effect: Effect) -> None:
        if effect.remaining <= 0:  # 瞬时伤害立即结算
            self.stats["hp"] = max(0, self.stats["hp"] - effect.value)

    def _apply_heal(self, effect: Effect) -> None:
        if effect.remaining <= 0:  # 瞬时治疗立即结算, 不超过生命上限
            self.stats["hp"] = min(self.max_hp, self.stats["hp"] + effect.value)

    def _apply_buff(self, effect: Effect) -> None:
        self.stats["attack"] = self.stats.get("attack", 0) + effect.value
        effect._stat_mod = ("attack", effect.value)

    def _apply_debuff(self, effect: Effect) -> None:
        self.stats["attack"] = self.stats.get("attack", 0) - effect.value
        effect._stat_mod = ("attack", -effect.value)

    def _apply_immunity(self, effect: Effect) -> None:
        pass  # 免疫仅登记, 由check_immunity查询

    # ---------- bug2: 检查剩余时间 + 固定tick间隔 ----------
    def tick_effects(self, delta: float) -> None:
        if delta <= 0:
            return
        # 固定间隔累积: 高/低帧率下单位时间结算次数一致
        self._tick_accumulator += delta
        while self._tick_accumulator >= TICK_INTERVAL - 1e-9:
            self._tick_accumulator -= TICK_INTERVAL
            self._tick_once()

    def _tick_once(self) -> None:
        expired = []
        for effect in self.sort_effects():
            if effect.remaining <= 0:
                continue  # 已到期/非持续效果不执行
            if effect.type == "damage":
                self.stats["hp"] = max(0, self.stats["hp"] - effect.value)
            elif effect.type == "heal":
                self.stats["hp"] = min(self.max_hp, self.stats["hp"] + effect.value)
            effect.remaining -= TICK_INTERVAL
            if effect.remaining <= 0:
                expired.append(effect)
        for effect in expired:
            self._expire_effect(effect)

    def _expire_effect(self, effect: Effect) -> None:
        """自然到期: 执行on_expire回调并移除效果"""
        if effect.on_expire is not None:
            effect.on_expire()
        self._remove_effect(effect)

    def _remove_effect(self, effect: Effect) -> None:
        stat_mod = getattr(effect, "_stat_mod", None)
        if stat_mod is not None:
            stat, delta = stat_mod
            self.stats[stat] = self.stats.get(stat, 0) - delta
            effect._stat_mod = None
        if effect in self.effects:
            self.effects.remove(effect)

    # ---------- bug3: 驱散执行on_expire + 检查可驱散 ----------
    def dispel_effect(self, eid: str) -> bool:
        target = next((e for e in self.effects if e.eid == eid), None)
        if target is None:
            return False
        if not target.dispellable or target.type == "immunity":
            return False  # 无敌/免疫等不可驱散的效果
        if target.on_expire is not None:
            target.on_expire()
        elif target.type == "damage" and target.remaining > 0:
            # 中毒类持续伤害被驱散时结算剩余伤害
            self.stats["hp"] = max(0, self.stats["hp"] - target.value * target.remaining)
        self._remove_effect(target)
        return True

    # ---------- bug4: 按优先级排序, 同优先级按添加顺序(可复现) ----------
    def sort_effects(self) -> list:
        def key(effect):
            priority = effect.priority
            if priority is None:
                priority = TYPE_PRIORITY.get(effect.type, 100)
            return (priority, getattr(effect, "_seq", 0))

        self.effects.sort(key=key)
        return list(self.effects)

    # ---------- bug5: 免疫检查效果强度, 免疫不可驱散 ----------
    def check_immunity(self, effect: Effect) -> bool:
        for immunity in self.effects:
            if immunity.type != "immunity":
                continue
            # 标签匹配: 免疫的tags与效果的tags有交集, 或免疫针对该效果类型
            matched = bool(set(immunity.tags) & set(effect.tags)) or effect.type in immunity.tags
            # 强度检查: 免疫等级必须不低于效果等级
            if matched and immunity.level >= effect.level:
                return True
        return False
