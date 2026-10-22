import { useState } from "react";
import { useWorldStore } from "../stores";

export function Inspector() {
  const snapshot = useWorldStore((state) => state.snapshot);
  const selectedId = useWorldStore((state) => state.selectedResidentId);
  const debug = useWorldStore((state) => state.debug);
  const recent = useWorldStore((state) => state.recentUtterances);
  const selectResident = useWorldStore((state) => state.selectResident);

  const [sheetOpen, setSheetOpen] = useState(false);
  const residents = snapshot?.residents ?? [];
  const selected = residents.find((resident) => resident.resident_id === selectedId) ?? null;

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
          주민 ({residents.length}) {sheetOpen ? "▾" : "▴"}
        </span>
      </button>
      <div className={`${sheetOpen ? "flex" : "hidden"} min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3 md:flex`}>
        <h2 className="hidden font-bold text-stone-700 md:block">주민 ({residents.length})</h2>
        <ul className="flex flex-col gap-1">
          {residents.map((resident) => (
            <li key={resident.resident_id}>
              <button
                type="button"
                onClick={() => selectResident(resident.resident_id === selectedId ? null : resident.resident_id)}
                className={`flex min-h-11 w-full items-center gap-2 rounded px-2 py-1 text-left md:min-h-0 ${
                  resident.resident_id === selectedId ? "bg-emerald-200" : "hover:bg-amber-100"
                }`}
              >
                <span>{resident.emoji ?? "🙂"}</span>
                <span className="font-medium">{resident.display_name}</span>
              </button>
            </li>
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
