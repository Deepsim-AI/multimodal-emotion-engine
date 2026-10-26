# MEE Release Signing & Verification Pipeline — Current State Analysis

**Task context:** Forgejo/Hub self-hosting transition (Oct 2026).
**Purpose:** Document exactly how MEE releases are signed, published, and verified
*TODAY*, so the production release path stays working throughout the transition.
**Decision (owner, 2026-10-23):** Option (i) — retain GitHub Actions for release
signing (existing GitHub OIDC keyless Sigstore flow) *unchanged initially*.
Forgejo/Hub are for dev repos, review, tests, self-hosted builds, and artifact
distribution; they do NOT replace the signing identity.

---

## 1. What is signed (authoritative: `.github/workflows/release.yml`, 132 lines)

Workflow `release-sigstore-sign` triggers on `push` tags `v*` and
`workflow_dispatch`. Permission: **`id-token: write`** (OIDC for keyless
signing) + `contents: write` (publish release).

Signed artifacts (step "Sign artifacts with Sigstore (keyless)"):
- `MEE_RELEASE_MANIFEST.json`  (SHA-256 manifest — primary anchor)
- `MEE_INTEGRITY_HASHES.txt`   (integrity anchor of licensing files — Decision #3)
- `dist/*.whl`                 (the wheel)
- `dist/*.tar.gz`              (the sdist)

Signing mechanism: **`sigstore sign <artifact>`** (sigstore-python 3.x, CI-only
dep, not a runtime dep). Identity is the **GitHub runner's OIDC workload
identity** (Fulcio keyless) — *no long-lived signing key*.

## 2. Anchors (two-layer)
- **Primary anchor:** `MEE_RELEASE_MANIFEST.json` — `{"artifacts":[{name,sha256}],
  "task":"TASK_MEE_020","scheme":"sigstore-fulcio-keyless"}`. Published as a
  release asset.
- **Secondary anchor:** `MEE_INTEGRITY_HASHES.txt` — deterministic SHA-256 of
  critical licensing files (from `tools/generate_integrity_anchor.py`, backed by
  `mee.licensing.integrity.generate_anchor_file`). **Embedded inside the wheel's
  `<pkg>.dist-info/`** for offline verification.

## 3. How signatures/bundles are published
- `sigstore sign` emits a single **`<artifact>.sigstore.json`** bundle per
  artifact (sigstore 3.x format; NOT a directory).
- Published via `softprops/action-gh-release@v2` to the **GitHub release**:
  `dist/*.whl`, `dist/*.tar.gz`, `MEE_RELEASE_MANIFEST.json`,
  `MEE_INTEGRITY_HASHES.txt`, `*.sigstore.json`.
- **Distribution today = GitHub Releases only** (PyPI name is squatted; no
  PyPI publication).

## 4. How customers verify (`tools/verify_release.sh`, PRESERVE EXACTLY)
Two independent checks, both required for a full PASS:
1. **Integrity:** wheel `sha256sum` matches the manifest entry.
2. **Authenticity/provenance:**
   ```
   sigstore verify github \
     --certificate <wheel>.crt \
     --bundle <wheel>.sigstore.json \
     --repository Deepsim-AI \
     --name multimodal-emotion-engine \
     <wheel>
   ```
   with a fallback to `sigstore verify github --bundle <bundle> <wheel>`
   (repo pin not enforced). Verification reaches the **public Sigstore CA
   (Fulcio) + Rekor transparency log** — the *only* network use.
- Honest scope note (C3): verifies distribution provenance + integrity; NOT a
  license check (that's the runtime `mee-lic verify` gate).
- **Signing identity the customer depends on:** `Deepsim-AI / multimodal-emotion-engine`
  GitHub repo, GitHub Actions provenance, Fulcio keyless cert.

## 5. Transition invariants (owner directive)
- **Do NOT change `release.yml`** until this analysis is complete and the
  production path is confirmed still-working.
- Moving artifacts to Forgejo/Hub does **not** change their trustworthiness —
  signatures + verification must remain **independently verifiable** against
  the public Sigstore root (Fulcio + Rekor), regardless of where the bytes are
  hosted.
- **Do NOT deploy a self-hosted Fulcio CA** and **do NOT introduce a long-lived
  Cosign key** now.
- Server deployment (Forgejo runner) and signing migration are **separate
  stages**; do not enable CI runners merely to resolve signing.

## 6. Future self-hosting project — Option (ii) (NOT to start now)
If we later move signing off GitHub OIDC, the self-hosted Fulcio design MUST
specify and resolve:
- **OIDC issuer:** a self-hosted IdP (e.g., Forgejo OIDC / Authelia / Zitadel)
  that issues tokens the runner workflow can present to the Fulcio client.
- **CA-key protection:** how the Fulcio CA signing key (and the Rekor
  transparency-log key) are generated, held (HSM / encrypted KMS), rotated,
  and who can access them.
- **Transparency logging:** a Rekor instance (or delegated transparency log)
  the signatures anchor to; how log entries are made publicly auditable.
- **Trust-root distribution:** customers currently verify against the *public*
  Sigstore root. A private CA means distributing a new trust root (CA bundle +
  Rekor public key) to every customer and updating `verify_release.sh` to
  pin it — a **customer migration**, not a drop-in.
- **Customer migration requirements:** versioned, announced change; dual-accept
  window (old GitHub-anchored + new self-hosted bundles); tooling to install the
  new trust root; deprecation timeline for the old identity.
