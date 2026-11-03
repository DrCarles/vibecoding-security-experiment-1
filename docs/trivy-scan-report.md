# Trivy Vulnerability Scan Report

| | |
|---|---|
| **System scanned** | Chirp, commit `c1b20f2` ([DrCarles/vibecoding-security-experiment-1](https://github.com/DrCarles/vibecoding-security-experiment-1)) |
| **Scanner** | Trivy 0.74.0, vulnerability DB v2 updated 2026-11-03 07:14 UTC |
| **Scan date** | 2026-11-03 |
| **Scanners used** | `vuln` + `secret` on images; `vuln` + `misconfig` + `secret` on the repository |
| **Raw results** | [trivy-results/](trivy-results/) (Trivy JSON, one file per target) |
| **Related** | [Security gap analysis](security-gap-analysis.md), finding X-04 |

## 1. Summary

The scan found **no secrets and no Dockerfile misconfigurations**, but **many outdated dependencies**:

- **All dependency findings in Chirp's own code can be fixed by upgrading.** The pinned Python and npm versions in `requirements.txt` and `package.json` date from late 2024, about two years before the scan. That accounts for every critical finding in the application.
- **The Debian base image has 85 known CVEs with no fix available yet.** Most affect tools the app never runs (`mount`, `login`, `util-linux`).
- **The `postgres:17-alpine` image** carries an outdated `gosu` binary built with an old Go version: 61 findings, all fixed in newer image releases.

| Target | Critical | High | Medium | Low | Unknown | Fixable | Notes |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| `chirp-backend`: Python packages | **6** | **50** | 30 | 6 | 0 | 92 / 92 | 84 in app dependencies, 8 in pip's bundled packages |
| `chirp-backend`: Debian 13.7 OS | 0 | 45 | 72 | 61 | 7 | 0 / 185 | 85 unique CVEs; no fixes released |
| `chirp-frontend`: Node packages | 0 | 13 | 22 | 4 | 0 | 39 / 39 | 16 in the app, 23 in the npm tool bundled with Node |
| `chirp-frontend`: Alpine 3.24.3 OS | 0 | 0 | 0 | 0 | 0 | – | Clean |
| `postgres:17-alpine`: `gosu` (Go) | 1 | 25 | 31 | 3 | 1 | 61 / 61 | Old Go stdlib in the privilege-drop helper |
| `postgres:17-alpine`: Alpine 3.24.3 OS | 0 | 0 | 0 | 0 | 0 | – | Clean |
| Repo: `backend/requirements.txt` | 6 | 42 | 25 | 4 | 0 | 77 / 77 | Same as the image's direct dependencies |
| Repo: `frontend/package-lock.json` | 0 | 3 | 10 | 3 | 0 | 16 / 16 | Same as the image's app dependencies |
| Repo: Dockerfiles (misconfig) | – | – | – | – | – | – | **0 failures**, 27/27 checks passed in each Dockerfile |
| Repo and images: secrets | – | – | – | – | – | – | **0 secrets found** |

*Counts are Trivy findings, so a CVE that affects several OS packages counts once per package. The repository rows repeat the image findings and are not additional.*

### Verdict

**Not ready for production.** Six critical and about 60 high-severity findings are in libraries that every request uses (FastAPI/Starlette, multipart parsing, image decoding, JWT verification), and all of them can be fixed by upgrading. Phase 1 below removes all critical findings and every high-severity finding that can be fixed.

---

## 2. Exploitability assessment

Trivy reports what is *installed*. The table below records whether Chirp's code can actually *reach* each vulnerable component, based on how Chirp uses it.

| Package (installed → fixed) | Worst | Used by Chirp for | Reachable? | Assessment |
|---|:-:|---|:-:|---|
| **pillow** 11.0.0 → 13.0.0 | Critical | Decoding every uploaded avatar and post image | **Yes** | [media.py](../backend/app/media.py) calls `Image.open()` **without restricting formats**, so Pillow identifies and parses any of its **42 registered formats** before the JPEG/PNG/WebP/GIF allow-list runs. Bugs in TIFF, PSD (code execution, CVE-2026-42311), FlashPix, MSP, SPIDER, FITS and McIdas are therefore reachable through an upload. The JPEG decoder overflow (CVE-2026-112403) is reachable even with the allow-list. The Ghostscript bug (CVE-2026-112900) is **not** reachable, because Ghostscript isn't installed in the image. |
| **PyJWT** 2.10.1 → 2.15.0 | Critical | Signing and verifying session cookies (HS256) | **Partly** | Chirp uses a fixed HMAC secret and `algorithms=["HS256"]`, and doesn't use JWKs or public keys. The JWKS, DER-key and OKP issues (CVE-2026-102268, -102271, -102267, GHSA-pxh4-856f-4h89) **don't apply**. The forged-token bypass (CVE-2026-48526), the `crit` header handling and the nested-payload DoS **may apply**. Treat it as reachable, because it guards authentication. |
| **starlette** 0.41.3 → 1.3.1 (via FastAPI) | High | HTTP framework; `StaticFiles` serves `/media` | **Yes** | The Range-header DoS (CVE-2025-62727) hits `StaticFiles`, which serves every image. The general DoS (CVE-2025-54121) and form-limit bypass (CVE-2026-54283) affect request parsing. The Windows UNC-path issue (CVE-2026-48818) doesn't apply, because the container runs Linux. |
| **python-multipart** 0.0.20 → 0.0.31 | High | Parsing every upload (`multipart/form-data`) | **Yes** | The DoS issues (CVE-2026-42561, -53539, -40347, -53540) are reachable by anyone who can send a POST. The path-traversal file write (CVE-2026-24486) needs the `UPLOAD_DIR` / keep-filename options, which Starlette doesn't use, so it's **not reachable**. |
| **compression** 1.7.5 → 1.8.2 | High | Gzip for static files | **Yes** | Memory leak on prematurely closed responses (CVE-2026-87776), a remote DoS. |
| **path-to-regexp** 0.1.12 → 0.1.13 | High | Express routing | Low | The ReDoS needs routes with parameters; Chirp's Express routes are only `/healthz` and `*`. Upgrade anyway. |
| **body-parser** 1.20.3 → 1.20.9 | High | Installed with Express | **No** | Chirp never calls `express.json()` or `urlencoded()`; request bodies are streamed to the backend. |
| **qs** 6.13.0 → 6.16.1 | Medium | Express query-string parsing | Yes | DoS through crafted array query strings. |
| **http-proxy-middleware** 3.0.3 → 3.0.6+ | Medium | The `/api` and `/media` proxy | Partly | The Host-header routing issue (CVE-2026-55602) needs the `router` option, which Chirp doesn't use. CVE-2025-32996 and -32997 affect the proxy's error and body-handling paths. |
| **morgan** 1.10.0 → 1.12.1 | Medium | Frontend access logging | **Yes** | Log forging through control characters, Unicode line separators or quotes in the URL or User-Agent (CVE-2026-5078, -15603, -87859). This undermines log integrity, which the audit-logging requirements AUT-008 and AUZ-006 depend on. |
| on-headers 1.0.2 → 1.1.0 | Low | Dependency of `compression` | Yes | Fixed by upgrading `compression`. |
| msgpack, urllib3, setuptools | High | **Nothing**: they are bundled inside `pip` | No | They live in pip's own `_vendor` folder; `import msgpack` fails in the app. They only matter if pip runs at runtime. Upgrade pip or remove it from the runtime image. |
| npm's bundled packages (23 findings: brace-expansion, sigstore, pacote, ip-address…) | High | **Nothing**: the npm tool inside `node:22-alpine` | No | npm is never run in the running container. Delete it from the runtime image. |
| Debian 13.7 OS packages (85 CVEs) | High | Base OS of `python:3.13-slim` | Mostly no | The 9 high-severity CVEs are in `util-linux`/`mount`/`login` (mount helpers, nsenter), `acl`, `ncurses`, `systemd` (homed), `perl` (Archive::Tar) and `sqlite3` (FTS). Chirp runs none of them; it uses PostgreSQL, not SQLite. There is **no fix in Debian yet**, so the only remedy is a smaller base image. |
| `gosu` Go stdlib v1.24.6 → 1.27.3 (postgres image) | Critical | Dropping root privileges when the Postgres container starts | Low | It runs once at startup and doesn't touch the network, so the Go `net/http`, crypto and TLS bugs can't be reached. Pulling the latest `postgres:17-alpine` image picks up a rebuilt `gosu`. |

**Bottom line:** 4 Python packages (`pillow`, `PyJWT`, `starlette`/`fastapi`, `python-multipart`) and 4 npm packages (`compression`, `qs`, `morgan`, `http-proxy-middleware`) are **exploitable over the network today**. Upgrading them is the single most important action.

---

## 3. Remediation plan

### Phase 1: immediately (before any exposure)

1. **Upgrade the Python dependencies** in [backend/requirements.txt](../backend/requirements.txt):

   | Package | From | To (minimum) |
   |---|---|---|
   | pillow | 11.0.0 | **13.0.0** |
   | PyJWT | 2.10.1 | **2.15.0** |
   | fastapi | 0.115.6 | the release that requires **starlette ≥ 1.3.1** |
   | python-multipart | 0.0.20 | **0.0.31** |
   | uvicorn, sqlalchemy, alembic, psycopg, pydantic-settings, argon2-cffi, slowapi | – | the latest releases (no findings, but they're stale) |

   Then run the backend test suite and fix any breaking changes (Starlette 1.x and Pillow 13 are major releases).

2. **Upgrade the npm dependencies** in [frontend/package.json](../frontend/package.json): `compression` ≥ 1.8.2, `morgan` ≥ 1.12.1, `http-proxy-middleware` ≥ 3.0.6, and Express to the latest 4.x so it pulls `body-parser` ≥ 1.20.9, `path-to-regexp` ≥ 0.1.13 and `qs` ≥ 6.16.1. Or move to Express 5. Regenerate `package-lock.json`.

3. **Limit which image formats Pillow will parse.** This is defence in depth, so the next Pillow bug in an obscure format can't be reached:
   ```python
   Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP", "GIF"])
   ```
   Pillow then never runs the TIFF, PSD, FPX or other parsers on untrusted input.

### Phase 2: harden the images

4. **Backend base image.** Switch to a minimal runtime image without a shell, mount, login or perl (e.g. distroless Python, Chainguard `python`, or a multi-stage build onto `gcr.io/distroless/python3-debian13`). This removes all 85 Debian CVEs that have no fix. If you stay on `python:3.13-slim`, rebuild weekly with `--pull` to pick up Debian fixes as they land, and remove `pip` and `setuptools` from the final image.
5. **Frontend image.** Use a multi-stage build: run `npm ci` in a build stage, then copy only `node_modules`, `server.js` and `public/` into a runtime stage without npm. Or delete npm: `rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx`. This removes 23 findings.
6. **Postgres.** Pin `postgres:17-alpine` by digest, then refresh the digest regularly (`docker compose pull`) to pick up rebuilt `gosu` and Alpine fixes.

### Phase 3: keep it clean (process)

7. **Scan in CI.** Fail the build on fixable high or critical findings:
   ```bash
   trivy fs --scanners vuln,misconfig,secret --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 .
   trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 chirp-backend:latest
   trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 chirp-frontend:latest
   ```
8. **Automated updates.** Enable Dependabot or Renovate for `pip`, `npm`, `docker` and `github-actions`.
9. **SBOM.** Produce a software bill of materials per build: `trivy image --format cyclonedx -o sbom-backend.cdx.json chirp-backend:latest`.
10. **Record accepted risk.** Write down the Debian CVEs with no fix in a `.trivyignore` file, each with an expiry date and justification (e.g. "util-linux mount helpers not executed by the application"), so new findings stand out.
11. **Compose misconfiguration.** Trivy doesn't check `docker-compose.yml`. Review it by hand or with another tool; the gap analysis already covers the Compose-level issues (no TLS, a database superuser, no resource limits or log rotation).

---

## 4. Scope and method

| Target | Command |
|---|---|
| Backend image | `trivy image --scanners vuln,secret --format json chirp-backend:latest` |
| Frontend image | `trivy image --scanners vuln,secret --format json chirp-frontend:latest` |
| Database image | `trivy image --scanners vuln,secret --format json postgres:17-alpine` |
| Repository | `trivy fs --scanners vuln,misconfig,secret --format json .` |

- The images are the ones built from commit `c1b20f2` and running in the local Docker Compose stack.
- The repository scan covered the working tree, including the untracked local `.env` file; **no secrets were detected**. Note that Trivy's built-in secret rules look for known token formats (cloud keys, private keys, GitHub tokens…). They don't flag generic `KEY=value` pairs, so passing this check doesn't prove there are no secrets in the repo.
- Misconfiguration checks covered both Dockerfiles. Each passed all 27 checks, including: a non-root `USER`, `HEALTHCHECK` present, no `latest`-tag base images, and no `ADD` of remote URLs. Trivy has no misconfiguration checks for `docker-compose.yml`.
- **Exploitability** (section 2) was assessed by reading Chirp's code and inspecting the backend image: Pillow's registered formats, whether Ghostscript is installed, and where `msgpack` and `urllib3` live.

To reproduce, run the four commands above from the repository root with the Compose images built.

---

## Appendix A: Full findings

The full list below was generated from the JSON files in [trivy-results/](trivy-results/). For OS packages, each CVE appears once, with every affected binary package listed. The repository scan is omitted because it repeats the image findings for the same packages.

### A.1 `chirp-backend:latest`


#### A.1.1 chirp-backend:latest (debian 13.7) (debian, 185 findings)

| Severity | Vulnerability | Affected packages | Installed | Fixed | Title |
|---|---|---|---|---|---|
| 🟠 High | [CVE-2025-69720](https://avd.aquasec.com/nvd/cve-2025-69720) | libncursesw6, libtinfo6, ncurses-base, ncurses-bin | 6.5+20250216-2 | – | ncurses: ncurses: Buffer overflow vulnerability may lead to arbitrary code execution. |
| 🟠 High | [CVE-2026-119373](https://avd.aquasec.com/nvd/cve-2026-119373) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: sqlite: Denial of service via heap-based buffer overflow in FTS5 |
| 🟠 High | [CVE-2026-16742](https://avd.aquasec.com/nvd/cve-2026-16742) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | systemd: systemd-homed: Local privilege escalation via missing home-record signature verification |
| 🟠 High | [CVE-2026-54369](https://avd.aquasec.com/nvd/cve-2026-54369) | libacl1 | 2.3.2-2+b1 | – | acl: Symlink traversal privilege escalation via libacl functions |
| 🟠 High | [CVE-2026-76642](https://avd.aquasec.com/nvd/cve-2026-76642) | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | 1:2.41.5-0+deb13u1 | – | util-linux: util-linux: failed external mount helper still runs privileged X-mount post-hooks |
| 🟠 High | [CVE-2026-78408](https://avd.aquasec.com/nvd/cve-2026-78408) | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | 1:2.41.5-0+deb13u1 | – | util-linux: util-linux: nsenter --join-cgroup leaks root cgroup migration authority |
| 🟠 High | [CVE-2026-78409](https://avd.aquasec.com/nvd/cve-2026-78409) | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | 1:2.41.5-0+deb13u1 | – | util-linux: util-linux: X-mount.subdir detached-tree resolution can escape via intermediate symlinks |
| 🟠 High | [CVE-2026-78410](https://avd.aquasec.com/nvd/cve-2026-78410) | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | 1:2.41.5-0+deb13u1 | – | util-linux: util-linux: restricted bind mounts do not pin the source, allowing X-mount.owner/group/mode redire |
| 🟠 High | [CVE-2026-9538](https://avd.aquasec.com/nvd/cve-2026-9538) | perl-base | 5.40.1-6+deb13u1 | – | perl-Archive-Tar: perl-Archive-Tar: Denial of Service via crafted tar header with large entry size |
| 🟡 Medium | [CVE-2026-102010](https://avd.aquasec.com/nvd/cve-2026-102010) | gcc-14-base, libgcc-s1, libstdc++6 | 14.2.0-19 | – | gcc-toolset-15-gcc: gcc: gcc-toolset-16: gcc: Denial of Service via use-after-free in binary heap erase_if |
| 🟡 Medium | [CVE-2026-114690](https://avd.aquasec.com/nvd/cve-2026-114690) | gcc-14-base, libgcc-s1, libstdc++6 | 14.2.0-19 | – | gcc: Confirmed out-of-bounds read/write in libstdc++ parallel `std |
| 🟡 Medium | [CVE-2026-114691](https://avd.aquasec.com/nvd/cve-2026-114691) | gcc-14-base, libgcc-s1, libstdc++6 | 14.2.0-19 | – | gcc: Integer wrap in `std |
| 🟡 Medium | [CVE-2026-115455](https://avd.aquasec.com/nvd/cve-2026-115455) | gcc-14-base, libgcc-s1, libstdc++6 | 14.2.0-19 | – | gcc: Stack overflow in std::bitset on libstdc++ |
| 🟡 Medium | [CVE-2026-119378](https://avd.aquasec.com/nvd/cve-2026-119378) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: sqlite: Denial of Service via use-after-free in R-Tree extension |
| 🟡 Medium | [CVE-2026-119591](https://avd.aquasec.com/nvd/cve-2026-119591) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: sqlite: Denial of Service via stack exhaustion in countOfViewOptimization() |
| 🟡 Medium | [CVE-2026-15059](https://avd.aquasec.com/nvd/cve-2026-15059) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | systemd: systemd-oomd: Unprivileged users can terminate arbitrary processes via IPC API |
| 🟡 Medium | [CVE-2026-15534](https://avd.aquasec.com/nvd/cve-2026-15534) | perl-base | 5.40.1-6+deb13u1 | – | perl: Perl: Arbitrary code execution via out-of-bounds memory access in regular expression engine. |
| 🟡 Medium | [CVE-2026-18374](https://avd.aquasec.com/nvd/cve-2026-18374) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Heap buffer overflow via attacker-controlled fopen mode string |
| 🟡 Medium | [CVE-2026-18477](https://avd.aquasec.com/nvd/cve-2026-18477) | tar | 1.35+dfsg-3.1 | – | tar: tar: TOCTOU in incremental dumpdir 'X' rename handling allows restore path escape |
| 🟡 Medium | [CVE-2026-18508](https://avd.aquasec.com/nvd/cve-2026-18508) | tar | 1.35+dfsg-3.1 | – | tar: tar: --one-top-level hardlink targets not confined to top-level directory enabling arbitrary file overwri |
| 🟡 Medium | [CVE-2026-19499](https://avd.aquasec.com/nvd/cve-2026-19499) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: Buffer Overflow in strfmon right-justification padding |
| 🟡 Medium | [CVE-2026-19542](https://avd.aquasec.com/nvd/cve-2026-19542) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: Fix out-of-bounds array write in tdelete |
| 🟡 Medium | [CVE-2026-27171](https://avd.aquasec.com/nvd/cve-2026-27171) | zlib1g | 1:1.3.dfsg+really1.3.1-1+b1 | – | zlib: zlib: Denial of Service via infinite loop in CRC32 combine functions |
| 🟡 Medium | [CVE-2026-3184](https://avd.aquasec.com/nvd/cve-2026-3184) | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | 1:2.41.5-0+deb13u1 | – | util-linux: util-linux: Access control bypass due to improper hostname canonicalization |
| 🟡 Medium | [CVE-2026-42250](https://avd.aquasec.com/nvd/cve-2026-42250) | libbz2-1.0 | 1.0.8-6 | – | bzip2: bzip2: Denial of Service in bzip2recover via a specially crafted file |
| 🟡 Medium | [CVE-2026-50812](https://avd.aquasec.com/nvd/cve-2026-50812) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: SQLite: Denial of Service via malformed changeset in Session Extension |
| 🟡 Medium | [CVE-2026-50813](https://avd.aquasec.com/nvd/cve-2026-50813) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: SQLite: Information disclosure via Session Extension changeset merge path |
| 🟡 Medium | [CVE-2026-5435](https://avd.aquasec.com/nvd/cve-2026-5435) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Out-of-bounds write via TSIG record processing |
| 🟡 Medium | [CVE-2026-54370](https://avd.aquasec.com/nvd/cve-2026-54370) | libacl1 | 2.3.2-2+b1 | – | acl: TOCTOU Symlink Traversal via getfacl/setfacl |
| 🟡 Medium | [CVE-2026-54371](https://avd.aquasec.com/nvd/cve-2026-54371) | libattr1 | 1:2.5.2-3 | – | attr: attr: Symlink Traversal Privilege Escalation via getfattr and setfattr |
| 🟡 Medium | [CVE-2026-54411](https://avd.aquasec.com/nvd/cve-2026-54411) | libpam-modules, libpam-modules-bin, libpam-runtime, libpam0g | 1.7.0-5 | – | linux-pam: Plaintext password recovery via timing discrepancy in pam_userdb module |
| 🟡 Medium | [CVE-2026-5704](https://avd.aquasec.com/nvd/cve-2026-5704) | tar | 1.35+dfsg-3.1 | – | tar: tar: Hidden file injection via crafted archives |
| 🟡 Medium | [CVE-2026-6238](https://avd.aquasec.com/nvd/cve-2026-6238) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Application crash or uninitialized memory read via crafted DNS response |
| 🟡 Medium | [CVE-2026-6368](https://avd.aquasec.com/nvd/cve-2026-6368) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Process abort due to invalid memory in wordexp |
| 🟡 Medium | [CVE-2026-6791](https://avd.aquasec.com/nvd/cve-2026-6791) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: Glibc: Denial of Service via stack exhaustion during tilde expansion |
| 🟡 Medium | [CVE-2026-77117](https://avd.aquasec.com/nvd/cve-2026-77117) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: Non-progress DoS in SHIFT_JISX0213 -&gt |
| 🟡 Medium | [CVE-2026-80489](https://avd.aquasec.com/nvd/cve-2026-80489) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: Non-progress DoS in EUC_JISX0213 -&gt; UCS-4 conversion state |
| 🟡 Medium | [CVE-2026-82560](https://avd.aquasec.com/nvd/cve-2026-82560) | perl-base | 5.40.1-6+deb13u1 | – | Pod::Text versions before 6.1.1 for Perl allow CPU and memory exhausti ... |
| 🟡 Medium | [CVE-2026-84243](https://avd.aquasec.com/nvd/cve-2026-84243) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Arbitrary code execution via directory traversal in LANGUAGE environment variable |
| 🟡 Medium | [CVE-2026-85091](https://avd.aquasec.com/nvd/cve-2026-85091) | zlib1g | 1:1.3.dfsg+really1.3.1-1+b1 | – | zlib versions 1.3.1.2 through 1.3.2 contain a heap buffer overflow vul ... |
| 🟡 Medium | [CVE-2026-8674](https://avd.aquasec.com/nvd/cve-2026-8674) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc DNS stub resolver: Denial of Service via long search domain in configuration |
| 🟡 Medium | [CVE-2026-86805](https://avd.aquasec.com/nvd/cve-2026-86805) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Privilege escalation and arbitrary code execution via TOCTOU race condition in dynamic loader |
| 🟡 Medium | [CVE-2026-89092](https://avd.aquasec.com/nvd/cve-2026-89092) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: nscd stack overflow leads to degraded DNS resolution |
| 🟡 Medium | [CVE-2026-95619](https://avd.aquasec.com/nvd/cve-2026-95619) | gcc-14-base, libgcc-s1, libstdc++6 | 14.2.0-19 | – | gcc: libstdc++ integer overflow in `new` operator |
| 🟡 Medium | [CVE-2026-95818](https://avd.aquasec.com/nvd/cve-2026-95818) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Local attacker can cause denial of service and information disclosure via stack-based buffer ove |
| 🔵 Low | [CVE-2005-2541](https://avd.aquasec.com/nvd/cve-2005-2541) | tar | 1.35+dfsg-3.1 | – | tar: does not properly warn the user when extracting setuid or setgid files |
| 🔵 Low | [CVE-2007-5686](https://avd.aquasec.com/nvd/cve-2007-5686) | login.defs, passwd | 1:4.17.4-2 | – | initscripts in rPath Linux 1 sets insecure permissions for the /var/lo ... |
| 🔵 Low | [CVE-2010-4756](https://avd.aquasec.com/nvd/cve-2010-4756) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glob implementation can cause excessive CPU and memory consumption due to crafted glob expressions |
| 🔵 Low | [CVE-2011-3374](https://avd.aquasec.com/nvd/cve-2011-3374) | apt, libapt-pkg7.0 | 3.0.3 | – | It was found that apt-key in apt, all versions, do not correctly valid ... |
| 🔵 Low | [CVE-2011-4116](https://avd.aquasec.com/nvd/cve-2011-4116) | perl-base | 5.40.1-6+deb13u1 | – | perl: File:: Temp insecure temporary file handling |
| 🔵 Low | [CVE-2013-4392](https://avd.aquasec.com/nvd/cve-2013-4392) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | systemd: TOCTOU race condition when updating file permissions and SELinux security contexts |
| 🔵 Low | [CVE-2017-18018](https://avd.aquasec.com/nvd/cve-2017-18018) | coreutils | 9.7-3 | – | coreutils: race condition vulnerability in chown and chgrp |
| 🔵 Low | [CVE-2018-20796](https://avd.aquasec.com/nvd/cve-2018-20796) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: uncontrolled recursion in function check_dst_limits_calc_pos_1 in posix/regexec.c |
| 🔵 Low | [CVE-2019-1010022](https://avd.aquasec.com/nvd/cve-2019-1010022) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: stack guard protection bypass |
| 🔵 Low | [CVE-2019-1010023](https://avd.aquasec.com/nvd/cve-2019-1010023) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: running ldd on malicious ELF leads to code execution because of wrong size computation |
| 🔵 Low | [CVE-2019-1010024](https://avd.aquasec.com/nvd/cve-2019-1010024) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: ASLR bypass using cache of thread stack and heap |
| 🔵 Low | [CVE-2019-1010025](https://avd.aquasec.com/nvd/cve-2019-1010025) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: information disclosure of heap addresses of pthread_created thread |
| 🔵 Low | [CVE-2019-9192](https://avd.aquasec.com/nvd/cve-2019-9192) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: uncontrolled recursion in function check_dst_limits_calc_pos_1 in posix/regexec.c |
| 🔵 Low | [CVE-2021-45346](https://avd.aquasec.com/nvd/cve-2021-45346) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: crafted SQL query allows a malicious user to obtain sensitive information |
| 🔵 Low | [CVE-2022-0563](https://avd.aquasec.com/nvd/cve-2022-0563) | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | 1:2.41.5-0+deb13u1 | – | util-linux: partial disclosure of arbitrary files in chfn and chsh when compiled with libreadline |
| 🔵 Low | [CVE-2023-31437](https://avd.aquasec.com/nvd/cve-2023-31437) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | An issue was discovered in systemd 253. An attacker can modify a seale ... |
| 🔵 Low | [CVE-2023-31438](https://avd.aquasec.com/nvd/cve-2023-31438) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | An issue was discovered in systemd 253. An attacker can truncate a sea ... |
| 🔵 Low | [CVE-2023-31439](https://avd.aquasec.com/nvd/cve-2023-31439) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | An issue was discovered in systemd 253. An attacker can modify the con ... |
| 🔵 Low | [CVE-2024-56433](https://avd.aquasec.com/nvd/cve-2024-56433) | login.defs, passwd | 1:4.17.4-2 | – | shadow-utils: Default subordinate ID configuration in /etc/login.defs could lead to compromise |
| 🔵 Low | [CVE-2025-5278](https://avd.aquasec.com/nvd/cve-2025-5278) | coreutils | 9.7-3 | – | coreutils: Heap Buffer Under-Read in GNU Coreutils sort via Key Specification |
| 🔵 Low | [CVE-2025-6141](https://avd.aquasec.com/nvd/cve-2025-6141) | libncursesw6, libtinfo6, ncurses-base, ncurses-bin | 6.5+20250216-2 | – | gnu-ncurses: ncurses Stack Buffer Overflow |
| 🔵 Low | [CVE-2025-70873](https://avd.aquasec.com/nvd/cve-2025-70873) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | sqlite: SQLite: Information Disclosure via Crafted ZIP File |
| 🔵 Low | [CVE-2026-102473](https://avd.aquasec.com/nvd/cve-2026-102473) | dash | 0.5.12-12 | – | dash: dash: Super-polynomial backtracking in pmatch when libc fnmatch is disabled |
| 🔵 Low | [CVE-2026-102474](https://avd.aquasec.com/nvd/cve-2026-102474) | dash | 0.5.12-12 | – | dash: dash: Heap out-of-bounds write in conv_escape via undersized Unicode escape reservation |
| 🔵 Low | [CVE-2026-40228](https://avd.aquasec.com/nvd/cve-2026-40228) | libsystemd0, libudev1 | 257.13-1~deb13u1 | – | systemd: systemd-journald: Unintended output to user terminals via logger command |
| 🔵 Low | [CVE-2026-53910](https://avd.aquasec.com/nvd/cve-2026-53910) | diffutils | 1:3.10-4 | – | diffutils: heap‑based buffer overflow due to multiple signed integer overflows in line‑mapping calculations |
| 🔵 Low | [CVE-2026-56391](https://avd.aquasec.com/nvd/cve-2026-56391) | coreutils | 9.7-3 | – | coreutils: GNU coreutils uniq: Denial of Service and information disclosure via out-of-bounds read with multib |
| 🔵 Low | [CVE-2026-56392](https://avd.aquasec.com/nvd/cve-2026-56392) | coreutils | 9.7-3 | – | coreutils: GNU coreutils unexpand: Denial of Service via crafted tab stop values |
| 🔵 Low | [CVE-2026-97399](https://avd.aquasec.com/nvd/cve-2026-97399) | libc-bin, libc6 | 2.41-12+deb13u4 | – | glibc: glibc: Denial of Service via out-of-bounds read in strncasecmp |
| 🔵 Low | [TEMP-0290435-0B57B5](https://security-tracker.debian.org/tracker/TEMP-0290435-0B57B5) | tar | 1.35+dfsg-3.1 | – | [tar's rmt command may have undesired side effects] |
| 🔵 Low | [TEMP-0517018-A83CE6](https://security-tracker.debian.org/tracker/TEMP-0517018-A83CE6) | sysvinit-utils | 3.14-4 | – | [sysvinit: no-root option in expert installer exposes locally exploitable security flaw] |
| 🔵 Low | [TEMP-0628843-DBAD28](https://security-tracker.debian.org/tracker/TEMP-0628843-DBAD28) | login.defs, passwd | 1:4.17.4-2 | – | [more related to CVE-2005-4890] |
| 🔵 Low | [TEMP-0841856-B18BAF](https://security-tracker.debian.org/tracker/TEMP-0841856-B18BAF) | bash | 5.2.37-2+b10 | – | [Privilege escalation possible to other user than root] |
| ⚪ Unknown | [CVE-2026-119371](https://avd.aquasec.com/nvd/cve-2026-119371) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 contains a stack exhaustion vulnerability that al ... |
| ⚪ Unknown | [CVE-2026-119372](https://avd.aquasec.com/nvd/cve-2026-119372) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 built with FTS3/FTS4 and SQLITE_ENABLE_FTS3_PAREN ... |
| ⚪ Unknown | [CVE-2026-119374](https://avd.aquasec.com/nvd/cve-2026-119374) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 built with FTS5 contains a heap buffer overflow i ... |
| ⚪ Unknown | [CVE-2026-119375](https://avd.aquasec.com/nvd/cve-2026-119375) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 contains an information disclosure vulnerability  ... |
| ⚪ Unknown | [CVE-2026-119376](https://avd.aquasec.com/nvd/cve-2026-119376) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 contains a stack exhaustion vulnerability that al ... |
| ⚪ Unknown | [CVE-2026-119377](https://avd.aquasec.com/nvd/cve-2026-119377) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 contains an authorization bypass vulnerability in ... |
| ⚪ Unknown | [CVE-2026-119379](https://avd.aquasec.com/nvd/cve-2026-119379) | libsqlite3-0 | 3.46.1-7+deb13u2 | – | SQLite before 3.54.0 built with the session extension contains a heap  ... |

#### A.1.2 Python (python-pkg, 92 findings)

| Severity | Vulnerability | Package | Installed | Fixed | Location | Title |
|---|---|---|---|---|---|---|
| 🔴 Critical | [CVE-2026-112393](https://avd.aquasec.com/nvd/cve-2026-112393) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Heap buffer overflow in _tiffWriteProc when saving TIFF to BytesIO |
| 🔴 Critical | [CVE-2026-112398](https://avd.aquasec.com/nvd/cve-2026-112398) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Heap buffer overflow in FlashPix (FPX) JPEG decoding leads to code execution |
| 🔴 Critical | [CVE-2026-112403](https://avd.aquasec.com/nvd/cve-2026-112403) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Heap buffer overflow in ImagingJpegDecode |
| 🔴 Critical | [CVE-2026-112900](https://avd.aquasec.com/nvd/cve-2026-112900) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Argument Injection in Ghostscript call, potentially leading into RCE |
| 🔴 Critical | [CVE-2026-96639](https://avd.aquasec.com/nvd/cve-2026-96639) | pillow | 11.0.0 | 13.0.0 | app | Pillow is a Python imaging library. From 11.0.0 until 13.0.0, multi-fr ... |
| 🔴 Critical | [CVE-2026-102268](https://avd.aquasec.com/nvd/cve-2026-102268) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: PyJWT: Authentication bypass via improper public key validation |
| 🟠 High | [CVE-2026-114613](https://avd.aquasec.com/nvd/cve-2026-114613) | msgpack | 1.1.2 | 1.2.3 | pip (vendored) | msgpack: msgpack: Denial of Service via memory leak during map deserialization |
| 🟠 High | [GHSA-6v7p-g79w-8964](https://github.com/advisories/GHSA-6v7p-g79w-8964) | msgpack | 1.1.2 | 1.2.1 | pip (vendored) | MessagePack for Python: Out-of-bounds read / crash on Unpacker reuse after a caught error |
| 🟠 High | [CVE-2026-112390](https://avd.aquasec.com/nvd/cve-2026-112390) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via infinite loop during crafted MIC image parsing |
| 🟠 High | [CVE-2026-112392](https://avd.aquasec.com/nvd/cve-2026-112392) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via zero-size images in rank filters |
| 🟠 High | [CVE-2026-112397](https://avd.aquasec.com/nvd/cve-2026-112397) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via out-of-bounds memory access on zero-width images |
| 🟠 High | [CVE-2026-112399](https://avd.aquasec.com/nvd/cve-2026-112399) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of service via crafted APNG image |
| 🟠 High | [CVE-2026-112400](https://avd.aquasec.com/nvd/cve-2026-112400) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via memory exhaustion from crafted GIF image |
| 🟠 High | [CVE-2026-112402](https://avd.aquasec.com/nvd/cve-2026-112402) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of service via double free during image transformation |
| 🟠 High | [CVE-2026-112404](https://avd.aquasec.com/nvd/cve-2026-112404) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via out-of-bounds read in TIFF decoding |
| 🟠 High | [CVE-2026-112406](https://avd.aquasec.com/nvd/cve-2026-112406) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via infinite loop during PDF page rewriting |
| 🟠 High | [CVE-2026-112892](https://avd.aquasec.com/nvd/cve-2026-112892) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via unbounded memory expansion in MSP image decoder |
| 🟠 High | [CVE-2026-112893](https://avd.aquasec.com/nvd/cve-2026-112893) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via invalid pointer free during font rendering |
| 🟠 High | [CVE-2026-112894](https://avd.aquasec.com/nvd/cve-2026-112894) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via crafted multi-frame image conversion |
| 🟠 High | [CVE-2026-112895](https://avd.aquasec.com/nvd/cve-2026-112895) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of service via crafted PDF during append operations |
| 🟠 High | [CVE-2026-112896](https://avd.aquasec.com/nvd/cve-2026-112896) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via out-of-bounds read in TIFF encoder |
| 🟠 High | [CVE-2026-112897](https://avd.aquasec.com/nvd/cve-2026-112897) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Information disclosure via uninitialized buffer in TIFF decoding |
| 🟠 High | [CVE-2026-112902](https://avd.aquasec.com/nvd/cve-2026-112902) | pillow | 11.0.0 | 13.0.0 | app | Pillow: Memory disclosure and segfault in libtiff encoder via crafted TIFF tags |
| 🟠 High | [CVE-2026-25990](https://avd.aquasec.com/nvd/cve-2026-25990) | pillow | 11.0.0 | 12.1.1 | app | pillow: Pillow: Out-of-bounds Write via Specially Crafted PSD Image |
| 🟠 High | [CVE-2026-40192](https://avd.aquasec.com/nvd/cve-2026-40192) | pillow | 11.0.0 | 12.2.0 | app | Pillow: Pillow: Denial of Service via decompression bomb in FITS image processing |
| 🟠 High | [CVE-2026-42311](https://avd.aquasec.com/nvd/cve-2026-42311) | pillow | 11.0.0 | 12.2.0 | app | Pillow: python-pillow: Pillow: Arbitrary code execution via malicious PSD file processing |
| 🟠 High | [CVE-2026-54058](https://avd.aquasec.com/nvd/cve-2026-54058) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Memory disclosure or denial of service via crafted McIdas AREA image |
| 🟠 High | [CVE-2026-54059](https://avd.aquasec.com/nvd/cve-2026-54059) | pillow | 11.0.0 | 12.3.0 | app | python-pillow: Pillow: Denial of Service via crafted PCF font data |
| 🟠 High | [CVE-2026-54060](https://avd.aquasec.com/nvd/cve-2026-54060) | pillow | 11.0.0 | 12.3.0 | app | python-pillow: Pillow: Denial of Service via excessive memory allocation when processing font files |
| 🟠 High | [CVE-2026-55379](https://avd.aquasec.com/nvd/cve-2026-55379) | pillow | 11.0.0 | 12.3.0 | app | python-pillow: Pillow: Denial of Service via crafted BDF font file |
| 🟠 High | [CVE-2026-55380](https://avd.aquasec.com/nvd/cve-2026-55380) | pillow | 11.0.0 | 12.3.0 | app | python-pillow: Pillow: Denial of Service via crafted GD 2.x image file |
| 🟠 High | [CVE-2026-59197](https://avd.aquasec.com/nvd/cve-2026-59197) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Native heap out-of-bounds write |
| 🟠 High | [CVE-2026-59199](https://avd.aquasec.com/nvd/cve-2026-59199) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Denial of Service via out-of-bounds write in image processing |
| 🟠 High | [CVE-2026-59200](https://avd.aquasec.com/nvd/cve-2026-59200) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Denial of service via crafted PDF stream |
| 🟠 High | [CVE-2026-59204](https://avd.aquasec.com/nvd/cve-2026-59204) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Denial of Service via crafted JPEG2000 image |
| 🟠 High | [CVE-2026-59205](https://avd.aquasec.com/nvd/cve-2026-59205) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Controlled native heap corruption in ImageCms.ImageCmsTransform.apply API |
| 🟠 High | [CVE-2026-96637](https://avd.aquasec.com/nvd/cve-2026-96637) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via decompression bomb bypass in SPIDER images |
| 🟠 High | [CVE-2026-96640](https://avd.aquasec.com/nvd/cve-2026-96640) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via duplicate page references in PDF files |
| 🟠 High | [CVE-2026-96642](https://avd.aquasec.com/nvd/cve-2026-96642) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via negative archive member size in TarIO |
| 🟠 High | [CVE-2026-96643](https://avd.aquasec.com/nvd/cve-2026-96643) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via repeated EXIF headers |
| 🟠 High | [CVE-2026-96644](https://avd.aquasec.com/nvd/cve-2026-96644) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via out-of-bounds read in metafile parser |
| 🟠 High | [CVE-2026-96778](https://avd.aquasec.com/nvd/cve-2026-96778) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Arbitrary code execution via JPEG encoder buffer overflow |
| 🟠 High | [CVE-2026-102267](https://avd.aquasec.com/nvd/cve-2026-102267) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: pyjwt: Verification key substitution via unvalidated JWKS redirects |
| 🟠 High | [CVE-2026-102271](https://avd.aquasec.com/nvd/cve-2026-102271) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: PyJWT: Authentication bypass via acceptance of DER public keys as HMAC secrets |
| 🟠 High | [CVE-2026-32597](https://avd.aquasec.com/nvd/cve-2026-32597) | PyJWT | 2.10.1 | 2.12.0 | app | pyjwt: PyJWT accepts unknown `crit` header extensions (RFC 7515 §4.1.11 MUST violation) |
| 🟠 High | [CVE-2026-48526](https://avd.aquasec.com/nvd/cve-2026-48526) | PyJWT | 2.10.1 | 2.13.0 | app | python-pyjwt: PyJWT: Authentication bypass due to forged JSON Web Tokens |
| 🟠 High | [GHSA-pxh4-856f-4h89](https://github.com/advisories/GHSA-pxh4-856f-4h89) | PyJWT | 2.10.1 | 2.14.0 | app | PyJWT: HS256/384/512 verify accepts empty HMAC key via oct JWK (PyJWK/PyJWKClient) enabling token fo |
| 🟠 High | [CVE-2026-24486](https://avd.aquasec.com/nvd/cve-2026-24486) | python-multipart | 0.0.20 | 0.0.22 | app | python-multipart: Python-Multipart: Arbitrary file write via path traversal vulnerability |
| 🟠 High | [CVE-2026-42561](https://avd.aquasec.com/nvd/cve-2026-42561) | python-multipart | 0.0.20 | 0.0.27 | app | python-multipart: python-multipart: Denial of Service via excessive multipart part headers |
| 🟠 High | [CVE-2026-53539](https://avd.aquasec.com/nvd/cve-2026-53539) | python-multipart | 0.0.20 | 0.0.30 | app | python-multipart: Python-Multipart: Denial of Service via crafted form-urlencoded bodies |
| 🟠 High | [CVE-2025-47273](https://avd.aquasec.com/nvd/cve-2025-47273) | setuptools | 70.3.0 | 78.1.1 | pip (vendored) | setuptools: Path Traversal Vulnerability in setuptools PackageIndex |
| 🟠 High | [CVE-2025-62727](https://avd.aquasec.com/nvd/cve-2025-62727) | starlette | 0.41.3 | 0.49.1 | app | starlette: Starlette DoS via Range header merging |
| 🟠 High | [CVE-2026-48818](https://avd.aquasec.com/nvd/cve-2026-48818) | starlette | 0.41.3 | 1.1.0 | app | starlette: Starlette: SSRF and NTLM credential theft via UNC paths in StaticFiles on Windows |
| 🟠 High | [CVE-2026-54283](https://avd.aquasec.com/nvd/cve-2026-54283) | starlette | 0.41.3 | 1.3.1 | app | starlette: Starlette: request.form() limits silently ignored for application/x-www-form-urlencoded e |
| 🟠 High | [CVE-2026-97687](https://avd.aquasec.com/nvd/cve-2026-97687) | urllib3 | 2.7.0 | 2.8.0 | pip (vendored) | urllib3: urllib3: Traffic interception via HTTPS proxy TLS configuration override |
| 🟠 High | [CVE-2026-97689](https://avd.aquasec.com/nvd/cve-2026-97689) | urllib3 | 2.7.0 | 2.8.0 | pip (vendored) | urllib3: urllib3: Denial of Service via unbounded memory allocation in chunk parser |
| 🟡 Medium | [CVE-2026-112391](https://avd.aquasec.com/nvd/cve-2026-112391) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via unbounded recursion in PDF parser |
| 🟡 Medium | [CVE-2026-112394](https://avd.aquasec.com/nvd/cve-2026-112394) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Information disclosure via out-of-bounds read in raw decoders |
| 🟡 Medium | [CVE-2026-112395](https://avd.aquasec.com/nvd/cve-2026-112395) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Information disclosure via crafted tiled TIFF image |
| 🟡 Medium | [CVE-2026-112401](https://avd.aquasec.com/nvd/cve-2026-112401) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via crafted GIF comments |
| 🟡 Medium | [CVE-2026-112891](https://avd.aquasec.com/nvd/cve-2026-112891) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via large GIF comments |
| 🟡 Medium | [CVE-2026-112898](https://avd.aquasec.com/nvd/cve-2026-112898) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Information disclosure via empty palette quantization |
| 🟡 Medium | [CVE-2026-112899](https://avd.aquasec.com/nvd/cve-2026-112899) | pillow | 11.0.0 | 13.0.0 | app | Pillow: EPS load(scale) lets Ghostscript render past the decompression bomb limit |
| 🟡 Medium | [CVE-2026-112901](https://avd.aquasec.com/nvd/cve-2026-112901) | pillow | 11.0.0 | 13.0.0 | app | pillow: Pillow: Denial of Service via crafted XBM image header |
| 🟡 Medium | [CVE-2026-42308](https://avd.aquasec.com/nvd/cve-2026-42308) | pillow | 11.0.0 | 12.2.0 | app | Pillow: Pillow: Denial of Service via integer overflow in font processing |
| 🟡 Medium | [CVE-2026-42310](https://avd.aquasec.com/nvd/cve-2026-42310) | pillow | 11.0.0 | 12.2.0 | app | Pillow: Pillow: Denial of Service via malicious PDF processing |
| 🟡 Medium | [CVE-2026-55798](https://avd.aquasec.com/nvd/cve-2026-55798) | pillow | 11.0.0 | 12.3.0 | app | python-pillow: Pillow: Arbitrary command injection via shell metacharacters in file paths |
| 🟡 Medium | [CVE-2026-59198](https://avd.aquasec.com/nvd/cve-2026-59198) | pillow | 11.0.0 | 12.3.0 | app | Pillow: Pillow: Information disclosure via TGA RLE encoder out-of-bounds read |
| 🟡 Medium | [CVE-2026-96636](https://avd.aquasec.com/nvd/cve-2026-96636) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via decompression bomb check bypass in multi-frame images |
| 🟡 Medium | [CVE-2026-96638](https://avd.aquasec.com/nvd/cve-2026-96638) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via crafted RLE BMP image |
| 🟡 Medium | [CVE-2026-96641](https://avd.aquasec.com/nvd/cve-2026-96641) | pillow | 11.0.0 | 13.0.0 | app | pillow: pillow: Denial of Service via integer overflow in text-width calculation |
| 🟡 Medium | [CVE-2026-101917](https://avd.aquasec.com/nvd/cve-2026-101917) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: PyJWT: Denial of Service via outbound request amplification on unknown key identifiers |
| 🟡 Medium | [CVE-2026-101918](https://avd.aquasec.com/nvd/cve-2026-101918) | PyJWT | 2.10.1 | 2.15.0 | app | pyjwt: PyJWT: Denial of Service via deeply nested JSON token payload |
| 🟡 Medium | [CVE-2026-102269](https://avd.aquasec.com/nvd/cve-2026-102269) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: PyJWT: Token revocation bypass via non-canonical signature decoding |
| 🟡 Medium | [CVE-2026-102270](https://avd.aquasec.com/nvd/cve-2026-102270) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: pyjwt: Denial of Service via regular expression backtracking in is_pem_format |
| 🟡 Medium | [CVE-2026-102274](https://avd.aquasec.com/nvd/cve-2026-102274) | PyJWT | 2.10.1 | 2.14.0 | app | pyjwt: pyjwt: Denial of Service via malformed RSA key in JWK set |
| 🟡 Medium | [CVE-2026-102275](https://avd.aquasec.com/nvd/cve-2026-102275) | PyJWT | 2.10.1 | 2.15.0 | app | pyjwt: PyJWT: Token verification bypass via mismatched OKP key components |
| 🟡 Medium | [CVE-2026-48522](https://avd.aquasec.com/nvd/cve-2026-48522) | PyJWT | 2.10.1 | 2.13.0 | app | python-pyjwt: PyJWT: Server-Side Request Forgery (SSRF) via uncontrolled URL fetching in PyJWKClient |
| 🟡 Medium | [CVE-2026-48523](https://avd.aquasec.com/nvd/cve-2026-48523) | PyJWT | 2.10.1 | 2.13.0 | app | python-pyjwt: PyJWT: Verifier-side algorithm bypass leads to unauthorized information access |
| 🟡 Medium | [CVE-2026-48525](https://avd.aquasec.com/nvd/cve-2026-48525) | PyJWT | 2.10.1 | 2.13.0 | app | python-pyjwt: PyJWT: Denial of Service via processing of crafted detached JWS tokens |
| 🟡 Medium | [CVE-2026-40347](https://avd.aquasec.com/nvd/cve-2026-40347) | python-multipart | 0.0.20 | 0.0.26 | app | python-multipart: Python-Multipart: Denial of Service via crafted multipart/form-data requests |
| 🟡 Medium | [CVE-2026-59890](https://avd.aquasec.com/nvd/cve-2026-59890) | setuptools | 70.3.0 | 83.0.0 | pip (vendored) | setuptools: setuptools: MANIFEST.in exclusion bypass in sdist via Unicode normalization collision (N |
| 🟡 Medium | [CVE-2025-54121](https://avd.aquasec.com/nvd/cve-2025-54121) | starlette | 0.41.3 | 0.47.2 | app | starlette: Starlette denial-of-service |
| 🟡 Medium | [CVE-2026-48710](https://avd.aquasec.com/nvd/cve-2026-48710) | starlette | 0.41.3 | 1.0.1 | app | starlette: Starlette: Security restriction bypass via malformed HTTP Host header |
| 🟡 Medium | [CVE-2026-48817](https://avd.aquasec.com/nvd/cve-2026-48817) | starlette | 0.41.3 | 1.1.0 | app | starlette: Starlette: Information disclosure and unintended method execution via non-standard HTTP m |
| 🟡 Medium | [CVE-2026-97688](https://avd.aquasec.com/nvd/cve-2026-97688) | urllib3 | 2.7.0 | 2.8.0 | pip (vendored) | urllib3: urllib3: Denial of Service via infinite loop during chunked Deflate decoding |
| 🔵 Low | [CVE-2026-48524](https://avd.aquasec.com/nvd/cve-2026-48524) | PyJWT | 2.10.1 | 2.13.0 | app | python-pyjwt: PyJWT: Denial of Service via unverified JSON Web Token key IDs |
| 🔵 Low | [CVE-2026-53537](https://avd.aquasec.com/nvd/cve-2026-53537) | python-multipart | 0.0.20 | 0.0.30 | app | multipart: Python-Multipart: Information disclosure via header parsing discrepancy |
| 🔵 Low | [CVE-2026-53538](https://avd.aquasec.com/nvd/cve-2026-53538) | python-multipart | 0.0.20 | 0.0.30 | app | python-multipart: Python-Multipart: Information disclosure due to parser differential in form data h |
| 🔵 Low | [CVE-2026-53540](https://avd.aquasec.com/nvd/cve-2026-53540) | python-multipart | 0.0.20 | 0.0.31 | app | python-multipart: Python-Multipart: Negative Content-Length in parse_form buffers the entire body in |
| 🔵 Low | [GHSA-xmj3-9gf7-h52w](https://github.com/advisories/GHSA-xmj3-9gf7-h52w) | setuptools | 70.3.0 | 84.1.0 | pip (vendored) | setuptools: Windows path escape via namespace_packages.txt during legacy wheel installation  Descrip |
| 🔵 Low | [CVE-2026-54282](https://avd.aquasec.com/nvd/cve-2026-54282) | starlette | 0.41.3 | 1.3.0 | app | starlette: Starlette: Information disclosure due to improper HTTP request path validation |

### A.2 `chirp-frontend:latest`


**chirp-frontend:latest (alpine 3.24.3)**: no vulnerabilities.


#### A.2.1 Node.js (node-pkg, 39 findings)

| Severity | Vulnerability | Package | Installed | Fixed | Location | Title |
|---|---|---|---|---|---|---|
| 🟠 High | [CVE-2026-111181](https://avd.aquasec.com/nvd/cve-2026-111181) | body-parser | 1.20.3 | 2.4.0, 1.20.9 | app | body-parser: body-parser: Denial of Service via unhandled decompression stream error |
| 🟠 High | [CVE-2026-102276](https://avd.aquasec.com/nvd/cve-2026-102276) | brace-expansion | 2.0.2 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | npm (bundled) | brace-expansion: brace-expansion: Denial of Service via stack exhaustion from crafted brace patterns |
| 🟠 High | [CVE-2026-102278](https://avd.aquasec.com/nvd/cve-2026-102278) | brace-expansion | 2.0.2 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | npm (bundled) | brace-expansion: brace-expansion: Denial of Service via uncontrolled recursion in nested brace patte |
| 🟠 High | [CVE-2026-13149](https://avd.aquasec.com/nvd/cve-2026-13149) | brace-expansion | 2.0.2 | 5.0.7, 1.1.16, 2.1.2 | npm (bundled) | brace-expansion: Brace-expansion: Denial of Service due to exponential-time complexity |
| 🟠 High | [CVE-2026-14257](https://avd.aquasec.com/nvd/cve-2026-14257) | brace-expansion | 2.0.2 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | npm (bundled) | brace-expansion: Brace-expansion: Denial of Service via memory exhaustion in expand() function |
| 🟠 High | [CVE-2026-69152](https://avd.aquasec.com/nvd/cve-2026-69152) | brace-expansion | 2.0.2 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | npm (bundled) | brace-expansion: DoS via unbounded intermediate arrays, bypassing the CVE-2026-14257 mitigation |
| 🟠 High | [CVE-2026-87776](https://avd.aquasec.com/nvd/cve-2026-87776) | compression | 1.7.5 | 1.8.2 | app | compression: compression: Denial of Service via memory leak on premature response close |
| 🟠 High | [CVE-2026-69192](https://avd.aquasec.com/nvd/cve-2026-69192) | ip-address | 10.1.0 | 10.3.1 | npm (bundled) | ip-address: ip-address: Inconsistent IP address parsing leads to Server-Side Request Forgery (SSRF) |
| 🟠 High | [CVE-2026-9496](https://avd.aquasec.com/nvd/cve-2026-9496) | pacote | 19.0.2 | 21.5.1 | npm (bundled) | pacote: Pacote: Denial of Service via crafted spec.rawSpec value in addGitSha function |
| 🟠 High | [CVE-2026-9496](https://avd.aquasec.com/nvd/cve-2026-9496) | pacote | 20.0.1 | 21.5.1 | npm (bundled) | pacote: Pacote: Denial of Service via crafted spec.rawSpec value in addGitSha function |
| 🟠 High | [CVE-2026-4867](https://avd.aquasec.com/nvd/cve-2026-4867) | path-to-regexp | 0.1.12 | 0.1.13 | app | path-to-regexp: path-to-regexp: Denial of Service via catastrophic backtracking from malformed URL p |
| 🟠 High | [CVE-2026-33671](https://avd.aquasec.com/nvd/cve-2026-33671) | picomatch | 4.0.3 | 4.0.4, 3.0.2, 2.3.2 | npm (bundled) | picomatch: Picomatch: Regular Expression Denial of Service via crafted extglob patterns |
| 🟠 High | [CVE-2026-48815](https://avd.aquasec.com/nvd/cve-2026-48815) | sigstore | 3.1.0 | 4.1.1 | npm (bundled) | sigstore: Sigstore: Unauthorized certificates accepted due to ignored `certificateOIDs` verification |
| 🟡 Medium | [CVE-2026-48758](https://avd.aquasec.com/nvd/cve-2026-48758) | @sigstore/core | 2.0.0 | 3.2.1 | npm (bundled) | sigstore-core: @sigstore/core: Signature bypass due to incorrect encoding in preAuthEncoding |
| 🟡 Medium | [CVE-2026-102277](https://avd.aquasec.com/nvd/cve-2026-102277) | brace-expansion | 2.0.2 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | npm (bundled) | brace-expansion: brace-expansion: Denial of Service via crafted brace patterns |
| 🟡 Medium | [CVE-2026-33750](https://avd.aquasec.com/nvd/cve-2026-33750) | brace-expansion | 2.0.2 | 5.0.5, 3.0.2, 2.0.3, 1.1.13 | npm (bundled) | brace-expansion: brace-expansion: Denial of Service via zero step value in brace pattern |
| 🟡 Medium | [CVE-2026-118773](https://avd.aquasec.com/nvd/cve-2026-118773) | glob | 10.5.0 | 14.0.2 | npm (bundled) | glob: glob: Denial of Service (DoS) via incomplete traversal cancellation |
| 🟡 Medium | [CVE-2025-32996](https://avd.aquasec.com/nvd/cve-2025-32996) | http-proxy-middleware | 3.0.3 | 2.0.8, 3.0.4 | app | http-proxy-middleware: Always-Incorrect Control Flow Implementation in http-proxy-middleware |
| 🟡 Medium | [CVE-2025-32997](https://avd.aquasec.com/nvd/cve-2025-32997) | http-proxy-middleware | 3.0.3 | 2.0.9, 3.0.5 | app | http-proxy-middleware: Improper Check for Unusual or Exceptional Conditions in http-proxy-middleware |
| 🟡 Medium | [CVE-2026-55602](https://avd.aquasec.com/nvd/cve-2026-55602) | http-proxy-middleware | 3.0.3 | 3.0.6, 4.1.0, 2.0.10 | app | http-proxy-middleware: http-proxy-middleware: Unintended backend routing due to crafted Host header |
| 🟡 Medium | [CVE-2026-101911](https://avd.aquasec.com/nvd/cve-2026-101911) | ip-address | 10.1.0 | 10.7.1 | npm (bundled) | ip-address: ip-address: Denial of Service via unbounded IPv6 address parsing |
| 🟡 Medium | [CVE-2026-101912](https://avd.aquasec.com/nvd/cve-2026-101912) | ip-address | 10.1.0 | 10.7.1 | npm (bundled) | ip-address: ip-address: Access control bypass via cross-family subnet comparison |
| 🟡 Medium | [CVE-2026-101913](https://avd.aquasec.com/nvd/cve-2026-101913) | ip-address | 10.1.0 | 10.5.1 | npm (bundled) | ip-address: ip-address: Security bypass via incomplete IPv6 link-local address validation |
| 🟡 Medium | [CVE-2026-111997](https://avd.aquasec.com/nvd/cve-2026-111997) | ip-address | 10.1.0 | 10.7.4 | npm (bundled) | ip-address: ip-address: Denial of Service via excessive percent characters in IPv6 address input |
| 🟡 Medium | [CVE-2026-42338](https://avd.aquasec.com/nvd/cve-2026-42338) | ip-address | 10.1.0 | 10.1.1 | npm (bundled) | ip-address: ip-address: Cross-site scripting via improper HTML escaping of untrusted input |
| 🟡 Medium | [CVE-2026-118764](https://avd.aquasec.com/nvd/cve-2026-118764) | minimatch | 9.0.9 | 11.0.1 | npm (bundled) | minimatch: minimatch: Denial of Service via crafted glob pattern expansion |
| 🟡 Medium | [CVE-2026-15603](https://avd.aquasec.com/nvd/cve-2026-15603) | morgan | 1.10.0 | 1.12.0 | app | morgan: morgan: Log Forging via unescaped Unicode line separators |
| 🟡 Medium | [CVE-2026-5078](https://avd.aquasec.com/nvd/cve-2026-5078) | morgan | 1.10.0 | 1.11.0 | app | morgan: morgan: Log forgery due to unneutralized control characters |
| 🟡 Medium | [CVE-2026-87859](https://avd.aquasec.com/nvd/cve-2026-87859) | morgan | 1.10.0 | 1.12.1 | app | morgan: morgan: Log Injection via unescaped double quote in log fields |
| 🟡 Medium | [CVE-2026-33672](https://avd.aquasec.com/nvd/cve-2026-33672) | picomatch | 4.0.3 | 4.0.4, 3.0.2, 2.3.2 | npm (bundled) | picomatch: Picomatch: Data integrity compromised via method injection with crafted POSIX bracket exp |
| 🟡 Medium | [CVE-2026-104844](https://avd.aquasec.com/nvd/cve-2026-104844) | postcss-selector-parser | 7.1.1 | 7.1.6, 6.1.5 | npm (bundled) | postcss-selector-parser: postcss-selector-parser: Denial of Service via crafted CSS selectors |
| 🟡 Medium | [CVE-2025-15284](https://avd.aquasec.com/nvd/cve-2025-15284) | qs | 6.13.0 | 6.14.1 | app | qs: qs: Denial of Service via improper input validation in array parsing |
| 🟡 Medium | [CVE-2026-110816](https://avd.aquasec.com/nvd/cve-2026-110816) | qs | 6.13.0 | 6.16.1 | app | qs: qs: Denial of Service via unhandled exception during array serialization |
| 🟡 Medium | [CVE-2026-82417](https://avd.aquasec.com/nvd/cve-2026-82417) | qs | 6.13.0 | 6.16.0 | app | qs: qs: Denial of Service via improper validation in stringify function |
| 🟡 Medium | [CVE-2026-8723](https://avd.aquasec.com/nvd/cve-2026-8723) | qs | 6.13.0 | 6.15.2 | app | qs: qs: Denial of Service due to improper handling of null/undefined array elements |
| 🔵 Low | [CVE-2026-12590](https://avd.aquasec.com/nvd/cve-2026-12590) | body-parser | 1.20.3 | 1.20.6, 2.3.0 | app | body-parser: body-parser: Denial of Service via invalid limit option |
| 🔵 Low | [CVE-2025-7339](https://avd.aquasec.com/nvd/cve-2025-7339) | on-headers | 1.0.2 | 1.1.0 | app | on-headers: on-headers vulnerable to http response header manipulation |
| 🔵 Low | [CVE-2026-9358](https://avd.aquasec.com/nvd/cve-2026-9358) | postcss-selector-parser | 7.1.1 | 6.1.3, 7.1.3 | npm (bundled) | postcss-selector-parser: Postcss: Denial of Service via uncontrolled recursion in AST Serialization |
| 🔵 Low | [CVE-2026-2391](https://avd.aquasec.com/nvd/cve-2026-2391) | qs | 6.13.0 | 6.14.2 | app | qs: qs's arrayLimit bypass in comma parsing allows denial of service |

### A.3 `postgres:17-alpine`


**postgres:17-alpine (alpine 3.24.3)**: no vulnerabilities.


#### A.3.1 usr/local/bin/gosu (gobinary, 61 findings)

| Severity | Vulnerability | Package | Installed | Fixed | Location | Title |
|---|---|---|---|---|---|---|
| 🔴 Critical | [CVE-2025-68121](https://avd.aquasec.com/nvd/cve-2025-68121) | stdlib | v1.24.6 | 1.24.13, 1.25.7, 1.26.0-rc.3 | – | crypto/tls: crypto/tls: Incorrect certificate validation during TLS session resumption |
| 🟠 High | [CVE-2025-61726](https://avd.aquasec.com/nvd/cve-2025-61726) | stdlib | v1.24.6 | 1.24.12, 1.25.6 | – | golang: net/url: Memory exhaustion in query parameter parsing in net/url |
| 🟠 High | [CVE-2025-61729](https://avd.aquasec.com/nvd/cve-2025-61729) | stdlib | v1.24.6 | 1.24.11, 1.25.5 | – | crypto/x509: golang: Denial of Service due to excessive resource consumption via crafted certificate |
| 🟠 High | [CVE-2026-111943](https://avd.aquasec.com/nvd/cve-2026-111943) | stdlib | v1.24.6 | 1.26.10, 1.27.3 | – | crypto/x509: golang: crypto/x509: Man-in-the-middle attacks via untrusted intermediate certificates |
| 🟠 High | [CVE-2026-25679](https://avd.aquasec.com/nvd/cve-2026-25679) | stdlib | v1.24.6 | 1.25.8, 1.26.1 | – | net/url: Incorrect parsing of IPv6 host literals in net/url |
| 🟠 High | [CVE-2026-27145](https://avd.aquasec.com/nvd/cve-2026-27145) | stdlib | v1.24.6 | 1.25.11, 1.26.4 | – | crypto/x509: golang: golang crypto/x509: Denial of Service via excessive processing of DNS SAN entri |
| 🟠 High | [CVE-2026-32280](https://avd.aquasec.com/nvd/cve-2026-32280) | stdlib | v1.24.6 | 1.25.9, 1.26.2 | – | crypto/x509: crypto/tls: golang: Go: Denial of Service vulnerability in certificate chain building |
| 🟠 High | [CVE-2026-32281](https://avd.aquasec.com/nvd/cve-2026-32281) | stdlib | v1.24.6 | 1.25.9, 1.26.2 | – | crypto/x509: golang: Go crypto/x509: Denial of Service via inefficient certificate chain validation |
| 🟠 High | [CVE-2026-32283](https://avd.aquasec.com/nvd/cve-2026-32283) | stdlib | v1.24.6 | 1.25.9, 1.26.2 | – | crypto/tls: golang: Go crypto/tls: Denial of Service via multiple TLS 1.3 key update messages |
| 🟠 High | [CVE-2026-33811](https://avd.aquasec.com/nvd/cve-2026-33811) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | net: golang: Go net package: Denial of Service via long CNAME response in LookupCNAME |
| 🟠 High | [CVE-2026-33814](https://avd.aquasec.com/nvd/cve-2026-33814) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | net/http/internal/http2: golang: golang.org/x/net: Go HTTP/2: Denial of Service via malformed SETTIN |
| 🟠 High | [CVE-2026-33818](https://avd.aquasec.com/nvd/cve-2026-33818) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | encoding/asn1: golang: Go encoding/asn1: Denial of Service via excessive recursion in Unmarshal |
| 🟠 High | [CVE-2026-39820](https://avd.aquasec.com/nvd/cve-2026-39820) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | net/mail: golang: Go net/mail: Denial of Service via crafted email inputs |
| 🟠 High | [CVE-2026-39821](https://avd.aquasec.com/nvd/cve-2026-39821) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | golang.org/x/net/idna: golang: net/http: golang.org/x/net/idna: Privilege escalation via incorrect P |
| 🟠 High | [CVE-2026-39822](https://avd.aquasec.com/nvd/cve-2026-39822) | stdlib | v1.24.6 | 1.25.12, 1.26.5, 1.27.0-rc.2 | – | golang: Go os.Root: Symlink following vulnerability allows directory traversal |
| 🟠 High | [CVE-2026-39836](https://avd.aquasec.com/nvd/cve-2026-39836) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | net: golang: Go net package: Denial of Service via NUL byte in Dial and LookupPort on Windows |
| 🟠 High | [CVE-2026-42499](https://avd.aquasec.com/nvd/cve-2026-42499) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | net/mail: golang: net/mail: Denial of Service via pathological email address parsing |
| 🟠 High | [CVE-2026-42504](https://avd.aquasec.com/nvd/cve-2026-42504) | stdlib | v1.24.6 | 1.25.11, 1.26.4 | – | mime: golang: Golang MIME: Denial of Service via maliciously-crafted MIME header |
| 🟠 High | [CVE-2026-56853](https://avd.aquasec.com/nvd/cve-2026-56853) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | net/http: golang: Go net/http: Unencrypted HTTP/2 connections vulnerable to Denial of Service |
| 🟠 High | [CVE-2026-56858](https://avd.aquasec.com/nvd/cve-2026-56858) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | html/template: golang: Go html/template: Cross-Site Scripting via pathological input |
| 🟠 High | [CVE-2026-56859](https://avd.aquasec.com/nvd/cve-2026-56859) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | encoding/xml: golang: Go: Denial of Service via XML decoding recursion depth issue |
| 🟠 High | [CVE-2026-56860](https://avd.aquasec.com/nvd/cve-2026-56860) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | net/url: golang: golang net/url: Denial of Service from quadratic complexity in path resolution |
| 🟠 High | [CVE-2026-56862](https://avd.aquasec.com/nvd/cve-2026-56862) | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | – | crypto/tls: golang: Golang crypto/tls: Denial of Service via indefinite KeyUpdate messages |
| 🟠 High | [CVE-2026-78667](https://avd.aquasec.com/nvd/cve-2026-78667) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: golang: golang: Denial of Service via crafted HTTP Range headers |
| 🟠 High | [CVE-2026-78669](https://avd.aquasec.com/nvd/cve-2026-78669) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: net/http/internal/http2: golang.org/x/net/http2: net/http: Denial of Service via excessive |
| 🟠 High | [CVE-2026-97031](https://avd.aquasec.com/nvd/cve-2026-97031) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | crypto/tls: golang: crypto/tls: Denial of Service via multiple ECH outer extension references |
| 🟡 Medium | [CVE-2026-61801](https://avd.aquasec.com/nvd/cve-2026-61801) | github.com/moby/sys/user | v0.1.0 | 0.4.1 | – | github.com/moby/sys/user: moby/sys/user: Denial of Service via crafted user or group database files |
| 🟡 Medium | [CVE-2025-47912](https://avd.aquasec.com/nvd/cve-2025-47912) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | net/url: Insufficient validation of bracketed IPv6 hostnames in net/url |
| 🟡 Medium | [CVE-2025-58183](https://avd.aquasec.com/nvd/cve-2025-58183) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | golang: archive/tar: Unbounded allocation when parsing GNU sparse map |
| 🟡 Medium | [CVE-2025-58185](https://avd.aquasec.com/nvd/cve-2025-58185) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | encoding/asn1: Parsing DER payload can cause memory exhaustion in encoding/asn1 |
| 🟡 Medium | [CVE-2025-58187](https://avd.aquasec.com/nvd/cve-2025-58187) | stdlib | v1.24.6 | 1.24.9, 1.25.3 | – | crypto/x509: Quadratic complexity when checking name constraints in crypto/x509 |
| 🟡 Medium | [CVE-2025-58188](https://avd.aquasec.com/nvd/cve-2025-58188) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | crypto/x509: golang: Panic when validating certificates with DSA public keys in crypto/x509 |
| 🟡 Medium | [CVE-2025-58189](https://avd.aquasec.com/nvd/cve-2025-58189) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | crypto/tls: go crypto/tls ALPN negotiation error contains attacker controlled information |
| 🟡 Medium | [CVE-2025-61723](https://avd.aquasec.com/nvd/cve-2025-61723) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | encoding/pem: Quadratic complexity when parsing some invalid inputs in encoding/pem |
| 🟡 Medium | [CVE-2025-61724](https://avd.aquasec.com/nvd/cve-2025-61724) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | net/textproto: Excessive CPU consumption in Reader.ReadResponse in net/textproto |
| 🟡 Medium | [CVE-2025-61725](https://avd.aquasec.com/nvd/cve-2025-61725) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | net/mail: Excessive CPU consumption in ParseAddress in net/mail |
| 🟡 Medium | [CVE-2025-61727](https://avd.aquasec.com/nvd/cve-2025-61727) | stdlib | v1.24.6 | 1.24.11, 1.25.5 | – | golang: crypto/x509: excluded subdomain constraint does not restrict wildcard SANs |
| 🟡 Medium | [CVE-2025-61728](https://avd.aquasec.com/nvd/cve-2025-61728) | stdlib | v1.24.6 | 1.24.12, 1.25.6 | – | golang: archive/zip: Excessive CPU consumption when building archive index in archive/zip |
| 🟡 Medium | [CVE-2025-61730](https://avd.aquasec.com/nvd/cve-2025-61730) | stdlib | v1.24.6 | 1.24.12, 1.25.6 | – | crypto/tls: Handshake messages may be processed at the incorrect encryption level in crypto/tls |
| 🟡 Medium | [CVE-2026-27142](https://avd.aquasec.com/nvd/cve-2026-27142) | stdlib | v1.24.6 | 1.25.8, 1.26.1 | – | html/template: URLs in meta content attribute actions are not escaped in html/template |
| 🟡 Medium | [CVE-2026-32282](https://avd.aquasec.com/nvd/cve-2026-32282) | stdlib | v1.24.6 | 1.25.9, 1.26.2 | – | golang: internal/syscall/unix: Root.Chmod can follow symlinks out of the root |
| 🟡 Medium | [CVE-2026-32288](https://avd.aquasec.com/nvd/cve-2026-32288) | stdlib | v1.24.6 | 1.25.9, 1.26.2 | – | archive/tar: golang: Go's archive/tar package: Denial of Service via maliciously-crafted archive |
| 🟡 Medium | [CVE-2026-32289](https://avd.aquasec.com/nvd/cve-2026-32289) | stdlib | v1.24.6 | 1.25.9, 1.26.2 | – | html/template: golang: html/template: Cross-Site Scripting (XSS) via improper context and brace dept |
| 🟡 Medium | [CVE-2026-39823](https://avd.aquasec.com/nvd/cve-2026-39823) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | html/template: golang: Go html/template: Cross-Site Scripting via improper URL escaping in meta tag |
| 🟡 Medium | [CVE-2026-39825](https://avd.aquasec.com/nvd/cve-2026-39825) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | net/http/httputil: golang: net/http/httputil: ReverseProxy forwards hidden query parameters, potenti |
| 🟡 Medium | [CVE-2026-39826](https://avd.aquasec.com/nvd/cve-2026-39826) | stdlib | v1.24.6 | 1.25.10, 1.26.3 | – | html/template: golang: html/template: Cross-site scripting due to incorrect script tag escaping |
| 🟡 Medium | [CVE-2026-42505](https://avd.aquasec.com/nvd/cve-2026-42505) | stdlib | v1.24.6 | 1.25.12, 1.26.5, 1.27.0-rc.2 | – | crypto/tls: golang: Go crypto/tls: Information disclosure in Encrypted Client Hello |
| 🟡 Medium | [CVE-2026-42507](https://avd.aquasec.com/nvd/cve-2026-42507) | stdlib | v1.24.6 | 1.25.11, 1.26.4 | – | net/textproto: golang: Golang net/textproto: Misleading error messages via input injection |
| 🟡 Medium | [CVE-2026-56866](https://avd.aquasec.com/nvd/cve-2026-56866) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: golang: golang: Cross-user response poisoning via desynchronized HTTP CONNECT connections |
| 🟡 Medium | [CVE-2026-78659](https://avd.aquasec.com/nvd/cve-2026-78659) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: golang.org/x/net/http2: golang: net/http: Denial of Service via HTTP/2 trailer header memo |
| 🟡 Medium | [CVE-2026-78660](https://avd.aquasec.com/nvd/cve-2026-78660) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: golang: golang.org/x/net/http2: net/http: HTTP response smuggling via malformed HTTP/2 fra |
| 🟡 Medium | [CVE-2026-78663](https://avd.aquasec.com/nvd/cve-2026-78663) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: net/http/internal/http2: golang: golang.org/x/net/http2: golang: flow control limit bypass |
| 🟡 Medium | [CVE-2026-94439](https://avd.aquasec.com/nvd/cve-2026-94439) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: golang: net/http: HTTP request smuggling via improper handling of HTTP/1 CONNECT responses |
| 🟡 Medium | [CVE-2026-94440](https://avd.aquasec.com/nvd/cve-2026-94440) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/textproto: mime/multipart: golang: golang: Denial of Service via memory limit bypass in multipar |
| 🟡 Medium | [CVE-2026-94448](https://avd.aquasec.com/nvd/cve-2026-94448) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | html/template: golang: golang: cross-site scripting via consecutive expressions in JavaScript templa |
| 🟡 Medium | [CVE-2026-97030](https://avd.aquasec.com/nvd/cve-2026-97030) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | html/template: golang: html/template: Cross-site scripting via improper escaping of yield keyword |
| 🟡 Medium | [CVE-2026-97032](https://avd.aquasec.com/nvd/cve-2026-97032) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | net/http: net/http/internal/http2: golang: golang.org/x/net/http2: net/http: Denial of Service via c |
| 🔵 Low | [CVE-2025-58186](https://avd.aquasec.com/nvd/cve-2025-58186) | stdlib | v1.24.6 | 1.24.8, 1.25.2 | – | golang.org/net/http: Lack of limit when parsing cookies can cause memory exhaustion in net/http |
| 🔵 Low | [CVE-2026-27139](https://avd.aquasec.com/nvd/cve-2026-27139) | stdlib | v1.24.6 | 1.25.8, 1.26.1 | – | os: FileInfo can escape from a Root in golang os module |
| 🔵 Low | [CVE-2026-56857](https://avd.aquasec.com/nvd/cve-2026-56857) | stdlib | v1.24.6 | 1.26.9, 1.27.2 | – | os: golang: golang: Directory traversal via Windows junction handling |
| ⚪ Unknown | [CVE-2026-39824](https://avd.aquasec.com/nvd/cve-2026-39824) | golang.org/x/sys | v0.1.0 | 0.44.0 | – | Invoking integer overflow in NewNTUnicodeString in golang.org/x/sys/windows |

### A.4 Repository: misconfiguration and secret checks

| Target | Type | Checks passed | Failures |
|---|---|:-:|:-:|
| backend/Dockerfile | dockerfile | 27 | 0 |
| frontend/Dockerfile | dockerfile | 27 | 0 |

Secrets detected in the repository: **0**.

