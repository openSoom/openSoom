#!/usr/bin/env bash
# Build x86-64 Linux native service bundles from the verified ETSI commit.
set -euo pipefail
: "${SOURCE:?Existing ETSI Git checkout}" "${OUTPUT:?Build directory outside that checkout}"
here=$(cd "$(dirname "$0")" && pwd)
rev=8c66f08e443be174f109fe2ac645247c9afcd449
mkdir -p "$OUTPUT"
out=$(cd "$OUTPUT" && pwd)
scratch=$(mktemp -d "$out/etsi-src.XXXXXXXX")
git -C "$SOURCE" archive "$rev" | tar xf - -C "$scratch"
(cd "$scratch" && patch -p1 < "$here/couch-credentials.patch" && patch -p1 < "$here/precreated-namespace.patch")
for name in meep-app-enablement meep-iot meep-sss meep-sandbox-ctrl meep-platform-ctrl meep-virt-engine; do
  dir="$out/$name"
  mkdir -p "$dir/user-api" "$dir/api"
  if [[ -d "$scratch/go-apps/$name/api" ]]; then
    cp -R "$scratch/go-apps/$name/api/." "$dir/api/"
  fi
  (cd "$scratch/go-apps/$name" && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -mod=readonly -trimpath -o "$dir/server" .)
  cat > "$dir/Dockerfile" <<'IMAGE'
FROM scratch
COPY server /server
COPY api /api
COPY user-api /user-api
ENTRYPOINT ["/server"]
IMAGE
done
cat > "$out/meep-virt-engine/Dockerfile" <<'IMAGE'
FROM scratch
COPY server /server
COPY helm /bin/helm
ENV PATH=/bin
ENV HELM_DRIVER=configmap
ENTRYPOINT ["/server"]
IMAGE
