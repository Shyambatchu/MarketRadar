import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001/api',
    // Generous: an uncached Price Intelligence search makes several provider
    // calls in sequence. Without any limit a stalled request hung forever.
    timeout: 180000,
});

export default api;
