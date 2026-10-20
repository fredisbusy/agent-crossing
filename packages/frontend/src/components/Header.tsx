import { useWorldStore } from "../stores";
import { CONNECTION_DOT_CLASSES, CONNECTION_LABELS, formatSimTime } from "./format";

export function Header() {
  const snapshot = useWorldStore((state) => state.snapshot);
  const connection = useWorldStore((state) => state.connection);
  const debug = useWorldStore((state) => state.debug);
  const toggleDebug = useWorldStore((state) => state.toggleDebug);

  return (
    <header className="flex items-center justify-between gap-4 border-b border-amber-900/30 bg-amber-50 px-4 py-2 text-stone-800">
      <h1 className="text-lg font-bold text-emerald-700">Agent Crossing</h1>
      <div className="flex items-center gap-4 text-sm">
        <span data-testid="sim-time">{snapshot ? formatSimTime(snapshot.sim_time) : "--"}</span>
        <span data-testid="tick">tick {snapshot ? snapshot.tick : "-"}</span>
        <span className="flex items-center gap-1" data-testid="connection">
          <span className={`inline-block h-2 w-2 rounded-full ${CONNECTION_DOT_CLASSES[connection]}`} />
          {CONNECTION_LABELS[connection]}
        </span>
        <button
          type="button"
          onClick={toggleDebug}
          aria-pressed={debug}
          className={`rounded px-2 py-1 text-xs font-semibold ${
            debug ? "bg-pink-500 text-white" : "bg-stone-200 text-stone-700 hover:bg-stone-300"
          }`}
        >
          디버그 {debug ? "ON" : "OFF"}
        </button>
      </div>
    </header>
  );
}
