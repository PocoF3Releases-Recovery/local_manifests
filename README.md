# Native recovery integration

Use the normal PocoF3Releases ROM repositories for `frameworks/base`,
`device/xiaomi/alioth` and `device/xiaomi/sm8250-common`. This repository stores
only their recovery additions as authored mail patches. Recovery-only dependency
repositories remain selected by `poco-native-recovery.xml`.

Place this repository at `.repo/local_manifests`, retaining your ROM device and
framework overrides alongside it. If that directory already contains loose XML
files, copy this repository's tracked files into it while preserving the existing
ROM overrides; do not clone over or delete the directory. The apply script and
`patches/` must be present together. After each sync, apply the recovery patches:

```sh
repo sync -j50
python3 .repo/local_manifests/apply-recovery-patches.py --check
python3 .repo/local_manifests/apply-recovery-patches.py
. build/envsetup.sh
lunch lineage_alioth-cp2a-user
m evolution
```

The apply command is idempotent, preserves commit authors through `git am`, checks
patch hashes and preflights all projects with private indexes. It rejects dirty
checkouts, unfinished Git operations and incompatible patches. It does not fetch,
reset, push or modify any security setting. If upstream changes the affected code,
review and refresh the patches instead of forcing them. Applied commits are local;
keep the ROM repositories free of recovery-specific commits when pushing ROM work.
A later `repo sync` may drop local patches or rebase them; rerun the check/apply
command and resolve any repo-reported conflict before building.

The normal ROM product remains `lineage_alioth-cp2a-user`. Use `m installclean`
for release preparation when needed, not for every incremental recovery change.
