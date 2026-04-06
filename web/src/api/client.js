import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const BASE_URL =
  process.env.REACT_APP_API_URL ||
  'https://son-of-mervan-production.up.railway.app';

// In-memory access token lives in authStore — never written to localStorage.

let _refreshPromise = null;

const client = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send httpOnly refresh-token cookie on every request
});

// Inject the in-memory access token into every outgoing request
client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401: silently refresh the access token and retry the original request.
// Skips retry for the refresh/login/signup endpoints themselves.
client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;

    const isAuthEndpoint =
      original.url?.includes('/auth/refresh') ||
      original.url?.includes('/login') ||
      original.url?.includes('/auth/signup');

    if (status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;

      // Deduplicate concurrent 401s into a single refresh call
      if (!_refreshPromise) {
        _refreshPromise = axios
          .post(`${BASE_URL}/auth/refresh`, {}, { withCredentials: true })
          .then((res) => {
            const newToken = res.data.access_token;
            useAuthStore.getState().setToken(newToken);
            return newToken;
          })
          .catch(() => {
            useAuthStore.getState().clearAuth();
            return Promise.reject(new Error('Session expired'));
          })
          .finally(() => { _refreshPromise = null; });
      }

      try {
        const newToken = await _refreshPromise;
        original.headers.Authorization = `Bearer ${newToken}`;
        return client(original);
      } catch (e) {
        return Promise.reject(e);
      }
    }

    return Promise.reject(error);
  }
);

export default client;
