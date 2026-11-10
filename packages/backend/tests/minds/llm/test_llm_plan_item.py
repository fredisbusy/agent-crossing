import asyncio

from llm_fakes import DAY, HOME, ScriptedClient, ctx, make_mind

MORNING = DAY.replace(hour=10)


def test_plan_item_is_none_before_plan_then_describes_current_slot() -> None:
    mind, _ = make_mind(ScriptedClient(lambda _: {}))
    assert mind.plan_item_at(MORNING) is None
    asyncio.run(mind.next_action(ctx("isabella", MORNING, where=HOME)))
    item = mind.plan_item_at(MORNING)
    assert item
    assert item == mind.social.agenda.slot_at(MORNING).description
