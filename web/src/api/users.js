import client from './client';

export const getProfile = () =>
  client.get('/users/me').then((r) => r.data);

export const updateProfile = (payload) =>
  client.put('/users/me', payload).then((r) => r.data);

export const changePassword = (currentPassword, newPassword) =>
  client
    .put('/users/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    .then((r) => r.data);

export const deleteAccount = () =>
  client.delete('/users/me').then((r) => r.data);
