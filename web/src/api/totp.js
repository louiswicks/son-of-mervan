import client from './client';

export const getTOTPStatus = () =>
  client.get('/auth/2fa/status').then((r) => r.data);

export const setupTOTP = () =>
  client.post('/auth/2fa/setup').then((r) => r.data);

export const confirmTOTP = (code) =>
  client.post('/auth/2fa/confirm', { code }).then((r) => r.data);

export const disableTOTP = (password, code) =>
  client.post('/auth/2fa/disable', { password, code }).then((r) => r.data);

export const verifyTOTPLogin = (challengeToken, code) =>
  client
    .post('/auth/2fa/verify-login', { challenge_token: challengeToken, code })
    .then((r) => r.data);
