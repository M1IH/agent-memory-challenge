import { defineRailway, github, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const apiVolume = volume("api-volume", {
    alerts: { usage: { "80": {}, "95": {}, "100": {} } },
    allowOnlineResize: true,
    region: "sfo",
    sizeMB: 500,
  });
  const api = service("api", {
    source: github("M1IH/agent-memory-challenge"),
    build: {
      builder: "DOCKERFILE",
      buildEnvironment: "V3",
      dockerfilePath: "/Dockerfile",
    },
    healthcheck: "/health",
    healthcheckTimeout: 300,
    replicas: { "sfo": 1 },
    volumeMounts: { "/data": apiVolume },
    env: {
      AML_API_KEY: preserve(),
      AML_DB_PATH: preserve(),
      AML_EMBED_ENABLED: preserve(),
      AML_LOCKDOWN: preserve(),
      AML_MAX_REQUEST_BYTES: preserve(),
      AML_MEMORY_CACHE_USERS: preserve(),
      PORT: preserve(),
      RAILWAY_RUN_UID: preserve(),
    },
  });

  return project("agent-memory-challenge", {
    resources: [api, apiVolume],
  });
});
