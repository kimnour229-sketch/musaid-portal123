# Ubuntu Deployment Guide — Musaid Portal

End-to-end production deployment on **Ubuntu 22.04 / 24.04 LTS** using
**Gunicorn + systemd + Nginx + Let's Encrypt**.

Stack served: Flask 3.1 + SQLite (`musaid_ist.db`), behind Nginx over HTTPS.

> Conventions used below:
> - App path: `/opt/musaid/Musaid_Portal`
> - Service user: `musaid`
> - Domain: `musaid.example.ly` (replace with yours)

---

## 0. Prerequisites

- A VPS running Ubuntu 22.04/24.04 LTS with root/sudo.
- A domain name with an **A/AAAA record** pointing to the server's IP.
- Ports **80** and **443** open in the firewall/security group.

---

## 1. System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng \
    ufw fail2ban
```

`tesseract-ocr-ara` + `tesseract-ocr-eng` are required for the handout OCR/summary feature (`pytesseract`).

---

## 2. Create the service user and app directory

```bash
sudo useradd --system --create-home --home-dir /home/musaid --shell /usr/sbin/nologin musaid
sudo mkdir -p /opt/musaid
sudo chown musaid:www-data /opt/musaid
```

---

## 3. Deploy the application code

Copy the project to `/opt/musaid/Musaid_Portal` (via `git clone`, `scp`, or `rsync`). Example:

```bash
sudo -u musaid git clone <your-repo-url> /opt/musaid/Musaid_Portal
# OR upload the folder, then:
sudo chown -R musaid:www-data /opt/musaid/Musaid_Portal
```

---

## 4. Python virtualenv + dependencies

```bash
cd /opt/musaid/Musaid_Portal
sudo -u musaid python3 -m venv .venv
sudo -u musaid .venv/bin/pip install --upgrade pip
sudo -u musaid .venv/bin/pip install -r requirements.txt
```

---

## 5. Configure environment (.env)

```bash
sudo -u musaid cp .env.example .env
# Generate a strong secret:
sudo -u musaid .venv/bin/python -c "import secrets; print('MUSAID_SECRET_KEY=' + secrets.token_hex(32))"
# Edit .env: paste the secret, set MUSAID_ENV=production, MUSAID_COOKIE_SECURE=1
sudo -u musaid nano .env
sudo chmod 600 .env
```

Quick sanity check (should print `DEBUG = False`):

```bash
sudo -u musaid .venv/bin/python -c "import app; print('DEBUG =', app.DEBUG, '| ENV =', app.ENV)"
```

---

## 6. Log directory

```bash
sudo mkdir -p /var/log/musaid
sudo chown musaid:www-data /var/log/musaid
```

(The application also writes its own auth audit log to `/opt/musaid/Musaid_Portal/logs/auth.log`.)

---

## 7. Gunicorn under systemd

```bash
sudo cp deploy/musaid.service /etc/systemd/system/musaid.service
# Review paths/user/secret inside the unit if your layout differs:
sudo nano /etc/systemd/system/musaid.service

sudo systemctl daemon-reload
sudo systemctl enable --now musaid
sudo systemctl status musaid --no-pager
```

The app now listens on the UNIX socket `/run/musaid/musaid.sock`.

---

## 8. Nginx reverse proxy

```bash
sudo mkdir -p /var/www/certbot
sudo cp deploy/nginx-musaid.conf /etc/nginx/sites-available/musaid
sudo nano /etc/nginx/sites-available/musaid    # set your real server_name + static alias path
sudo ln -s /etc/nginx/sites-available/musaid /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

> Tip: For the very first run before you have a certificate, you can temporarily
> comment out the `listen 443` server block (or just run Certbot in step below,
> which will provision certs and rewrite the config).

---

## 9. HTTPS / SSL

Follow **SSL_SETUP.md** (Let's Encrypt via Certbot). Summary:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d musaid.example.ly -d www.musaid.example.ly
```

---

## 10. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 11. First-login hardening

1. Visit `https://musaid.example.ly/login`, sign in as `admin@musaid.edu.ly`.
2. Immediately go to **تغيير كلمة المرور** (`/change_password`) and change the default admin password.
3. Have each teacher log in once (migrates their legacy plaintext password to a hash),
   or run a force-reset campaign.

---

## 12. Updates / redeploy

```bash
cd /opt/musaid/Musaid_Portal
sudo -u musaid git pull            # or re-upload files
sudo -u musaid .venv/bin/pip install -r requirements.txt
sudo systemctl restart musaid
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| 502 Bad Gateway | `sudo systemctl status musaid`; `sudo journalctl -u musaid -n 50`; confirm socket `/run/musaid/musaid.sock` exists |
| Login fails over HTTPS | Ensure `MUSAID_COOKIE_SECURE=1` **and** the site is genuinely HTTPS; check cert validity |
| CSS/JS missing | Verify the Nginx `/static/` `alias` path matches the app dir |
| OCR/summary errors | Confirm `tesseract --version` and the `-ara`/`-eng` packs are installed |
| Uploads rejected (413) | `client_max_body_size` in Nginx must be ≥ 50M |
| Permission denied writing DB | App dir must be writable by `musaid` (`chown -R musaid:www-data`) |
