import axios, { type InternalAxiosRequestConfig } from 'axios';
import { isQuiet, requestFinished, requestStarted } from './loadingTracker';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001/api',
    // Generous: an uncached Price Intelligence search makes several provider
    // calls in sequence. Without any limit a stalled request hung forever.
    timeout: 180000,
});

// Every request that is not background polling drives the global loading
// bar. The flag on the config makes sure each request is counted out exactly
// once, whether it succeeds, fails or is cancelled.
type TrackedConfig = InternalAxiosRequestConfig & { __tracked?: boolean };

api.interceptors.request.use((config: TrackedConfig) => {
    if (!isQuiet(config.url)) {
        config.__tracked = true;
        requestStarted();
    }
    return config;
});

const settle = (config?: TrackedConfig) => {
    if (config?.__tracked) {
        config.__tracked = false;
        requestFinished();
    }
};

api.interceptors.response.use(
    (response) => {
        settle(response.config as TrackedConfig);
        return response;
    },
    (error) => {
        settle(error?.config as TrackedConfig | undefined);
        return Promise.reject(error);
    },
);

export default api;
