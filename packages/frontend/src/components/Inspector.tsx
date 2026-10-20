import { useWorldStore } from "../stores";

export function Inspector() {
  const snapshot = useWorldStore((state) => state.snapshot);
  const selectedId = useWorldStore((state) => state.selectedResidentId);
  const debug = useWorldStore((state) => state.debug);
  const recent = useWorldStore((state) => state.recentUtterances);
  const selectResident = useWorldStore((state) => state.selectResident);

  const residents = snapshot?.residents ?? [];
  const selected = residents.find((resident) => resident.resident_id === selectedId) ?? null;

  return (
    <aside className="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto border-l border-amber-900/30 bg-amber-50 p-3 text-sm text-stone-800">
      <h2 className="font-bold text-stone-700">주민 ({residents.length})</h2>
      <ul className="flex flex-col gap-1">
        {residents.map((resident) => (
          <li key={resident.resident_id}>
            <button
              type="button"
              onClick={() => selectResident(resident.resident_id === selectedId ? null : resident.resident_id)}
              className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left ${
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
    </aside>
  );
}
