# TELCO FLEET REALITY — how the existing fleet infrastructure supports or conflicts with adding cellular backhaul to remote base stations

**Author:** Hermes subagent (delegated assessment)
**Date:** 2026-10-14
**Method:** read-only inspection of the live fleet over its own remote-access path. No configuration was changed.
**Inputs read:** `~/CONSULT-BRIEF-telco-backhaul.md`, `worktrees/e80-lr2021-audit/docs/adr/100-tollgate-over-fips-mesh-udp.md`, `worktrees/e80-lr2021-audit/docs/adr/071-ground-station-gateway-design-basis.md`, `repos/hermes-orchestration/inventory.ini`, `~/.ssh/config`, live node state.

**Honesty legend:** **[MEASURED]** = a command was run and its output is quoted. **[MODELLED]** = derived arithmetically from measured values, derivation shown. **[GUESSED]** = not observed; explicitly flagged.

---

## 0. Headline corrections to the brief (read this first)

The brief states two things that the live fleet contradicts:

| Brief claim | Measured reality |
|---|---|
| "The only cellular object anywhere in the fleet is an **LTE modem in a laptop** (Sierra EM7455, `/dev/ttyUSB0-2`)" | **FALSE — there are at least TWO cellular modems in the fleet.** CobradorWave carries the Sierra EM7455; **x280 carries its own Fibocom L830-EB-00 LTE modem** with a registered `wwan0` netdev and `/dev/cdc-wdm1`. **[MEASURED]** |
| "There is ONE known LTE device in the fleet" | Correct as to *station-ready* hardware (none), but wrong as a count of modems. x280's is on the node the manager session itself runs on. **[MEASURED]** |

Everything else in the brief (no base-station cellular design, PCBA is control/bias only, adr-071/100 as stated) is consistent with what I read.

---

## 1. Measured current remote-access path, per node

**All seven fleet nodes were reachable during this assessment. None was unreachable.** **[MEASURED]**

```
$ for h in cobrador dq05 hermes-nvme testserver2 x240 t440; do ssh ... $h 'hostname; echo REACHED'; done
hostname → CobradorWave / c03rad0r-DQ05proplus / hermes / testserver2 / x240 / t440   (all exit 0)
```

### 1.1 The primary path is FIPS over IPv6, keyed by `id_fleet`

`~/.ssh/config` is Ansible-generated and is the decisive artifact:

```
# BEGIN ANSIBLE MANAGED fips ssh aliases
# Managed by Ansible - role 03-fips-mesh. Do not edit in place.
# One Host alias per fleet node, resolved via the .fips mesh DNS over IPv6.
Host cobrador
    HostName cobrador.fips
    User c03rad0r
    AddressFamily inet6
    IdentityFile ~/.ssh/id_fleet
```

**Every fleet node alias resolves to a `.fips` name, forces `AddressFamily inet6`, and uses `~/.ssh/id_fleet`.** Name resolution is local, not DNS-over-WAN:

```
$ getent hosts cobrador.fips
fd97:77d4:cd27:a6ae:1b29:e92e:fd96:dee8 cobrador.fips
$ getent hosts dq05.fips
fdb0:bf34:d648:96ac:f65a:3fd6:358:710b dq05.fips
$ getent hosts x280.fips
fd36:3c0f:d6f:8029:ea50:958b:672e:bb0 x280.fips
```

Addresses are in `fd00::/8` ULA space, derived from the node npub (`/etc/fips/hosts` maps `cobrador npub1eak9…`, `x280 npub1ye3t…`, …). **[MEASURED]**

### 1.2 Per-node path table

| Node | Role | FIPS `fips0` addr | FIPS daemon | NetBird | LAN mangle | Measured reachable |
|---|---|---|---|---|---|---|
| **CobradorWave** | main gateway host | `fd97:77d4:…:dee8` | active | **active**, `100.90.101.9` | `192.168.2.26` (`AX88179B`), + second WAN `10.63.101.201` | yes |
| **dq05** | mini-PC, board hub | `fdb0:bf34:…:710b` | active | **active**, `100.90.22.201` | `192.168.2.38` (wired, preferred) / `.32` (wifi) | yes (slow: exit 124 on a long probe; short sshes succeed) |
| **hermes-nvme** | public VPS, build runner | `fdb8:d8ff:…:afd9` | active | active | `23.182.128.219` (public) | yes |
| **testserver2** | public VPS, relay | `fdfd:c0e5:…:7149` | active | active | `23.182.128.51` (public) | yes |
| **x280** | this manager session's host | `fd36:3c0f:…:bb0` | active | **ABSENT** | `192.168.2.20` (wifi) / `.13`, `.12` (two USB NICs) | yes (local) |
| **x240** | laptop, heavy disk | `fd00:6a8e:…:f220` | active | **ABSENT** | `192.168.2.25` | yes |
| **t440** | laptop | `fd59:2944:…:e489` | active | **ABSENT** | `192.168.2.21` | yes |

```
$ fipsctl show status   # on x280
"peer_count": 8, "is_leaf_only": false, "estimated_mesh_size": 849
```

**[MEASURED]** — this is a live, multi-hop, routed mesh, not a flat LAN: x280's spanning-tree parent is the *external* peer `andre` at depth 4:

```
$ fipsctl show tree
"depth": 4, "is_root": false,
"parent": "918fb55778f3527ee21fdbd6ab868f74", "parent_display_name": "andre",
```

### 1.3 Inbound SSH posture on every node

```
$ sshd -T
port 22
permitrootlogin no
pubkeyauthentication yes
passwordauthentication no
kbdinteractiveauthentication no
permitemptypasswords no
gatewayports no
```

Same posture on CobradorWave. Auth is **public-key only, no root login, no gateway ports**. **[MEASURED]**

### 1.4 The FIPS mesh has an explicit host firewall with a strict allowlist

```
/etc/fips/peers.deny:   ALL
/etc/fips/peers.allow:  npub1eak9… (cobrador) … npub1ye3t… (x280) … 9 npubs total
```

```
# /etc/fips/fips.nft
# Polices ONLY the fips0 mesh interface — every packet not arriving
# on fips0 returns immediately…
#   INBOUND on fips0:   DROP everything except —
#                         • replies to outbound flows we initiated
#                         • ICMPv6 echo-request (ping6 reachability)
#                         • rules in /etc/fips/fips.d/*.nft drop-ins
```

Mesh-reachable services are exactly two drop-ins:

```
# /etc/fips/fips.d/ssh.nft      → tcp dport 22 accept
# /etc/fips/fips.d/hermes.nft   → tcp dport 8443, 3001, 8200, udp/tcp dport 53
```

**[MEASURED]** — the mesh is **default-deny inbound with a cryptographic peer allowlist**; only SSH + the fleet management ports are exposed on `fips0`.

### 1.5 NetBird is a live fallback, not the primary — and it is metered

```
$ netbird status        # cobrador
Management: Connected
FQDN: cobradorwave.netbird.cloud
NetBird IP: 100.90.101.9/16
```
```
$ netbird status -d    # cobrador, peer dq05
NetBird IP: 100.90.22.201
Connection type: P2P
Last WireGuard handshake: 1 minute, 59 seconds ago
Transfer status (received/sent) 492.8 MiB/995.8 MiB
```

**[MEASURED]** NetBird is installed and connected on *only* `cobrador`, `dq05`, `hermes-nvme`, `testserver2`. It is **ABSENT on x240, t440, x280**:

```
$ ssh x240 'command -v netbird' → netbird ABSENT
$ ssh t440 'command -v netbird' → netbird ABSENT
$ which netbird                 → (x280: not found)
```

The fleet's own IaC names it a fallback and prices it in metered bytes:

```
# roles/13-fleet-node-base/defaults/main.yml
# the metered path. Enabled per-host (cobrador); NetBird is the manual fallback.
# same-LAN transfers don't hair-pin through the .fips mesh (metered WAN).
```
```
# roles/01-node-hardening/defaults/main.yml
# NetBird — retired as the primary transport (ADR-018); kept only as an explicit
# fallback. FIPS (role 03-fips-mesh) is the fleet mesh now.
```

**NetBird traffic is measured moving real bytes (1.5 GB on the dq05 peer).** That is metered WAN spend, and it is why the fleet deliberately prefers FIPS. **[MEASURED]**

### 1.6 The fleet's WAN is a metered home gateway with a hard 350 GB/month budget

```
$ ip route show default            # x280
default via 192.168.2.1 dev enx00e04c36043e proto dhcp src 192.168.2.12 metric 100
$ ip -6 route show default         # cobrador, dq05, x240, t440 all:
default via fe80::ea8f:6fff:fedf:9e11 dev … proto ra
```
```
# roles/56-bandwidth-meter/defaults/main.yml
# 56-bandwidth-meter — meter the metered gateway + attribute usage per
# interface/service/container, and drive the 350 GB/month budget guard.
bandwidth_meter_budget_gb: 350
bandwidth_meter_warn_pct: 70
bandwidth_meter_pause_pct: 80
```

**[MEASURED]** — every node including both laptops sits behind one metered CGNAT-ish home router at `192.168.2.1`. CobradorWave additionally has a **second, active WAN** on `10.63.101.201/24` (metric 201) over a USB ASIX AX88179B NIC — that is a second upstream, not cellular (the NIC identifies as `ID_MODEL=AX88179B`, `ID_VENDOR=ASIX`). **[MEASURED]**

Public egress IP today:

```
$ curl -s4 https://ifconfig.co                       → 80.187.85.172
$ curl -s6 https://ifconfig.co                       → 2a01:599:11d:2324:2e0:4cff:fe36:43e   (Deutsche Telekom)
$ ssh cobrador 'curl -s4 https://ifconfig.co'        → 80.187.85.172     (same IPv4 — one shared NAT)
$ ssh cobrador 'curl -s6 https://ifconfig.co'        → 2a01:599:11d:2324:e9d1:c7d3:bc61:3d36
```

**[MEASURED]** — one IPv4 for the whole household (NAT), but **every node gets its own public IPv6** via RA from the home router. This is the single most important network fact for the telco question (see §5).

---

## 2. Does any cellular capability already exist anywhere? — YES, on two nodes

### 2.1 CobradorWave — Sierra EM7455 (the brief's known one)

```
$ mmcli -m 0
  Hardware | manufacturer: Sierra Wireless, Incorporated
           |        model: Sierra Wireless EM7455 Qualcomm Snapdragon X7 LTE-A
           |     firmware: SWI9X30C_02.33.03.00
           | drivers: qcserial, cdc_mbim
           | primary port: cdc-wdm0
           |     ports: cdc-wdm0 (mbim), ttyUSB1 (gps), ttyUSB2 (at),
           |            wwp0s20f0u6i12 (net)
           |  ignored ports: ttyUSB0 (qcdm)
  Status   | state: failed
           | failed reason: sim-missing
           | power state: low
  Modes    | current: allowed: 3g, 4g; preferred: 4g
  Bands    | supported: utran-1…8, eutran-1,2,3,4,5,7,8,12,13,20,25,26,41
  IP       | supported: ipv4, ipv6, ipv4v6
  3GPP     | imei: 015105005594866
```

and, in the same session, the SIM slot:

```
$ mmcli -m 0 --sim 0
  Properties | active: yes
             |  iccid: 89470000181017073419
```

**[MEASURED]** Note the internal contradiction, recorded rather than resolved: `state: failed / failed reason: sim-missing` while `--sim 0` reports `active: yes` with an ICCID. **Conclusion: the modem is enumerated, driver-bound (`cdc_mbim`), and MODE-capable of LTE Cat-class operation, but has no working data bearer.** Whether the slot is physically empty, the SIM is deactivated, or the "slot 1" path is a ghost object produced by ModemManager cannot be settled from here. **GUESSED (flagged):** the ICCID read is a cached/stale property; the decisive failure is `sim-missing`.

`wwan0` does not exist on CobradorWave and no bearer is up:

```
$ ssh cobrador 'ip -br addr show wwan*'
Device "wwan*" does not exist.
```

### 2.2 x280 — Fibocom L830-EB-00 — **NOT IN THE BRIEF**

```
$ lsusb
Bus 001 Device 004: ID 2cb7:0210 Fibocom L830-EB-00 LTE WWAN Modem

$ ip -br link
wwan0            DOWN           7a:9e:6a:fd:35:b8 <BROADCAST,MULTICAST,NOARP>

$ udevadm info … /sys/class/net/wwan0
E: ID_MODEL=L830-EB-00
E: ID_VENDOR=FIBOCOM
E: ID_SERIAL=FIBOCOM_L830-EB-00_004999010640000
E: ID_NET_DRIVER=cdc_mbim
E: ID_MM_CANDIDATE=1

$ dmesg | grep -iE 'cdc_mbim|L830|wwan'
usb 1-6: Product: L830-EB-00
cdc_mbim 1-6:1.0: cdc-wdm1: USB WDM device
cdc_mbim 1-6:1.0 wwan0: register 'cdc_mbim' at usb-0000:00:14.0-6, CDC MBIM, 7a:9e:6a:fd:35:b8
```

**A second, never-mentioned LTE modem. The kernel binds it, registers a `wwan0` netdev, and the interface is administratively DOWN with no SIM/bearer brought up.** **[MEASURED]**

### 2.3 Fleet-wide cellular inventory (measured, one pass per node)

| Node | modem hardware | `wwan*` iface | ModemManager | `mmcli -L` |
|---|---|---|---|---|
| CobradorWave | Sierra EM7455 (USB) | none | **active** | `Modem/0 … failed: sim-missing` |
| **x280** | **Fibocom L830-EB-00 (USB)** | **`wwan0` DOWN** | **inactive (not installed)** | `mmcli: command not found` |
| dq05 | none | none | active | `No modems were found` |
| hermes-nvme | none | none | inactive | not installed |
| testserver2 | none | none | inactive | not installed |
| x240 | none | none | inactive | not installed |
| t440 | none | none | active | `No modems were found` |

Probe that produced it:

```
-- wwan ifaces:  ip -br link | grep -iE 'wwan|usb[0-9]'
-- cdc-wdm/ttyUSB:  ls /dev/cdc-wdm* /dev/ttyUSB* /dev/wwan*
-- mmcli:  mmcli -L
-- ModemManager unit:  systemctl is-active ModemManager
```

**[MEASURED]** Additional detail: x240 and t440 report `/dev/ttyUSB0` (plain USB-serial adapters, no modem in `lsusb`); dq05 also reports `wwan` but enumerated as a `modemmanager` *unit* is active on both dq05 and t440 while `mmcli` finds zero modems. Only dq05 has the full modem toolchain (`libmbim`/`libqmi`/`ModemManager` present); **x280 has none of it** (`dpkg -l | grep -icE 'libmbim|libqmi|modemmanager'` → `0`), so bringing x280's modem up requires installing ModemManager + libmbim first.

### 2.4 Two SIM slots of SIM-adjacent hardware already exist physically

x280's `lsusb` also shows:

```
Bus 001 Device 002: ID 058f:9540 Alcor Micro Corp. AU9540 Smartcard Reader
```
**[MEASURED]** — a smartcard reader, *not* a SIM slot; listed so it is not mistaken for one.

**Bottom line for (2):** cellular *hardware* already exists on two fleet nodes but **no node anywhere has a working cellular data path**, and **no node has any cellular configuration** (no ModemManager config on x280, no `NetworkManager`, no `pppd`, no `/etc/ppp` on x280, no `wwan` policy in Ansible).

---

## 3. Does the "internet gateway" ground function exist today? — NO, but a full prototype of the *hard half* exists and is running

### 3.1 It absolutely does not exist for the base station

The station's own record says what it is, and the design program is not consolidated:

> **ADR-071:** the ground station is "a full-duplex **INTERNET GATEWAY** through the balloon as a bent pipe".

And the program-state analysis is blunt:

> `docs/analysis/PROGRAM-GAP-ANALYSIS.md`: "**The design program is essentially NOT consolidated.** All of the ground-station ADRs live only on branches; main carries the flight-board ADR line (up to 065) and nothing of the ground station."

**[MEASURED]** (file content read). The state also confirms no board exists:

| Artifact | State |
|---|---|
| Schematic (`.kicad_sch`) | ❌ does not exist |
| Netlist / SKiDL source | ❌ does not exist |
| Board / placement / routing | ❌ does not exist |
| Gerbers | ❌ |

`~/PLAN-base-station-board.md` confirms: "STAGE 1–2 DRAFT — **AWAITING OPERATOR APPROVAL**" and "**Gate statement:** no board work begins until Stage 1's netlist is reviewed and accepted." **[MEASURED]**

**There is no NAT/router/PPP setup for a station, no station host computer, and no station IP stack.** A fleet-wide search for a station host finds none:
```
$ grep -rn -iE 'ground station (computer|host|pc)|station computer|shack computer|mini ?pc' docs/
(none)
```
**[MEASURED]** — no station-host design exists. Per the brief, the PCBA is control/bias/telemetry only (RP2040 + detector + VGA + bias tee + buck; "**no host CPU, no networking, no OS, no PCIe/USB host, and no cellular anything**"). That is consistent with everything I found.

### 3.2 BUT: the fleet already built and runs a mesh→clearnet **exit gateway** — the inverse of the station's problem

This is the single most consequential find for the operator's question, and it is not mentioned in the brief.

```
$ ssh dq05 'docker ps --format "{{.Names}} | {{.Status}}"'
fips-exit-agent-1 | Up 23 hours
fips-exit-captive-1 | Up 23 hours
fips-exit-unbound-1 | Up 23 hours
fips-exit-backend-backend-1 | Up 23 hours
fips-exit-backend-db-1 | Up 23 hours (healthy)
```

**[MEASURED]** — the stack is **live on dq05 right now** (23 h uptime). `~/repos/fips-exit-gate` on dq05 is a Go project. Its own README states the purpose:

> "A **paid internet-exit service for the [fips](https://github.com/jmcorgan/fips) mesh network**. fips clients are IPv6-only (fd00::/8) and their address is cryptographically derived from their nostr identity (npub), so the exit authenticates by **source address alone** — the SOCKS5 handshake stays credential-free and every stock client works unmodified. … Egress is **modular**, offered as per-port services behind one shared gate and one shared balance, each metered at its own rate: **Connectivity** (`:1080`) reaches clearnet **and** `.onion`, and **Privacy** (`:1081`) forces all traffic through Tor."

Its component table (measured, file read):

| Component | What it does |
|---|---|
| `exit/` | Dante `sockd` SOCKS5 egress, **egress-only (blocks fd00::/8, RFC1918, loopback, metadata)**, source-address auth |
| `dispatch/` | Client-facing SOCKS5 on `:1080`, routes `.onion`→Tor, rest→Dante |
| `captive/` | Answers **unauthorized** clients with HTTP 302 to the paid portal |
| `agent/` | Reconciles the nftables `authorized` set from the backend, **meters per-(client,service) byte counters**, enforces quota cutoffs; "**portable to OpenWrt**" |
| `backend/` | Go + Postgres control plane, nostr login, BTCPay payment webhook |

And a recorded, verified end-to-end demonstration exists (`state/kanban/boards/devops-infra/attachments/t_ffbe94ff/E4-verification-evidence.md`, 2026-09-09, host DQ05):

```
## 5. AUTHORIZED client -> clearnet (HTTP@ 200, exit public IP)
Also: `curl --socks5-hostname "[fdce:…:5eb7]:1080" https://ifconfig.co` -> `80.187.85.11`
## 6. UNAUTHORIZED client -> captive 302 (after admin revoke)
## 7. Metering — per-(client,service) byte counters increment
set acct { type ipv6_addr . inet_service, elements = { fd97:…:dee8 . 1080 counter packets 306 bytes 94461 } }
## 8. Agent reports usage to backend (volume entitlement consumed)
 volume | 50000000000 | 60873
```

**[MEASURED]** (evidence artifact read). **This is a working, metered, payment-gated IPv6-mesh→IPv4-clearnet relay with captive-portal fallback for unauthorized clients.** It is architecturally the exact machinery the operator's "relay internet from a station with reception to one without" sentence needs.

### 3.3 …but the gate is NOT currently armed

The exit stack is up, but the enforcement path is not:

```
$ ssh dq05 'sudo nft list table inet fips_exit'
Error: No such file or directory
list table inet fips_exit
$ ssh dq05 'ss -tlnp | grep -E ":(1080|1081)"'
NO LISTENER on 1080/1081
$ ssh dq05 'ls ~/repos/fips-exit-gate/deploy/'
docker-compose.yaml  services.conf  render-nftables.sh  allowlist.txt  tor/  unbound.conf …
$ ssh dq05 'cat ~/repos/fips-exit-gate/deploy/services.conf'
clearnet 1080
# tor 1081     ← commented out
```

Cross-checked by an independent TCP probe from x280 into the mesh:

```
$ python3 socket probe to fdb0:bf34:…:710b:1080  → TimeoutError: timed out
$ python3 socket probe to fd97:77d4:…:dee8:22    → OPEN
$ python3 socket probe to fdb8:d8ff:…:afd9:2121  → TimeoutError: timed out
$ python3 socket probe to fdfd:c0e5:…:7149:8443  → ConnectionRefusedError: [Errno 111]
```

**[MEASURED]** — the exit stack's control containers run, but **no nft gate table and no SOCKS listener on 1080 exist.** The compose override that ran in the E2E evidence (`fips-exit-exit-clearnet-1`, `fips-exit-dispatch-1`) is **not part of the currently-running set** — only `agent`, `captive`, `unbound`, `backend`, `db`. So: the code and the proof exist; **the live deployment has regressed to a partial set and the actual exit path is down.**

Note also: `nft list ruleset` on dq05 shows masquerade rules only for Docker bridges and libvirt, plus `iifname "wt0" tcp dport 22 accept` (NetBird) — **no `oifname <wan> masquerade` for the fips exit path.** **[MEASURED]**

### 3.4 Verdict for (3)

| Function | Exists today? |
|---|---|
| Base-station "internet gateway" (ADR-071) | **NO — unbuilt.** No board, no netlist, no host, no NAT, no station software. Design-only, unmerged. |
| Station-to-station backhaul relay | **NO.** Nothing in any repo. |
| Fleet-side mesh→clearnet exit **with metering + payment + captive fallback** | **CODE YES, PROOF YES, RUNTIME PARTIAL (gate down).** Live on dq05. |
| Ansible-encoded station/exit IaC | **NO.** `grep -rn -iE 'nat64\|dns64\|tayga\|j464xlat\|jool'` finds only a passing comment about the *hosting* VPS's NAT64/DNS64 path; **no role provisions any exit/gateway.** |
| Cellular / cellular-backhaul IaC | **NO.** No Ansible role, no inventory key, no config for LTE on any node. |

---

## 4. What the FIPS mesh already provides for station-to-station relay, and the gap

### 4.1 What it provides (measured)

1. **Routed IPv6 mesh with multi-hop relaying, already crossing the internet.** 8 authenticated peers, `estimated_mesh_size: 849`, spanning-tree depth 4, non-leaf, parent = external peer `andre`. `fipsctl show peers` shows `testserver2` at `"srtt_ms": 188.706`, `"mode": "full"`, `"etx": 1.0`, `"delivery_ratio_forward": 1.0`. **[MEASURED]**
2. **Two transports with automatic fallback**, already configured in IaC for off-LAN nodes:
   ```
   # /etc/fips/fips.yaml (managed by role 03-fips-mesh)
   transports: udp bind_addr "0.0.0.0:2121" / tcp bind_addr "0.0.0.0:8443"
   #   TCP fallback on the same public host (fips_tcp_port; opened by fips-firewall)
   #   so off-LAN peers survive UDP-hostile networks.
   ```
   **[MEASURED]** — this is the **first-class answer to CGNAT**, and the fleet already relies on it.
3. **Cryptographic admission + default-deny inbound.** `peers.deny = ALL`, `peers.allow` = 9 npubs, per-interface nft default-drop except conntrack + drop-ins. **[MEASURED]**
4. **Encryption is in the protocol**: `ADR-100` L6 = "FIPS Noise XK (end-to-end encrypted sessions)". So a station-to-station relay does not need its own crypto. **[MEASURED — file read]**
5. **A per-service metering/billing/gate layer already written** (`fips-exit-gate`, §3.2). **[MEASURED]**
6. **FIPS ships a gateway feature for non-FIPS LAN hosts** — `fips-gateway` is **installed**: `/usr/bin/fips-gateway` (3.9 MB, same 0.5.1 package). Per `docs/design/fips-gateway.md` it does exactly LAN↔mesh translation: *"prerouting DNAT rewrites the destination from the virtual IP to the real `fd00::/8` mesh address, and postrouting masquerade rewrites the source from the LAN host's address to the gateway's `fips0` address"*, and inbound `gateway.port_forwards[]` exposes a LAN service on a `fips0` port. **[MEASURED]** — **this is the mechanism that would put a station's SSH on the mesh, and it is already on disk, unconfigured.**

### 4.2 What it does NOT provide — the measured gaps

| Gap | Evidence |
|---|---|
| **No IPv6 default route through the mesh.** FIPS is a *peering* overlay, not a transit network. | `ip -6 route show dev fips0` → `fd36:…:bb0/128` (self) + `fd00::/8 proto static metric 1024`. **No `default`.** The only IPv6 defaults are `via fe80::ea8f:6fff:fedf:9e11 … proto ra` — i.e. **the metered home router**, on every node. |
| **No NAT64/DNS64.** FIPS addressing is IPv6-only, and the exit engine is `socks5`, not NAT. | `fipsctl show status` → `ipv6_addr`, `effective_ipv6_mtu: 1203`; `fips-exit-gate/exit/` = "Dante `sockd` SOCKS5 server". No `nat64`/`dns64`/`jool` anywhere in the fleet IaC. |
| **MTU is small and is enforced.** | `effective_ipv6_mtu: 1203` on x280; session `path_mtu: 1400`; `/etc/fips/fips.yaml` `tun: mtu: 1280`. **[MODELLED]** A relayed TCP path inherits ~1200 B usable payload → MSS clamping needed and throughput ceiling is lower than a direct path. |
| **The mesh's own throughput over the internet hop is already poor.** | `fipsctl show peers` (x280→testserver2): `"goodput_bps": 1944.38, "srtt_ms": 188.706`. A ~**2 kbit/s goodput** and ~**190 ms RTT** on the one measured inter-node mesh link. **[MEASURED]** **This alone disqualifies the current mesh as the *user-data* relay** for a "station with reception feeds a station without" service — it is a control-plane/signalling path, not a WAN. |
| **`gateway:` block absent.** | `/etc/fips/fips.yaml` contains `node/identity/rendezvous/tun/dns/transports/peers` only. `grep -nE 'forward\|ipv4\|exit\|relay'` → only a comment. |
| **No station exists to join the mesh.** | §3.1. |

### 4.3 The gap, stated precisely

**What the operator wants:** *station A (good reception) relays internet to station B (bad reception)*.
**What the fleet has:** a mesh that can **carry addressed IPv6 between any two members**, with crypto, ACLs, metering and a proven egress engine.
**What is missing** is a **4-part contract**, none of which exists:

1. **A WAN at A.** Requires cellular hardware + a station host. Today: unbuilt (§3.1), and the only cellular HW present has no bearer (§2).
2. **A forwarding decision at A.** A is a router for B. Today: `ip_forward` is already `1` on x280/cobrador/dq05/t440, but `net.ipv6.conf.all.forwarding = 0` on x280, and nothing routes `fd00::/8`↔WAN. **[MEASURED]**
3. **The relay leg A→B.** Today this is the FIPS mesh, measured at `1944 bps` / `189 ms` on the one link I could sample. **[MODELLED]** At that goodput a 1 MB page takes ≈70 minutes. **The mesh cannot be the data plane for relayed internet — it can only be the control plane.** The *data* plane would have to be the balloon link itself (the ADR-100 L4 UDP/IP tunnel), which does not fly yet.
4. **A pairwise peer identity + admission for station B.** The mesh already solves this cheaply: *the only thing B needs from A is A's `npub`* (self-generated, no accounts, no CA). B's path to A is then `A-npub.fips`, admitted by the `peers.allow` ACL. **[MEASURED — this is how the mesh already reaches `andre`, a non-fleet peer]**

**Addressing wrinkle [MODELLED]:** FIPS addresses are `0xfd ‖ SHA-256(pubkey)[0:15]` (per the `pkg/fipsaddr` description, quoted in the fips-exit-gate README), i.e. **deterministic from identity, not allocated by a DHCP/prefix authority**. A relay design therefore cannot "hand station B an IP"; it must either carry B inside the mesh's ULA space or hand B a *different* address family in its own transit subnet. The fleet's own `fips-exit-gate` proves the pattern that works: **the mesh peer runs a SOCKS5 client to the exit** — no IPv4/RFC1918/loopback/`fd00::/8` leakage, source-address auth, per-service metering. **That is the shape the station-to-station relay should copy** rather than a routed default-route handover.

---

## 5. CGNAT / dynamic-IP implications for exposing stations over cellular

### 5.1 The measured facts

- Home WAN IPv4: **one shared address** for the whole household — `80.187.85.172` from both x280 and cobrador. **[MEASURED]** Inbound IPv4 is NAT-translated (the upstream is a consumer CGNAT-ish router). **[MODELLED]**
- Public IPv6: **each node already owns a global IPv6** (`2a01:599:11d:2324:…`, Deutsche Telekom). **[MEASURED]**
- **This is why the meshes bind `0.0.0.0:2121` and `0.0.0.0:8443` with an explicit TCP fallback** — the IaC comment says so verbatim: *"so off-LAN peers survive UDP-hostile networks."* **[MEASURED]**
- `hardening_bootstrap_allow_public_ssh: true` still leaves a public SSH hole on some nodes, and cobrador's ufw shows a bare `22/tcp ALLOW IN Anywhere` + `9098/tcp ALLOW IN Anywhere` (see §6). **[MEASURED]**
- `state/fleet/public_ports.json` deliberately keeps management off the public list: *"Management (SSH, fleet bus, OpenBao, router) is NetBird-only and NOT listed here."* And `"cobrador": []`, `"x240": []`. **[MEASURED]**

### 5.2 What this means for a cellular station — no public IP

**[MODELLED, and it is the crux]** A cellular-attached station is the worst case of the fleet's *current* situation, not a new class of problem:

| Property | Today (home WAN) | Cellular station |
|---|---|---|
| Public IPv4 | shared (measured) | typically **none** (CGNAT, carrier-grade) |
| Inbound IPv4 SSH | **already unreachable** today | unreachable |
| Public IPv6 | yes, per-node (measured, DT) | **often none** on consumer/M2M APNs; if present, frequently firewalled inbound |
| NAT binding lifetime | router-managed | carrier-managed, can be short |
| Egress IP stability | stable-ish | **changes per attach / per APN** |

**Therefore: inbound SSH to a cellular station is the wrong design, and the fleet already knows it.** The pattern that is *already in production and already measured* is the right one:

> **Outbound-initiated overlay.** The station dials *out* to the fleet, and the fleet reaches back *through the established association*. No public IP is required, no port-forward is required, no DDNS is required.

**Which of our existing tools fits — ranked against measured evidence:**

1. **FIPS mesh (outbound UDP 2121, TCP 8443 fallback) — the fit already in place.** It is already the primary transport for every fleet node, already crosses CGNAT and internet, already has crypto + a peer allowlist + default-deny, already runs as a first-class binary on x280/cobrador/etc. A station joining as a `peers.allow` entry gets station↔station and station↔fleet addressing *for free*. **[MEASURED — this is exactly how the fleet reaches both the public VPSes and the external peer `andre`]**
2. **`fips-gateway` (`/usr/bin/fips-gateway`, already installed)** — the purpose-built bridge if the station's radio host is not FIPS-capable: it makes the station's LAN service appear as `<station-npub>.fips:<port>` on the mesh, with DNAT+masquerade handled by nft. **Already on disk, unconfigured.** **[MEASURED]**
3. **`fips-exit-gate` (code + verification artifact exist)** — supplies the missing pieces for a *relay service*: per-(client,service) byte metering, quota cutoff, authorized-set sync, captive 302 fallback, BTCpay/LN payment. It is **already written to be "portable to OpenWrt"** — i.e. it was designed for exactly a small remote box. **[MEASURED]**
4. **NetBird — works, but is the wrong choice here.** It is metered (measured 1.5 GB on the dq05 peer), it needs a SaaS/dashboard control plane (the fleet retired it as primary for exactly that reason, `ADR-018`), and **it is absent on three of seven nodes**. Using it for stations re-introduces the metered dependency the fleet has been actively removing. **[MEASURED]**
5. **Public-IPv6 inbound SSH** — possible today at home, **not dependable on cellular**. Do not design for it.

**Conclusion for (5):** the CGNAT constraint **strengthens** the case for using the existing FIPS overlay as the station access plane and **weakens** the case for any inbound-exposure design. There is no "public IP" variant of this that the fleet should adopt.

---

## 6. Security posture required before any station is internet-exposed

### 6.1 What is already true (measured — reuse, do not rebuild)

| Control | State | Evidence |
|---|---|---|
| SSH key-only, no root, no password, no empty pw | **enforced fleet-wide** | `sshd -T` on x280 + cobrador: `permitrootlogin no`, `passwordauthentication no`, `kbdinteractiveauthentication no`, `permitemptypasswords no` |
| Gateway ports off | enforced | `gatewayports no` |
| fail2ban | **active** | `fail2ban-client` present; `systemctl is-active fail2ban` → `active` |
| Unattended upgrades | enabled by role | `roles/01-node-hardening/defaults/main.yml` `hardening_unattended_upgrades: true` |
| Mesh inbound default-deny + peer allowlist | **enforced** | `fips.nft` default-drop on `fips0`; `peers.deny = ALL`; 9-npub `peers.allow` |
| Egress-only exit engine | **built** | `fips-exit-gate/exit/`: "egress-only (blocks fd00::/8, RFC1918, loopback, metadata)" |
| Per-client metering + quota cutoff | **built** | `agent/`: "reads the per-(client,service) byte counters, reports usage, and enforces quota cutoffs" |
| Public-port allowlist is config-as-code and empty by default | **present** | `state/fleet/public_ports.json` → `"default": []`, `"cobrador": []`, `"x240": []` |

### 6.2 What is measurably WRONG for an internet-exposed station — act on these

1. **A bare `22/tcp ALLOW IN Anywhere` is live on CobradorWave's WAN-facing firewall.**
   ```
   $ ssh cobrador 'sudo ufw status verbose' | grep '^22/tcp'
   22/tcp on wt0              ALLOW IN    Anywhere
   22/tcp                     ALLOW IN    Anywhere      ← unrestricted on ALL interfaces
   ```
   Also present: `9098/tcp ALLOW IN Anywhere`, `9099` exposed via `socat` (`ss -tlnp` → `*:9099 socat`). The fleet's *intent* (`public_ports.json`: management is "NetBird-only") and its *measured state* disagree. **Do not propagate this posture to a station.** **[MEASURED]**
2. **`hardening_bootstrap_allow_public_ssh: true` is still the role default** — a deliberate onboarding crutch: *"During first bring-up keep a public SSH hole so a failed NetBird join cannot strand the node. **Close it after onboarding**."* For a remote solar/cellular station, a stranded-node recovery plan is mandatory *before* the hole is closed, or the node is unrecoverable in the field. **[MEASURED]**
3. **The exit gate itself is currently down** (§3.3: `nft list table inet fips_exit` → not found; no 1080 listener). An unaudited "internet exit" that half-exists is worse than none — a station built on it needs its own enforced gate, verified on the node, not assumed.
4. **No station-side OS baseline exists.** All the hardening above is Ansible-applied to *fleet* nodes. There is **no role, inventory entry, or playbook for a station**; `~/.ssh/config` aliases, `fips peers.allow`, and `public_ports.json` all have no station row. **[MEASURED]**

### 6.3 Minimum posture before a station is exposed (each item has fleet precedent)

**[MODELLED — checklist derived from measured fleet state]**

1. **No inbound on the cellular interface.** The station dials out. Reuse the FIPS `0.0.0.0:2121` + `8443/tcp` fallback pattern.
2. **Admit by identity, not by address.** Add the station's npub to `peers.allow` / `peers.deny=ALL` before it ever comes up. (Precedent: the mesh does this today.)
3. **Key-only SSH, root off, gateway ports off** — copy `/etc/ssh/sshd_config.d/00-hermes-keys-only.conf` verbatim onto the station image.
4. **Default-deny on ALL station interfaces, not just the mesh.** Write the station's own nft baseline; do not rely on the fleet's `fips.nft`, which explicitly *only* polices `fips0` ("every packet not arriving on fips0 returns immediately").
5. **Egress policy at the station = the `fips-exit-gate` model** (block `fd00::/8`, RFC1918, loopback, link-local, cloud metadata) so a relayed client cannot pivot onto the station's own management plane.
6. **Meter the relay.** Per-(client,service) counters + quota cutoff already exist as code (`agent/`). An unattended cellular site without a byte cap is an uncapped bill.
7. **Watch the metered budget.** The fleet already runs a 350 GB/month guard (`56-bandwidth-meter`: warn 70 %, pause 80 %, `overlay_interfaces: ["wt0"]`). **A cellular SIM is metered by definition** — it must be enrolled in the same meter/alert path, or the fleet's containment policy silently stops applying to the one link that costs the most.
8. **Physical/failure-mode security.** A mast-mounted box is reachable by a human. Console/LAN access at the station must not grant fleet admission without the station's key.
9. **Do not put the station in the Station→Clearnet direction without deciding who pays.** The existing exit engine bills via BTCpay/LN against a prepaid balance. A station relaying *third-party* internet is a paid-service legal question (§ADR-071's unresolved ISM caveat) — flag as **UNVERIFIED**, not resolved by any code.

---

## 7. Direct answers to the six questions

**(1) Measured remote-access path per node.** FIPS mesh over IPv6 as primary everywhere — `.fips` names via `/etc/fips/hosts` + the node's own resolver, `AddressFamily inet6`, `~/.ssh/id_fleet`; 8 authenticated peers, non-leaf, spanning-tree depth 4, an external non-fleet parent (`andre`). NetBird is a *live, metered fallback* on 4 nodes and absent on 3. All 7 nodes were reachable; none was unreachable. LAN management is a second path (`192.168.2.0/24` allowed inbound in ufw).

**(2) Does cellular capability already exist anywhere?** **Hardware, yes, on two nodes; capability, no, on any node.**
- CobradorWave: Sierra EM7455, driver-bound, `mmcli` sees it, **`state: failed / failed reason: sim-missing`**, no `wwan0`, no bearer.
- **x280: Fibocom L830-EB-00 — a second LTE modem the brief does not mention**, `cdc_mbim`-bound, `wwan0` present but DOWN, and **no ModemManager/`mmcli`/`libmbim` installed** so it cannot be brought up without adding the stack.
- All other nodes: zero modem hardware (`mmcli -L` → `No modems were found` or not installed).
- **No node has any cellular configuration** (no NetworkManager anywhere on x280, no `/etc/ppp`, no pppd, no Ansible role, no inventory key).

**(3) Does the "internet gateway" ground function exist today?** **For the base station: purely unbuilt** — no schematic, no netlist, no placement, no host CPU, no station software, and the whole ground-station ADR set (071–082) is **unmerged** with no station host design anywhere. **But the fleet separately runs a full mesh→clearnet exit gateway** (`fips-exit-gate` on dq05: `agent`/`captive`/`unbound`/`backend`/`db` up 23 h; Dante SOCKS5 egress, source-address auth, per-client metering, captive 302, BTCpay) **with a verified end-to-end artifact from 2026-09-09** — and its **gate table (`inet fips_exit`) and `:1080` listener are currently absent**, so the live deployment is partial. That is the *inverse* direction of the station's problem, and it is the closest thing to the operator's ask that actually exists.

**(4) What the existing FIPS/NetBird mesh gives for station-to-station relay, and the gap.** Gives: multi-hop routed IPv6 over the public internet, two transports with TCP fallback for UDP-hostile/CGNAT paths, Noise-XK encryption, a cryptographic peer allowlist with default-deny inbound, a proven metering+billing+gate layer, and an already-installed `fips-gateway` binary that can put a non-FIPS station's service on the mesh as `<npub>.fips:<port>`. **Gap:** no IPv6 default route through the mesh, no NAT64/DNS64, MTU 1203, and — decisively — **the measured inter-node mesh goodput is ~1.9 kbit/s at ~189 ms RTT**, so the mesh is a **control plane, not the internet data plane**. The relay's data plane has to be the balloon link (ADR-100 L4 UDP/IP tunnel), which does not fly yet.

**(5) CGNAT/dynamic-IP implications.** Measured today: one shared public IPv4 for the entire household (`80.187.85.172` from two nodes) while IPv6 is per-node and public. On cellular, expect **no inbound IPv4 and often no usable inbound IPv6** — i.e. cellular is strictly worse than the fleet's current situation, and the fleet already solved the current situation the right way: **outbound-initiated overlay with an explicit TCP fallback** (`transports.tcp 0.0.0.0:8443`, IaC comment: *"so off-LAN peers survive UDP-hostile networks"*). **Fit ranking: FIPS mesh (already primary everywhere) > `fips-gateway` (already installed) > `fips-exit-gate` (already written and proof-verified) > NetBird (metered, SaaS control plane, absent on 3 nodes) > public-IPv6 inbound (not dependable on cellular).**

**(6) Security posture before exposure.** Key-only SSH/root-off/gateway-ports-off + fail2ban + unattended upgrades + mesh default-deny + an npub allowlist + egress blocking + per-client metering are **all already implemented and measured** — reuse them. What must be fixed first: (a) a bare `22/tcp ALLOW IN Anywhere` is live on CobradorWave's WAN firewall and `9098/tcp` plus a `socat` `*:9099` listener are exposed — **do not copy this to a station**; (b) `hardening_bootstrap_allow_public_ssh: true` is a deliberate onboarding hole whose closure requires a field-recovery plan; (c) the exit gate is currently unarmed, so any station built on it must have its own **node-verified** gate, not an assumed one; (d) no station OS baseline, inventory row, or playbook exists yet; (e) a cellular SIM is metered by definition and must be enrolled in the fleet's existing 350 GB/month budget guard.

---

## 8. Reproduce

```bash
# access path
cat ~/.ssh/config; cat ~/repos/hermes-orchestration/inventory.ini
getent hosts cobrador.fips
ssh cobrador 'hostname'; ssh dq05 'hostname'          # etc. — all 6 reachable
sudo fipsctl show status; sudo fipsctl show peers; sudo fipsctl show tree

# cellular inventory (per node)
ip -br link | grep -iE 'wwan|usb[0-9]'
ls /dev/cdc-wdm* /dev/ttyUSB* /dev/wwan*
mmcli -L; mmcli -m 0; mmcli -m 0 --sim 0
lsusb | grep -iE 'modem|wwan|lte|fibocom|sierra'
systemctl is-active ModemManager

# the mesh exit gateway (dq05)
ssh dq05 'docker ps --format "{{.Names}} | {{.Status}}"'
ssh dq05 'sudo nft list table inet fips_exit'          # → not found (gate down)
ssh dq05 'ss -tlnp | grep -E ":(1080|1081)"'           # → nothing

# station state
cat ~/PLAN-base-station-board.md
cat worktrees/e80-lr2021-audit/docs/analysis/PROGRAM-GAP-ANALYSIS.md
```

## 9. Explicit non-claims

- I did **not** open, insert, or inspect any SIM physically. CobradorWave's `sim-missing` vs `active: yes / iccid: …` contradiction is **recorded, not resolved**.
- I did **not** test whether x280's Fibocom modem can attach to a network — ModemManager is not installed there, so no such test was possible without changing the host (out of scope: read-only).
- I did **not** verify the fips-exit-gate E2E evidence of 2026-09-09 by re-running it; I read the artifact and separately verified the current deployment is **partial**.
- `80.187.85.172` being CGNAT (vs a plain NAT) is **MODELLED** from "one shared IPv4 across multiple hosts"; I did not query the upstream gateway's WAN address.
- The relay throughput ceiling is **MODELLED** from one sampled mesh goodput (`1944 bps`), not from a sustained transfer test.
- Legal/licencing of relaying internet over licence-exempt ISM to a third party remains **UNVERIFIED** — unchanged by anything measured here, and it is the binding constraint per ADR-071's own caveat.
