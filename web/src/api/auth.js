import client from './client';

export const login = (identifier, password) =>
  client.post('/login', { identifier, password }).then((r) => r.data);

export const signup = (email, password) =>
  client.post('/auth/signup', { email, password }).then((r) => r.data);

export const verifyEmail = (token) =>
  client.get('/auth/verify-email', { params: { token } }).then((r) => r.data);

export const requestPasswordReset = (email) =>
  client.post('/auth/password-reset-request', { email }).then((r) => r.data);

export const confirmPasswordReset = (token, newPassword) =>
  client
    .post('/auth/password-reset-confirm', { token, new_password: newPassword })
    .then((r) => r.data);

export const refreshSession = () =>
  client.post('/auth/refresh').then((r) => r.data);

export const logout = () =>
  client.post('/auth/logout').then((r) => r.data);
