"""시나리오 지표 수집: 행사 확산·약속·참석 (SPEC §16).

약속은 행사가 끝나면 할 일 목록에서 빠지므로 틱마다 표본을 모은다.
"""

import datetime
from collections.abc import Mapping, Sequence

from minds.social import HasSocialState
from world.contracts import LOCATION_SEPARATOR, MindKind, ResidentId, SocialEvent
from world.residents import Resident

from .contracts import ScenarioReport

BUILDING_DEPTH = 2
"""위치 경로 `Town > Building`까지 같으면 행사 건물 안으로 본다."""


class ScenarioTracker:
    """틱마다 `sample`을 불러 행사를 아는·가기로 한·참석한 주민을 모은다."""

    def __init__(self, event: SocialEvent) -> None:
        self.event = event
        parts = event.location_path.split(LOCATION_SEPARATOR)
        self._building = LOCATION_SEPARATOR.join(parts[:BUILDING_DEPTH])
        self.knew: set[ResidentId] = set()
        self.committed: set[ResidentId] = set()
        self.present: set[ResidentId] = set()

    def sample(self, residents: Sequence[Resident], now: datetime.datetime) -> None:
        for resident in residents:
            rid = resident.resident_id
            mind = resident.mind
            if isinstance(mind, HasSocialState):
                if mind.social.facts.get(self.event.name) is not None:
                    self.knew.add(rid)
                if mind.social.agenda.is_committed(self.event):
                    self.committed.add(rid)
            if self.event.start_time <= now < self.event.end_time:
                where = resident.body.state.location_path
                if where == self._building or where.startswith(
                    self._building + LOCATION_SEPARATOR
                ):
                    self.present.add(rid)

    def report(
        self,
        *,
        scenario: str,
        residents: Sequence[Resident],
        mind_calls: Mapping[MindKind, int],
    ) -> ScenarioReport:
        host = {self.event.host_id or ""}
        return ScenarioReport(
            scenario=scenario,
            event=self.event.name,
            resident_count=len(residents),
            agent_ids=tuple(r.resident_id for r in residents if r.config.mind == "llm"),
            knew_event=tuple(sorted(self.knew - host)),
            committed=tuple(sorted(self.committed - host)),
            attended=tuple(sorted((self.present & self.committed) - host)),
            present=tuple(sorted(self.present - host)),
            mind_calls={str(kind): count for kind, count in mind_calls.items()},
        )
