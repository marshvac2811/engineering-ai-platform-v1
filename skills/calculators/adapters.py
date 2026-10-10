"""Adapter classes for the governed calculator catalogue, one per skill (bound via implementation_bindings)."""
from skills.calculators.catalogue import CALCULATORS, make_skill_class

for _c in CALCULATORS:
    globals()[_c.class_name] = make_skill_class(_c)

__all__ = [c.class_name for c in CALCULATORS]
