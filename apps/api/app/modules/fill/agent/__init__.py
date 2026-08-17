"""Internal 2.2 agent pipeline submodule.

Not exposed via port.py — only used inside FillService.fill().

Components (IMPLEMENTATION_PLAN.md §三):
- grouper:  FieldGrouper  (按 row_group_id + field_type 分组)
- planner:  QueryPlanner + CSF 置信度合成 (创新点 1/4)
- runner:   LLMClient + type-aware Prompt 模板 (创新点 2/3)
"""
