import axios from 'axios';

const BASE_URL =
  process.env.REACT_APP_API_URL ||
  'https://son-of-mervan-production.up.railway.app';

// In-memory access token — never written to localStorage
let _accessToken = null;
let _onUnauthorized = null;
let _refreshPromise = null;

export const setAccessToken = (token) => { _accessToken = token; };
export const getAccessToken = () => _accessToken;

/**
 * Register a callback that fires when a refresh attempt fails (session expired).
 * App.js uses this to redirect to the login page.
 */
export const setOnUnauthorized = (cb) => { _onUnauthorized = cb; };

const client = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send httpOnly refresh-token cookie on every request
});

// Inject the in-memory access token into every outgoing request
client.interceptors.request.use((config) => {
  if (_accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
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
            setAccessToken(newToken);
            return newToken;
          })
          .catch(() => {
            setAccessToken(null);
            if (_onUnauthorized) _onUnauthorized();
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
