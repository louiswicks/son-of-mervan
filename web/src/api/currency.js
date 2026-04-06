import client from './client';

export const getCurrencies = () =>
  client.get('/currency/list').then((r) => r.data);

export const getExchangeRates = (base = 'GBP') =>
  client.get('/currency/rates', { params: { base } }).then((r) => r.data);
