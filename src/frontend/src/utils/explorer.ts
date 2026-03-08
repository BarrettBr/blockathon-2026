const DEFAULT_TX_BASE = "https://devnet.xrpl.org/transactions";

export function getExplorerTxUrl(txHash: string): string {
  const hash = String(txHash || "").trim();
  if (!hash) return "";
  const configuredBase = String(import.meta.env.VITE_XRPL_EXPLORER_TX_BASE_URL || "").trim();
  const base = (configuredBase || DEFAULT_TX_BASE).replace(/\/+$/, "");
  return `${base}/${encodeURIComponent(hash)}`;
}

