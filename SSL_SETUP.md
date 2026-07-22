# SSL / HTTPS Setup — Let's Encrypt (Certbot)

How to obtain and auto-renew a free TLS certificate for the Musaid Portal on Ubuntu + Nginx.

> Prerequisite: DNS for your domain (`musaid.example.ly`) must already point to the
> server's public IP, Nginx must be running (DEPLOYMENT_UBUNTU.md steps 1–8), and
> ports 80 + 443 must be open.

---

## 1. Install Certbot

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

---

## 2. Obtain the certificate (Nginx plugin)

This automatically edits your Nginx config to add the `ssl_certificate` paths and an HTTP→HTTPS redirect:

```bash
sudo certbot --nginx -d musaid.example.ly -d www.musaid.example.ly
```

- Enter an admin email (for expiry notices).
- Agree to the ToS.
- When asked about redirecting HTTP to HTTPS, choose **Redirect**.

After success, Certbot writes certs to:
```
/etc/letsencrypt/live/musaid.example.ly/fullchain.pem
/etc/letsencrypt/live/musaid.example.ly/privkey.pem
```
(These are the paths referenced in `deploy/nginx-musaid.conf`.)

---

## 3. Verify

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -I https://musaid.example.ly        # expect HTTP/2 200
```

Confirm in a browser that the padlock is valid and that `http://` redirects to `https://`.

Optional external grade check: https://www.ssllabs.com/ssltest/

---

## 4. Auto-renewal

Certbot installs a systemd timer that renews automatically (~twice daily, renews when <30 days left). Verify it:

```bash
sudo systemctl status certbot.timer
# Dry-run a renewal to be sure Nginx reload works:
sudo certbot renew --dry-run
```

To reload Nginx after each renewal, add a deploy hook (one-time):

```bash
echo -e '#!/bin/sh\nsystemctl reload nginx' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

---

## 5. App-side requirement (important)

The application sets **`SESSION_COOKIE_SECURE=True`** in production, so session cookies
are only sent over HTTPS. Once TLS is live, keep:

```
MUSAID_ENV=production
MUSAID_COOKIE_SECURE=1
```

Do **not** browse the site over plain `http://` for login — it will redirect to HTTPS
(via the Nginx config), which is the intended behavior.

---

## 6. HSTS note

`deploy/nginx-musaid.conf` already sends `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
Only keep HSTS enabled once you're confident HTTPS is permanent for the domain
(and all subdomains, given `includeSubDomains`).

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Challenge fails (timeout) | Port 80 must be open and DNS must resolve to this server; `/.well-known/acme-challenge/` must be reachable |
| `too many certificates` | Let's Encrypt rate limit — wait, or use `--staging` while testing |
| Mixed-content warnings | Ensure assets load via `https://` (the templates use protocol-relative/HTTPS CDNs already) |
| Renewal didn't reload Nginx | Add the deploy hook in step 4 |
