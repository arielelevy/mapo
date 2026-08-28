/**
 * Estimador de tokens. Aproximación por caracteres, deliberadamente barata.
 *
 * Alcanza para el medidor de presupuesto porque la decisión que alimenta —qué cabe y
 * qué no— es un umbral, no una factura. El conteo que cobra sale del motor, en el
 * evento `usage`, y la interfaz muestra los dos por separado para que no se confundan.
 */
const CHARS_PER_TOKEN = 3.6;

export function estimateTokens(chars: number): number {
  return Math.round(chars / CHARS_PER_TOKEN);
}

export function formatTokens(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(n >= 10_000 ? 0 : 1) + "k";
  return String(n);
}

export function formatBytes(n: number): string {
  if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
  return Math.max(1, Math.round(n / 1024)) + " KB";
}
