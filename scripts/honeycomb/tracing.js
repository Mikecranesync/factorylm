/**
 * OpenTelemetry Bootstrap — Honeycomb Integration
 * ================================================
 * Loaded via NODE_OPTIONS=-r /path/to/tracing.js before the openclaw process starts.
 *
 * Required env vars:
 *   HONEYCOMB_API_KEY       — Honeycomb ingest API key
 *   OTEL_SERVICE_NAME       — e.g. "openclaw-ultron", "openclaw-jarvis-legacy", "openclaw-jarvis-local"
 *
 * Optional env vars (set by setup scripts):
 *   OTEL_EXPORTER_OTLP_ENDPOINT  — defaults to https://api.honeycomb.io:443
 *   OTEL_EXPORTER_OTLP_PROTOCOL  — defaults to http/protobuf
 *   OTEL_INSTANCE_NAME            — human-friendly instance tag (ultron, jarvis-legacy, jarvis-local)
 *   OTEL_DEPLOYMENT_ENVIRONMENT   — production, staging, local
 */

'use strict';

const apiKey = process.env.HONEYCOMB_API_KEY;

if (!apiKey) {
  console.warn(
    '[tracing] ⚠  HONEYCOMB_API_KEY is not set — OpenTelemetry tracing is DISABLED. ' +
    'Set the variable and restart to enable Honeycomb telemetry.'
  );
  // Exit the bootstrap early; the app runs normally without tracing.
  return;
}

// ---------------------------------------------------------------------------
// Imports — all resolved from the global node_modules installed by the setup
// scripts.  If any package is missing we catch and warn rather than crashing
// the host process.
// ---------------------------------------------------------------------------
let NodeSDK, OTLPTraceExporter, createResource, getNodeAutoInstrumentations, ATTR;

try {
  ({ NodeSDK }                      = require('@opentelemetry/sdk-node'));
  ({ OTLPTraceExporter }            = require('@opentelemetry/exporter-trace-otlp-http'));
  const resources                   = require('@opentelemetry/resources');
  // OTel SDK v2.x uses resourceFromAttributes(), v1.x uses new Resource()
  createResource = resources.resourceFromAttributes
    ? (attrs) => resources.resourceFromAttributes(attrs)
    : (attrs) => new resources.Resource(attrs);
  ({ getNodeAutoInstrumentations }  = require('@opentelemetry/auto-instrumentations-node'));
  ATTR                              = require('@opentelemetry/semantic-conventions');
} catch (err) {
  console.warn(
    '[tracing] ⚠  Failed to load OpenTelemetry packages — tracing is DISABLED.\n' +
    '  Run the install-deps script first.\n' +
    '  Error: ' + err.message
  );
  return;
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const endpoint    = process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'https://api.honeycomb.io:443';
const protocol    = process.env.OTEL_EXPORTER_OTLP_PROTOCOL || 'http/protobuf';
const serviceName = process.env.OTEL_SERVICE_NAME            || 'openclaw-unknown';
const instanceName      = process.env.OTEL_INSTANCE_NAME            || 'unknown';
const deploymentEnv     = process.env.OTEL_DEPLOYMENT_ENVIRONMENT   || 'production';

// ---------------------------------------------------------------------------
// Resource attributes — instance identification metadata sent with every span
// ---------------------------------------------------------------------------
const resource = createResource({
  'service.name':                          serviceName,
  'service.version':                       process.env.npm_package_version || 'unknown',
  'deployment.environment.name':           deploymentEnv,
  'instance.name':                         instanceName,
  'host.name':                             require('os').hostname(),
  'host.arch':                             process.arch,
  'process.runtime.name':                  'node',
  'process.runtime.version':              process.version,
});

// ---------------------------------------------------------------------------
// OTLP HTTP Exporter → Honeycomb
// ---------------------------------------------------------------------------
const traceExporter = new OTLPTraceExporter({
  url: `${endpoint}/v1/traces`,
  headers: {
    'x-honeycomb-team': apiKey,
  },
});

// ---------------------------------------------------------------------------
// Auto-instrumentations — disable fs to cut noise
// ---------------------------------------------------------------------------
const instrumentations = getNodeAutoInstrumentations({
  '@opentelemetry/instrumentation-fs': { enabled: false },
  // dns can also be noisy; disable if needed:
  // '@opentelemetry/instrumentation-dns': { enabled: false },
});

// ---------------------------------------------------------------------------
// SDK initialisation
// ---------------------------------------------------------------------------
const sdk = new NodeSDK({
  resource,
  traceExporter,
  instrumentations,
});

try {
  sdk.start();
  console.log(
    `[tracing] ✓  OpenTelemetry started → ${endpoint}  service=${serviceName}  instance=${instanceName}`
  );
} catch (err) {
  console.warn('[tracing] ⚠  Failed to start OpenTelemetry SDK:', err.message);
}

// Graceful shutdown — flush remaining spans before process exit
const shutdown = () => {
  sdk
    .shutdown()
    .then(() => console.log('[tracing] SDK shut down cleanly'))
    .catch((err) => console.warn('[tracing] Error during SDK shutdown:', err.message));
};

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
