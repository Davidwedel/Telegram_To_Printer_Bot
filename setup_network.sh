#!/usr/bin/env bash
set -euo pipefail

# Setup static IP on eth0 and DHCP server for printer LAN
# Run once: sudo bash setup_network.sh

ETH_IF="eth0"
STATIC_IP="192.168.0.1/24"
DHCP_RANGE="192.168.0.10,192.168.0.50,24h"

echo "==> Configuring static IP $STATIC_IP on $ETH_IF"

# Persist static IP via dhcpcd (standard on Raspberry Pi OS)
if ! grep -q "^interface $ETH_IF" /etc/dhcpcd.conf 2>/dev/null; then
    cat >> /etc/dhcpcd.conf <<EOF

# Printer LAN — added by setup_network.sh
interface $ETH_IF
static ip_address=$STATIC_IP
nogateway
EOF
    echo "    Added static IP config to /etc/dhcpcd.conf"
else
    echo "    Static IP config already present in /etc/dhcpcd.conf"
fi

# Bring up the interface now
ip addr flush dev "$ETH_IF" 2>/dev/null || true
ip addr add "$STATIC_IP" dev "$ETH_IF" 2>/dev/null || true
ip link set "$ETH_IF" up

echo "==> Installing dnsmasq"
apt-get update -qq
apt-get install -y -qq dnsmasq

echo "==> Configuring dnsmasq for $ETH_IF"
cat > /etc/dnsmasq.d/printer-lan.conf <<EOF
# DHCP server for printer LAN — added by setup_network.sh
interface=$ETH_IF
bind-interfaces
dhcp-range=$DHCP_RANGE
EOF

echo "==> Restarting dnsmasq"
systemctl enable dnsmasq
systemctl restart dnsmasq

echo "==> Done. Printer LAN is ready on $ETH_IF ($STATIC_IP)"
echo "    Plug in the printer and check: cat /var/lib/misc/dnsmasq.leases"
