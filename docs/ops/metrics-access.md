## Metrics access policy

### Default posture

`GET /metrics` is **not authenticated by the app**. Treat it as operational telemetry and expose it only:
- inside a private network/VPC, or
- through a reverse proxy with IP allowlist and/or auth.

### Example reverse proxy setup

See `ops/reverse-proxy/nginx.conf.example` and `ops/reverse-proxy/docker-compose.proxy.yml`.

### Nginx example (basic auth)

```nginx
location = /metrics {
  auth_basic "metrics";
  auth_basic_user_file /etc/nginx/.htpasswd;

  proxy_pass http://api:8000/metrics;
}
```

### Nginx example (IP allowlist)

```nginx
location = /metrics {
  allow 10.0.0.0/8;
  deny all;
  proxy_pass http://api:8000/metrics;
}
```

