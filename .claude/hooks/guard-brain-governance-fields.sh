#!/bin/bash
# ============================================================
# PreToolUse 가드: packages/backend/src/agents/brain/ 이하 파일에
# governance/diagnostics 필드(raw_response, parse_error, model_thought 등)를
# 직접 추가하는 것을 사전 차단한다. (AGENTS.md §9)
#
# Edit/Write 도구 호출의 대상 파일이 brain/ 경로이고, 새로 쓰이는 내용에
# 금지 필드명이 등장하면 차단한다. false positive 가능성이 있으므로 deny가
# 아니라 확인을 요구하는 ask로 응답한다.
# ============================================================
set -uo pipefail

INPUT="$(cat)"

allow() {
  echo '{"continue": true}'
  exit 0
}

TOOL_NAME=$(echo "$INPUT" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')

case "$TOOL_NAME" in
  Edit|Write|MultiEdit) ;;
  *) allow ;;
esac

FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')

case "$FILE_PATH" in
  */agents/brain/*) ;;
  *) allow ;;
esac

FORBIDDEN_PATTERN='raw_response|parse_error|model_thought|self_critique|decision_process|action_summary|retry_count|suppress_reason|fallback_reason'

if echo "$INPUT" | grep -Eq "$FORBIDDEN_PATTERN"; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "AGENTS.md §9: governance/diagnostics 필드로 보이는 이름이 agents/brain/ 파일에 쓰이고 있습니다 (raw_response/parse_error/model_thought 등). Brain 결과 객체가 아니라 llm/governance, llm/guardrails, 또는 diagnostics 모듈에 속하는지 확인하세요. 의도된 것이면 진행하세요."
  }
}
EOF
  exit 0
fi

allow
