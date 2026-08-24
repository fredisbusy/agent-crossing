import type { IGridEngine, MoveToConfig, Position } from "grid-engine";

type MovementEngine = Pick<
  IGridEngine,
  "getPosition" | "moveTo" | "setPosition" | "stopMovement"
>;

export type GridTransitionKind = "stationary" | "cardinal-step" | "resync";

export interface GridTransition {
  kind: GridTransitionKind;
  deltaX: number;
  deltaY: number;
}

export function classifyGridTransition(
  current: Position,
  target: Position,
): GridTransition {
  const deltaX = target.x - current.x;
  const deltaY = target.y - current.y;
  const manhattanDistance = Math.abs(deltaX) + Math.abs(deltaY);
  if (manhattanDistance === 0) {
    return { kind: "stationary", deltaX, deltaY };
  }
  if (manhattanDistance === 1) {
    return { kind: "cardinal-step", deltaX, deltaY };
  }
  return { kind: "resync", deltaX, deltaY };
}

/**
 * Adapts authoritative server tiles to Grid Engine without client pathfinding.
 * Normal updates animate exactly one cardinal tile; reconnect gaps snap to the
 * latest authoritative tile instead of inventing a route through collisions.
 */
export class ServerGridMovement {
  private static readonly singleStepConfig: MoveToConfig = {
    ignoreLayers: true,
    maxPathLength: 1,
  };

  constructor(private readonly engine: MovementEngine) {}

  sync(characterId: string, target: Position): GridTransition {
    const transition = classifyGridTransition(
      this.engine.getPosition(characterId),
      target,
    );
    if (transition.kind === "stationary") {
      return transition;
    }

    this.engine.stopMovement(characterId);
    if (transition.kind === "cardinal-step") {
      this.engine.moveTo(
        characterId,
        { x: target.x, y: target.y },
        ServerGridMovement.singleStepConfig,
      );
    } else {
      this.engine.setPosition(characterId, { x: target.x, y: target.y });
    }
    return transition;
  }
}
