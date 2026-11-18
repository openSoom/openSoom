#!/usr/bin/env bash
# On the private Linux test host, from the output of package-services.sh.
set -euo pipefail
curl --fail --location --silent --show-error -o helm.tgz https://get.helm.sh/helm-v3.10.1-linux-amd64.tar.gz
echo 'c12d2cd638f2d066fec123d0bd7f010f32c643afdf288d39a4610b1f9cb32af3  helm.tgz' | sha256sum --check
tar -xOf helm.tgz linux-amd64/helm > meep-virt-engine/helm
chmod 0755 meep-virt-engine/helm
for app in meep-app-enablement meep-iot meep-sss meep-sandbox-ctrl meep-platform-ctrl meep-virt-engine; do
  tag=8c66f08e
  case "$app" in
    meep-sandbox-ctrl) tag=8c66f08e-private-auth ;;
    meep-virt-engine|meep-platform-ctrl) tag=8c66f08e-private ;;
  esac
  image="opensoom/$app:$tag"
  sudo docker build --quiet -t "$image" "$app"
  sudo docker save "$image" | sudo k3s ctr images import -
done
