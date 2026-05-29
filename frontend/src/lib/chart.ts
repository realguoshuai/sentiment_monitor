export const safeNum = (v: unknown): number =>
  v === undefined || v === null || Number.isNaN(Number(v)) ? 0 : Number(v)
