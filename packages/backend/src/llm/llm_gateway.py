import datetime
import json
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel

from agents.memory.memory_object import MemoryObject
from agents.planning.graph import PlanningGraphRunner
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
from agents.reaction import (
    GenerateClient,
    ReactionDecision,
    ReactionDecisionInput,
)
from agents.reaction.graph import ReactionGraphRunner
from llm.clients.types import JsonObject, LlmGenerateOptions
from llm.guardrails.similarity import EmbeddingEncoder

from . import prompt_builders
from .language_policy import contains_korean_text
from .structured_outputs import (
    InsightsOutput,
    SalientQuestionsOutput,
)

SALIENT_QUESTIONS_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=256,
)

INSIGHTS_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=768,
)

DAY_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=1024,
)

HOURLY_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=1024,
)

MINUTE_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=3072,
)


@dataclass(frozen=True)
class InsightWithCitation:
    context: str
    citation_memory_ids: list[int]


class LlmGateway:
    def __init__(
        self,
        generation_client: GenerateClient,
        *,
        embedding_encoder: EmbeddingEncoder | None = None,
    ):
        self.generation_client: GenerateClient = generation_client
        self.embedding_encoder: EmbeddingEncoder | None = embedding_encoder
        self.reaction_graph: ReactionGraphRunner = ReactionGraphRunner(
            generation_client=generation_client,
            embedding_encoder=embedding_encoder,
        )
        self.planning_graph: PlanningGraphRunner = PlanningGraphRunner(
            planning_client=self
        )

    def generate_salient_high_level_questions(
        self, agent_name: str, memories: list[MemoryObject]
    ) -> list[str]:
        if not memories:
            return []

        prompt = prompt_builders.build_salient_questions_prompt(
            agent_name=agent_name,
            memories=memories,
        )
        response_text = self.generation_client.generate(
            prompt=prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=SALIENT_QUESTIONS_GENERATE_OPTIONS,
            response_model=SalientQuestionsOutput,
        )

        try:
            parsed_data = cast(object, json.loads(response_text))
            if not isinstance(parsed_data, dict):
                return []

            parsed_payload = cast(JsonObject, parsed_data)
            questions = parsed_payload.get("questions", [])
            if not isinstance(questions, list):
                return []

            parsed_questions: list[str] = []
            for question in cast(list[object], questions):
                if (
                    isinstance(question, str)
                    and question.strip()
                    and contains_korean_text(question)
                ):
                    parsed_questions.append(question)

            return parsed_questions
        except json.JSONDecodeError:
            return []

    def generate_insights_with_citation_key(
        self, agent_name: str, memories: list[MemoryObject]
    ) -> list[InsightWithCitation]:
        if not memories:
            return []

        statement_to_memory_id = {
            index + 1: memory.id for index, memory in enumerate(memories)
        }
        prompt = prompt_builders.build_insights_with_citation_prompt(
            agent_name=agent_name,
            memories=memories,
        )
        response_text = self.generation_client.generate(
            prompt=prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=INSIGHTS_GENERATE_OPTIONS,
            response_model=InsightsOutput,
        )

        try:
            parsed_data = cast(object, json.loads(response_text))
            if not isinstance(parsed_data, dict):
                return []

            parsed_payload = cast(JsonObject, parsed_data)
            insights = parsed_payload.get("insights", [])
            if not isinstance(insights, list):
                return []

            parsed_insights: list[InsightWithCitation] = []
            for raw_insight in cast(list[object], insights):
                if not isinstance(raw_insight, dict):
                    continue

                insight_payload = cast(JsonObject, raw_insight)
                insight_text = insight_payload.get("insight")
                citation_numbers = insight_payload.get("citation_statement_numbers")
                if (
                    not isinstance(insight_text, str)
                    or not insight_text.strip()
                    or not contains_korean_text(insight_text)
                ):
                    continue

                citation_memory_ids: list[int] = []
                if isinstance(citation_numbers, list):
                    for raw_number in cast(list[object], citation_numbers):
                        if not isinstance(raw_number, int):
                            continue

                        citation_memory_id = statement_to_memory_id.get(raw_number)
                        if citation_memory_id is not None:
                            citation_memory_ids.append(citation_memory_id)

                parsed_insights.append(
                    InsightWithCitation(
                        context=insight_text.strip(),
                        citation_memory_ids=citation_memory_ids,
                    )
                )

            return parsed_insights
        except json.JSONDecodeError:
            return []

    def generate_day_plan(
        self,
        *,
        agent_name: str,
        age: int,
        innate_traits: list[str],
        persona_background: str,
        yesterday_date: datetime.datetime,
        yesterday_summary: str,
        today_date: datetime.datetime,
    ) -> list[DayPlanItem]:
        return self.planning_graph.generate_day_plan(
            DayPlanBroadStrokesRequest(
                agent_name=agent_name,
                age=age,
                innate_traits=innate_traits,
                persona_background=persona_background,
                yesterday_date=yesterday_date,
                yesterday_summary=yesterday_summary,
                today_date=today_date,
            )
        )

    def generate_hour_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]:
        return self.planning_graph.generate_hourly_plan(
            agent_name=agent_name,
            current_time=current_time,
            day_plan_item=day_plan_item,
        )

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]:
        return self.planning_graph.generate_minute_plan(
            agent_name=agent_name,
            current_time=current_time,
            hourly_plan_item=hourly_plan_item,
        )

    def complete_planning_prompt(
        self,
        *,
        prompt: str,
        options: LlmGenerateOptions,
        response_model: type[BaseModel],
    ) -> str:
        return self.generation_client.generate(
            prompt=prompt,
            system=prompt_builders.language_system_prompt("ko"),
            response_model=response_model,
            options=options,
        )

    def decide_reaction(
        self,
        input: ReactionDecisionInput,
    ) -> ReactionDecision:
        return self.reaction_graph.decide_reaction(input)
