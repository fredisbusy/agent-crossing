import { memo, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { useWorldStore } from "../stores";

const NO_IDS: readonly string[] = [];

/** 같은 주민을 다시 누르면 선택을 푼다. 참조가 늘 같아 `ResidentRow` memo가 깨지지 않는다. */
function toggleResident(id: string): void {
  const { selectedResidentId, selectResident } = useWorldStore.getState();
  selectResident(id === selectedResidentId ? null : id);
}

interface ResidentRowProps {
  id: string;
  isSelected: boolean;
  onToggle: (id: string) => void;
}

/** 주민 한 줄. 자기 이모지·이름만 구독하고, 목록 전체가 다시 그려져도 props가 같으면 건너뛴다. */
const ResidentRow = memo(function ResidentRow({ id, isSelected, onToggle }: ResidentRowProps) {
  const emoji = useWorldStore((state) => state.snapshot?.residents.find((r) => r.resident_id === id)?.emoji ?? null);
  const name = useWorldStore((state) => state.snapshot?.residents.find((r) => r.resident_id === id)?.display_name ?? id);
  return (
    <li>
      <button
        type="button"
        onClick={() => onToggle(id)}
        className={`flex min-h-11 w-full items-center gap-2 rounded px-2 py-1 text-left md:min-h-0 ${
          isSelected ? "bg-emerald-200" : "hover:bg-amber-100"
        }`}
      >
        <span>{emoji ?? "🙂"}</span>
        <span className="font-medium">{name}</span>
      </button>
    </li>
  );
});

export function Inspector() {
  // 주민 id 목록만 얕게 비교해 구독한다: 틱마다 위치가 바뀌어도 목록은 다시 만들지 않는다.
  const residentIds = useWorldStore(useShallow((state) => state.snapshot?.residents.map((r) => r.resident_id) ?? NO_IDS));
  const selectedId = useWorldStore((state) => state.selectedResidentId);
  const debug = useWorldStore((state) => state.debug);
  const recent = useWorldStore((state) => state.recentUtterances);
  const selected = useWorldStore((state) => state.snapshot?.residents.find((r) => r.resident_id === state.selectedResidentId) ?? null);

  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <aside className="absolute inset-x-0 bottom-0 z-10 flex max-h-[60%] flex-col rounded-t-xl border-t border-amber-900/30 bg-amber-50 text-sm text-stone-800 shadow-[0_-4px_12px_rgba(0,0,0,0.25)] md:static md:max-h-none md:w-72 md:shrink-0 md:rounded-none md:border-l md:border-t-0 md:shadow-none">
      <button
        type="button"
        onClick={() => setSheetOpen((open) => !open)}
        aria-expanded={sheetOpen}
        className="flex min-h-11 shrink-0 flex-col items-center justify-center gap-1 md:hidden"
      >
        <span aria-hidden="true" className="h-1 w-10 rounded-full bg-stone-400" />
        <span className="font-bold text-stone-700">
          주민 ({residentIds.length}) {sheetOpen ? "▾" : "▴"}
        </span>
      </button>
      <div className={`${sheetOpen ? "flex" : "hidden"} min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3 md:flex`}>
        <h2 className="hidden font-bold text-stone-700 md:block">주민 ({residentIds.length})</h2>
        <ul className="flex flex-col gap-1">
          {residentIds.map((id) => (
            <ResidentRow key={id} id={id} isSelected={id === selectedId} onToggle={toggleResident} />
          ))}
        </ul>
        {selected ? (
          <section className="rounded border border-amber-900/20 bg-white p-2" data-testid="inspector-detail">
            <h3 className="font-bold">{selected.display_name}</h3>
            <dl className="mt-1 space-y-1">
              <div>
                <dt className="text-xs text-stone-500">위치</dt>
                <dd>
                  {selected.location_path} ({selected.tile.x}, {selected.tile.y})
                </dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">행동</dt>
                <dd>{selected.action_description ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">최근 말</dt>
                <dd>
                  {(recent[selected.resident_id] ?? []).length === 0 ? (
                    "-"
                  ) : (
                    <ul className="list-disc pl-4">
                      {(recent[selected.resident_id] ?? []).map((entry) => (
                        <li key={entry.tick}>{entry.text}</li>
                      ))}
                    </ul>
                  )}
                </dd>
              </div>
              {debug ? (
                <div>
                  <dt className="text-xs text-stone-500">마음 종류 (debug)</dt>
                  <dd>{selected.mind_kind ?? "-"}</dd>
                </div>
              ) : null}
            </dl>
          </section>
        ) : (
          <p className="text-stone-500">주민을 선택하면 자세히 보여줍니다.</p>
        )}
      </div>
    </aside>
  );
}
