#!/usr/bin/env bash
# Run on the dedicated Ubuntu test VM as root. The API is reachable via SSH.
set -euo pipefail
cd /tmp
curl --fail --retry 3 --location --output opensoom-k3s https://github.com/k3s-io/k3s/releases/download/v1.34.3%2Bk3s1/k3s
echo 'f95350e3997165974d1d1406f01aabaf869aed7ca790cc2d83a92a82f26a06c5  opensoom-k3s' | sha256sum --check
install -m 0755 opensoom-k3s /usr/local/bin/k3s
# Pods must reach the API via the private node address. Drop every TCP/6443
# connection arriving on the host's uplink, including via GCE external NAT.
cat > /usr/local/sbin/opensoom-private-k3s-api <<'GUARD'
#!/usr/bin/env bash
set -euo pipefail
uplink=$(ip route show default | awk 'NR == 1 {print $5}')
test -n "$uplink"
iptables -C INPUT -i "$uplink" -p tcp --dport 6443 -j DROP 2>/dev/null ||
  iptables -I INPUT 1 -i "$uplink" -p tcp --dport 6443 -j DROP
GUARD
chmod 0755 /usr/local/sbin/opensoom-private-k3s-api
cat > /etc/systemd/system/opensoom-k3s.service <<'UNIT'
[Unit]
Description=openSoom private single-node Kubernetes test host
After=network-online.target
Wants=network-online.target
[Service]
Type=notify
Delegate=yes
KillMode=process
Restart=on-failure
ExecStartPre=/usr/local/sbin/opensoom-private-k3s-api
ExecStart=/usr/local/bin/k3s server --disable=traefik,servicelb,metrics-server,local-storage --bind-address=0.0.0.0 --write-kubeconfig-mode=600
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable opensoom-k3s.service
systemctl restart opensoom-k3s.service
k3s kubectl wait --for=condition=Ready node --all --timeout=180s
