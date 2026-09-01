export function dataSourceLabel(mode: "live" | "mock"): string {
  return mode === "mock" ? "Dữ liệu tham chiếu (mock)" : "Nguồn dữ liệu: Binance API + WebSocket";
}
