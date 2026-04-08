import client from './client';

export const getSessions = () => client.get('/auth/sessions').then(r => r.data);
export const revokeSession = (id) => client.delete(`/auth/sessions/${id}`).then(r => r.data);
export const revokeAllOtherSessions = () => client.delete('/auth/sessions').then(r => r.data);
