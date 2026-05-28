#!/usr/bin/env python3
"""수행기관 홈페이지에서 이메일 주소를 수집합니다."""

import argparse
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_DOMAINS = {
    "sentry.io",
    "sentry.wixpress.com",
    "sentry-next.wixpress.com",
    "wixpress.com",
    "example.com",
    "test.com",
    "yourdomain.com",
}

JUNK_LOCAL_PREFIXES = ("noreply", "no-reply", "donotreply", "mailer-daemon")

CONTACT_PATHS = (
    "/contact",
    "/contact-us",
    "/contactus",
    "/about/contact",
    "/support",
    "/inquiry",
    "/문의",
    "/contact.html",
)

USER_AGENT = "Mozilla/5.0 (compatible; AgencyEmailCrawler/1.0)"


def normalize_url(url: str) -> str | None:
    if not url or pd.isna(url):
        return None
    u = str(url).strip()
    if not u:
        return None
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def site_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_junk_email(email: str) -> bool:
    email = email.lower()
    local, _, domain = email.partition("@")
    if any(domain == d or domain.endswith("." + d) for d in JUNK_DOMAINS):
        return True
    if any(local.startswith(p) for p in JUNK_LOCAL_PREFIXES):
        return True
    if len(local) > 40 and re.fullmatch(r"[a-f0-9]+", local):
        return True
    return False


def filter_emails(emails: set[str], page_url: str) -> list[str]:
    domain = site_domain(page_url)
    good = []
    for e in sorted(emails):
        if is_junk_email(e):
            continue
        edomain = e.split("@", 1)[1]
        if edomain == domain or edomain.endswith("." + domain) or domain.endswith(edomain):
            good.append(e)
    if good:
        return good
    return sorted(e for e in emails if not is_junk_email(e))


def extract_emails(html: str) -> set[str]:
    return set(EMAIL_RE.findall(html))


def fetch(client: httpx.Client, url: str) -> str | None:
    try:
        r = client.get(url)
        r.raise_for_status()
        return r.text
    except Exception:
        if url.startswith("https://"):
            try:
                r = client.get(url.replace("https://", "http://", 1))
                r.raise_for_status()
                return r.text
            except Exception:
                return None
        return None


def crawl_one(client: httpx.Client, homepage: str) -> tuple[list[str], list[str]]:
    """Returns (emails, visited_urls)."""
    base = normalize_url(homepage)
    if not base:
        return [], []

    visited = []
    all_emails: set[str] = set()

    urls = [base]
    for path in CONTACT_PATHS:
        urls.append(urljoin(base.rstrip("/") + "/", path.lstrip("/")))

    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        html = fetch(client, url)
        if not html:
            continue
        visited.append(url)
        all_emails |= extract_emails(html)
        if len(all_emails) >= 3:
            break

    return filter_emails(all_emails, base), visited


def main():
    parser = argparse.ArgumentParser(description="수행기관 홈페이지 이메일 크롤링")
    parser.add_argument(
        "--input",
        default="수행기관조회_20260520.xls",
        help="입력 엑셀 파일",
    )
    parser.add_argument(
        "--output",
        default="수행기관조회_이메일수집_테스트.xlsx",
        help="출력 엑셀 파일",
    )
    parser.add_argument("--limit", type=int, default=10, help="처리 건수")
    parser.add_argument("--delay", type=float, default=1.0, help="요청 간격(초)")
    args = parser.parse_args()

    df = pd.read_excel(args.input, engine="xlrd")
    has_homepage = df["홈페이지"].notna() & (df["홈페이지"].astype(str).str.strip() != "")
    targets = df[has_homepage].head(args.limit).copy()

    results = []
    with httpx.Client(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for i, (idx, row) in enumerate(targets.iterrows(), 1):
            name = row["수행기관명"]
            homepage = row["홈페이지"]
            print(f"\n[{i}/{len(targets)}] {name}")
            print(f"  URL: {homepage}")

            emails, visited = crawl_one(client, homepage)
            status = "OK" if emails else "NOT_FOUND"

            print(f"  방문: {len(visited)}페이지")
            print(f"  이메일: {', '.join(emails) if emails else '(없음)'} [{status}]")

            results.append(
                {
                    "index": idx,
                    "수행기관명": name,
                    "홈페이지": homepage,
                    "수집_이메일": "; ".join(emails),
                    "상태": status,
                    "방문_URL": "; ".join(visited),
                }
            )
            if i < len(targets):
                time.sleep(args.delay)

    out_df = pd.DataFrame(results)
    out_df.to_excel(args.output, index=False)
    found = (out_df["상태"] == "OK").sum()
    print(f"\n완료: {found}/{len(targets)}건 이메일 수집 → {args.output}")


if __name__ == "__main__":
    main()
