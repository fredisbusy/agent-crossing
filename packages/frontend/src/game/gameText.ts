import Phaser from "phaser";
import { useGameStore } from "../stores/game.store";

export type GameTextTone =
  | "location"
  | "room"
  | "nameplate"
  | "bubble"
  | "action"
  | "title";

export type GameTextAnchor =
  | "center"
  | "top"
  | "bottom"
  | "left-top"
  | "right-top";

export interface GameTextOverlay {
  id: string;
  text: string;
  left: number;
  top: number;
  tone: GameTextTone;
  anchor: GameTextAnchor;
  maxWidth?: number;
  selected?: boolean;
}

type DynamicValue<T> = T | (() => T);

export interface GameTextSource {
  id: string;
  text: DynamicValue<string>;
  x: DynamicValue<number>;
  y: DynamicValue<number>;
  tone: GameTextTone;
  anchor?: GameTextAnchor;
  maxWidth?: number;
  selected?: DynamicValue<boolean>;
  visible?: DynamicValue<boolean>;
}

function valueOf<T>(value: DynamicValue<T>): T {
  return typeof value === "function" ? (value as () => T)() : value;
}

function overlaysMatch(
  previous: readonly GameTextOverlay[],
  next: readonly GameTextOverlay[],
): boolean {
  return (
    previous.length === next.length &&
    previous.every((label, index) => {
      const candidate = next[index];
      return (
        candidate !== undefined &&
        label.id === candidate.id &&
        label.text === candidate.text &&
        label.left === candidate.left &&
        label.top === candidate.top &&
        label.tone === candidate.tone &&
        label.anchor === candidate.anchor &&
        label.maxWidth === candidate.maxWidth &&
        label.selected === candidate.selected
      );
    })
  );
}

export class GameTextOverlayController {
  private readonly sources = new Map<string, GameTextSource>();
  private previous: readonly GameTextOverlay[] = [];

  constructor(
    private readonly scene: Phaser.Scene,
    private readonly owner: string,
  ) {}

  add(source: GameTextSource): void {
    this.sources.set(source.id, source);
  }

  removeByPrefix(prefix: string): void {
    for (const id of this.sources.keys()) {
      if (id.startsWith(prefix)) this.sources.delete(id);
    }
  }

  sync(): void {
    const camera = this.scene.cameras.main;
    const labels = [...this.sources.values()]
      .filter((source) =>
        source.visible === undefined ? true : valueOf(source.visible),
      )
      .map((source): GameTextOverlay => {
        const left =
          camera.x + (valueOf(source.x) - camera.worldView.x) * camera.zoom;
        const top =
          camera.y + (valueOf(source.y) - camera.worldView.y) * camera.zoom;
        return {
          id: source.id,
          text: valueOf(source.text),
          left: Math.round(left),
          top: Math.round(top),
          tone: source.tone,
          anchor: source.anchor ?? "center",
          maxWidth: source.maxWidth,
          selected:
            source.selected === undefined
              ? undefined
              : valueOf(source.selected),
        };
      });
    if (overlaysMatch(this.previous, labels)) return;
    this.previous = labels;
    useGameStore.getState().setGameTextOverlay(this.owner, labels);
  }

  destroy(): void {
    this.sources.clear();
    this.previous = [];
    useGameStore.getState().clearGameTextOverlay(this.owner);
  }
}
