"""대화 차례 규칙: 두 마음이 같은 조건으로 말을 멈춘다 (SPEC §13)."""

from world.contracts import ConversationView, ResidentId, Utterance


def partner_of(me: ResidentId, conversation: ConversationView) -> ResidentId | None:
    others = [p for p in conversation.participant_ids if p != me]
    return others[0] if others else None


def my_turns(me: ResidentId, conversation: ConversationView) -> tuple[Utterance, ...]:
    return tuple(u for u in conversation.history if u.speaker_id == me)


def should_stop(me: ResidentId, conversation: ConversationView) -> bool:
    """상대가 없거나, 내가 이미 작별했거나, 방금 내가 말했으면 말하지 않는다."""
    if partner_of(me, conversation) is None:
        return True
    mine = my_turns(me, conversation)
    if mine and any(a.kind == "farewell" for a in mine[-1].acts):
        return True
    history = conversation.history
    return bool(history) and history[-1].speaker_id == me


def must_end(me: ResidentId, conversation: ConversationView, max_turns: int) -> bool:
    """이번 말로 작별해야 하면 True: 내 차례 상한에 닿았거나 상대가 작별했다."""
    if len(my_turns(me, conversation)) + 1 >= max_turns:
        return True
    history = conversation.history
    last = history[-1] if history else None
    return (
        last is not None
        and last.speaker_id != me
        and any(a.kind == "farewell" for a in last.acts)
    )
