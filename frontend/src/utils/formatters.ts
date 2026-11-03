export const formatCurrency = (val: number, lang: 'id' | 'en' = 'id'): string => {
  if (Math.abs(val) >= 1_000_000_000) {
    return lang === 'en'
      ? `IDR ${(val / 1_000_000_000).toFixed(2)} Billion`
      : `Rp ${(val / 1_000_000_000).toFixed(2)} Miliar`;
  } else if (Math.abs(val) >= 1_000_000) {
    return lang === 'en'
      ? `IDR ${(val / 1_000_000).toFixed(2)} Million`
      : `Rp ${(val / 1_000_000).toFixed(2)} Juta`;
  }
  return lang === 'en'
    ? `IDR ${Number(val).toLocaleString('en-US')}`
    : `Rp ${Number(val).toLocaleString('id-ID')}`;
};

export const generateSafeSessionId = (): string => {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return `session-${crypto.randomUUID()}`;
    }
  } catch (e) {}
  return `session-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
};

export const formatValue = (val: any, colName: string = '', lang: 'id' | 'en' = 'id'): string => {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    const isCurrency =
      colName.includes('revenue') ||
      colName.includes('gmv') ||
      colName.includes('margin') ||
      colName.includes('cogs') ||
      colName.includes('price') ||
      colName === 'aov';
    if (isCurrency) return formatCurrency(val, lang);
    if (colName.includes('rate') || colName.includes('pct') || colName.includes('percentage')) return `${val}%`;
    return val.toLocaleString(lang === 'en' ? 'en-US' : 'id-ID');
  }
  return String(val);
};

