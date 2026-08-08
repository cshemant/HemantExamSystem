# Online Deployment Checklist

1. Provision a PostgreSQL database.
2. Install `requirements-online.txt`.
3. Set `APP_MODE=online`.
4. Set a strong `SECRET_KEY` and `ADMIN_PASSWORD`.
5. Set `DATABASE_URL` to your PostgreSQL connection string.
6. Start with Gunicorn using `wsgi:app`.
7. Put Nginx/Cloudflare/hosting TLS in front of the app so students use HTTPS.
8. Set your domain/subdomain, e.g. `exam.example.com`.
9. Back up PostgreSQL automatically.
10. Load-test with approximately the number of simultaneous students you expect before a real exam.

No HTML/template rewrite is required when moving between offline and online mode.

## Offline V2.02 public download

The login page uses the stable application route `/download/offline`. Set `OFFLINE_DOWNLOAD_URL` in the online environment if the binary is hosted somewhere other than the default V2.02 GitHub Release asset. This lets the storage location change later without changing the public button URL.
