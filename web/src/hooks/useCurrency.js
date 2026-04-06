import { useQuery } from '@tanstack/react-query';
import { getCurrencies, getExchangeRates } from '../api/currency';

export function useCurrencies() {
  return useQuery({
    queryKey: ['currencies'],
    queryFn: getCurrencies,
    staleTime: Infinity, // static list — never re-fetch
  });
}

export function useExchangeRates(base = 'GBP') {
  return useQuery({
    queryKey: ['exchange-rates', base],
    queryFn: () => getExchangeRates(base),
    staleTime: 60 * 60 * 1000, // 1 hour
    enabled: !!base,
  });
}

/**
 * Convert an amount from one currency to another using the provided rates map.
 * rates is { [targetCode]: rate } where rates are relative to a common base.
 * Assumes the rates map was fetched with the user's base_currency as the base,
 * so rates[from] gives units-of-base per 1 unit of `from`, and
 * rates[to] gives units-of-base per 1 unit of `to`.
 *
 * Actually simpler: when fetched with base=X, rates[Y] = how many Y per 1 X.
 * So: amount_in_Y = amount_in_X * rates[Y]
 *     amount_in_base = amount_in_X / rates[X] ... wait that's wrong.
 *
 * The rates endpoint returns: base=GBP, rates={USD: 1.27, EUR: 1.17, GBP: 1.0}
 * meaning 1 GBP = 1.27 USD. So to convert from USD to GBP:
 *   amount_GBP = amount_USD / rates['USD']
 * To convert from USD to EUR:
 *   amount_GBP = amount_USD / rates['USD']
 *   amount_EUR = amount_GBP * rates['EUR']
 */
export function convertCurrency(amount, fromCurrency, toCurrency, rates) {
  if (!rates || fromCurrency === toCurrency) return amount;
  // rates are base→target, so rates[from] = units of `from` per 1 base
  const fromRate = rates[fromCurrency];
  const toRate = rates[toCurrency];
  if (!fromRate || !toRate) return amount;
  // convert to base first, then to target
  return (amount / fromRate) * toRate;
}

/**
 * Return the currency symbol for a given ISO 4217 code.
 * Falls back to the code itself if unknown.
 */
const SYMBOLS = {
  GBP: '£', USD: '$', EUR: '€', JPY: '¥', CAD: 'CA$', AUD: 'A$',
  CHF: 'Fr', CNY: '¥', INR: '₹', MXN: 'MX$', BRL: 'R$', KRW: '₩',
  SGD: 'S$', HKD: 'HK$', SEK: 'kr', NOK: 'kr', DKK: 'kr', NZD: 'NZ$',
  ZAR: 'R', AED: 'د.إ', PLN: 'zł', TRY: '₺', THB: '฿', MYR: 'RM', IDR: 'Rp',
};

export function currencySymbol(code) {
  return SYMBOLS[code] || code;
}
