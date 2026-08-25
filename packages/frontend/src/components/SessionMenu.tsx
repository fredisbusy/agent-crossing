import type {
  GameSessionList,
  GameSessionSummary,
} from "@agent-crossing/shared";
import {
  FolderOpen,
  Gamepad2,
  Loader2,
  Plus,
  Save,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

type SessionAction = "loading" | "creating" | "saving" | "loading-session" | null;

function isSessionSummary(value: unknown): value is GameSessionSummary {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.id === "string" &&
    typeof record.name === "string" &&
    ["ACTIVE", "SAVED", "ERROR"].includes(String(record.status)) &&
    typeof record.map_id === "string" &&
    typeof record.world_time === "string" &&
    typeof record.turn === "number" &&
    typeof record.revision === "number" &&
    typeof record.save_version === "number" &&
    typeof record.created_at === "string" &&
    typeof record.saved_at === "string"
  );
}

function parseSessionList(value: unknown): GameSessionList | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  if (
    (record.current_session_id !== null &&
      typeof record.current_session_id !== "string") ||
    !Array.isArray(record.sessions) ||
    !record.sessions.every(isSessionSummary)
  ) {
    return null;
  }
  return {
    current_session_id: record.current_session_id as string | null,
    sessions: record.sessions,
  };
}

async function sessionRequest(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  const body = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    const detail =
      typeof body === "object" &&
      body !== null &&
      typeof (body as Record<string, unknown>).detail === "string"
        ? String((body as Record<string, unknown>).detail)
        : `세션 API 오류 ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

function formatGameTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function SessionMenu() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<GameSessionList>({
    current_session_id: null,
    sessions: [],
  });
  const [newName, setNewName] = useState("브라이어 코브 새 이야기");
  const [action, setAction] = useState<SessionAction>("loading");
  const [message, setMessage] = useState<string | null>(null);

  const current = data.sessions.find(
    (session) => session.id === data.current_session_id,
  );

  async function refresh(): Promise<void> {
    const body = await sessionRequest("/sessions");
    const parsed = parseSessionList(body);
    if (parsed === null) throw new Error("세션 목록 형식이 올바르지 않습니다");
    setData(parsed);
  }

  useEffect(() => {
    refresh()
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : "세션 연결 실패"),
      )
      .finally(() => setAction(null));
  }, []);

  async function createSession(): Promise<void> {
    const name = newName.trim();
    if (!name) {
      setMessage("새 세션 이름을 입력해주세요");
      return;
    }
    if (
      current &&
      !window.confirm("현재 진행을 저장하지 않고 새 이야기를 시작할까요?")
    ) {
      return;
    }
    setAction("creating");
    setMessage(null);
    try {
      await sessionRequest("/sessions", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      await refresh();
      setOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "새 세션 생성 실패");
    } finally {
      setAction(null);
    }
  }

  async function saveCurrent(): Promise<void> {
    if (!current) return;
    setAction("saving");
    setMessage(null);
    try {
      await sessionRequest("/sessions/current/save", {
        method: "POST",
        body: JSON.stringify({ expected_save_version: current.save_version }),
      });
      await refresh();
      setMessage("현재 이야기를 안전하게 저장했습니다");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "세션 저장 실패");
      await refresh().catch(() => undefined);
    } finally {
      setAction(null);
    }
  }

  async function loadSession(session: GameSessionSummary): Promise<void> {
    if (session.id === data.current_session_id) return;
    if (!window.confirm(`“${session.name}” 저장본을 불러올까요?`)) return;
    setAction("loading-session");
    setMessage(null);
    try {
      await sessionRequest(`/sessions/${session.id}/load`, {
        method: "POST",
        body: "{}",
      });
      await refresh();
      setOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "세션 불러오기 실패");
    } finally {
      setAction(null);
    }
  }

  const busy = action !== null;
  return (
    <>
      <button
        type="button"
        className="session-menu-button"
        onClick={() => setOpen(true)}
        aria-label="세션 메뉴 열기"
      >
        <Gamepad2 size={14} />
        <span>{current?.name ?? "세션"}</span>
      </button>

      {open ? (
        <div className="session-modal-backdrop" role="presentation">
          <section
            className="session-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="session-modal-title"
          >
            <header>
              <div>
                <span>BRIAR COVE SAVE DATA</span>
                <h2 id="session-modal-title">이야기 보관함</h2>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="세션 메뉴 닫기"
                disabled={busy}
              >
                <X size={18} />
              </button>
            </header>

            <div className="session-current-card">
              <div>
                <small>지금 플레이 중</small>
                <strong>{current?.name ?? "준비 중"}</strong>
                <span>
                  {current
                    ? `${formatGameTime(current.world_time)} · TURN ${current.turn}`
                    : "활성 세션이 없습니다"}
                </span>
              </div>
              <button
                type="button"
                className="session-primary-action"
                onClick={saveCurrent}
                disabled={!current || busy}
              >
                {action === "saving" ? (
                  <Loader2 className="session-spinner" size={15} />
                ) : (
                  <Save size={15} />
                )}
                지금 저장
              </button>
            </div>

            <div className="session-new-row">
              <label htmlFor="new-session-name">새로운 이야기</label>
              <div>
                <input
                  id="new-session-name"
                  value={newName}
                  maxLength={80}
                  onChange={(event) => setNewName(event.target.value)}
                  disabled={busy}
                />
                <button type="button" onClick={createSession} disabled={busy}>
                  {action === "creating" ? (
                    <Loader2 className="session-spinner" size={15} />
                  ) : (
                    <Plus size={15} />
                  )}
                  새 세션
                </button>
              </div>
            </div>

            <div className="session-save-list">
              <div className="session-list-heading">
                <FolderOpen size={14} /> 저장된 이야기
                <b>{data.sessions.length}</b>
              </div>
              {data.sessions.map((session) => {
                const selected = session.id === data.current_session_id;
                return (
                  <article className={selected ? "active" : ""} key={session.id}>
                    <div>
                      <strong>{session.name}</strong>
                      <span>
                        {formatGameTime(session.world_time)} · 저장 {session.save_version}
                      </span>
                      <small>
                        TURN {session.turn} · {formatGameTime(session.saved_at)} 저장
                      </small>
                    </div>
                    <button
                      type="button"
                      onClick={() => loadSession(session)}
                      disabled={selected || busy}
                    >
                      {selected ? "플레이 중" : "불러오기"}
                    </button>
                  </article>
                );
              })}
            </div>

            {message ? <p className="session-message">{message}</p> : null}
          </section>
        </div>
      ) : null}
    </>
  );
}
