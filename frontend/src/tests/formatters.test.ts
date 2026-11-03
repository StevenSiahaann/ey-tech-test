import { describe, it, expect } from 'vitest';
import { formatCurrency, generateSafeSessionId, formatValue } from '../utils/formatters';

describe('formatCurrency', () => {
  it('formats billions correctly for Indonesian and English', () => {
    const amount = 2_500_000_000;
    expect(formatCurrency(amount, 'id')).toBe('Rp 2.50 Miliar');
    expect(formatCurrency(amount, 'en')).toBe('IDR 2.50 Billion');
  });

  it('formats millions correctly for Indonesian and English', () => {
    const amount = 45_750_000;
    expect(formatCurrency(amount, 'id')).toBe('Rp 45.75 Juta');
    expect(formatCurrency(amount, 'en')).toBe('IDR 45.75 Million');
  });

  it('formats standard amounts with proper separators', () => {
    const amount = 750000;
    const resId = formatCurrency(amount, 'id');
    const resEn = formatCurrency(amount, 'en');
    expect(resId).toContain('Rp');
    expect(resEn).toContain('IDR');
  });

  it('handles negative values and zero properly', () => {
    expect(formatCurrency(0, 'id')).toContain('Rp');
    expect(formatCurrency(0, 'en')).toContain('IDR');
    const negativeBillion = -1_500_000_000;
    expect(formatCurrency(negativeBillion, 'en')).toBe('IDR -1.50 Billion');
  });
});

describe('generateSafeSessionId', () => {
  it('generates a valid session string prefix', () => {
    const id = generateSafeSessionId();
    expect(id).toMatch(/^session-/);
    expect(id.length).toBeGreaterThan(12);
  });

  it('generates distinct IDs on consecutive calls', () => {
    const id1 = generateSafeSessionId();
    const id2 = generateSafeSessionId();
    expect(id1).not.toBe(id2);
  });
});

describe('formatValue', () => {
  it('returns dash for null or undefined', () => {
    expect(formatValue(null)).toBe('-');
    expect(formatValue(undefined)).toBe('-');
  });

  it('formats financial columns as currency', () => {
    const res = formatValue(100_000_000, 'total_revenue', 'id');
    expect(res).toBe('Rp 100.00 Juta');
    const resGmv = formatValue(2_000_000_000, 'total_gmv', 'en');
    expect(resGmv).toBe('IDR 2.00 Billion');
  });

  it('formats percentage/rate columns with percent sign', () => {
    expect(formatValue(15.4, 'cancel_rate')).toBe('15.4%');
    expect(formatValue(8.2, 'margin_pct')).toBe('8.2%');
  });

  it('converts non-numeric values to string', () => {
    expect(formatValue('Jawa')).toBe('Jawa');
    expect(formatValue(true)).toBe('true');
  });
});
