import type { Strategy } from "./api";

export function strategyName(strategies: Strategy[], key: string): string {
  const [id, version] = key.split("@");
  return strategies.find((strategy) => strategy.strategy_id === id && strategy.version === version)?.display_name ?? key;
}
