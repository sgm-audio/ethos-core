import http from 'k6/http';
import { check, sleep } from 'k6';

// K6 Load Test Configuration for ETHOS Core REST API
export const options = {
  stages: [
    { duration: '30s', target: 20 }, // Ramp-up to 20 virtual users
    { duration: '1m', target: 20 },  // Steady state load
    { duration: '15s', target: 0 },  // Ramp-down
  ],
  thresholds: {
    // SLO 1: 95th percentile latency must stay below 200ms
    http_req_duration: ['p(95)<200'],
    // SLO 2: Error rate must be less than 0.1% (99.9% availability)
    http_req_failed: ['rate<0.001'],
  },
};

const BASE_URL = __ENV.ETHOS_BASE_URL || 'http://localhost:8000';

export default function () {
  // 1. Root Metadata Endpoint
  const rootRes = http.get(`${BASE_URL}/`);
  check(rootRes, {
    'root status is 200': (r) => r.status === 200,
    'platform is operational': (r) => r.json('status') === 'operational',
  });

  // 2. Healthcheck & Readiness Probe (21 Agents check)
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
    'system is healthy': (r) => r.json('status') === 'healthy',
    'all 21 agents active': (r) => r.json('active_agents') === 21,
  });

  // 3. Prometheus Metrics Endpoint
  const metricsRes = http.get(`${BASE_URL}/metrics`);
  check(metricsRes, {
    'metrics status is 200': (r) => r.status === 200,
    'contains agent count': (r) => r.body.includes('ethos_active_agents'),
  });

  // 4. Jobs Registry List
  const jobsRes = http.get(`${BASE_URL}/jobs`);
  check(jobsRes, {
    'jobs list status is 200': (r) => r.status === 200,
  });

  sleep(0.5);
}
