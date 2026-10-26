# Manual gateway IP implementation plan

Goal: Allow Mobile Alerts gateways on routed VLANs, with a stable proxy port.
Architecture: Keep broadcast discovery as the default. Add optional IPv4 unicast to the library; persist the gateway host in HA while retaining the MAC unique ID. Configure proxy port per entry (0 retains automatic allocation).
Scope approved in chat: modify both Johnnyyr forks, preserve names and origin/license credits, document installation and firewall. No live HA, Matrix or firewall changes; no upstream PR submission without a request.

1. Library: add tests for unicast discovery, commands, config writes, invalid hosts and default broadcast; run red, implement gateway_ip, run green.
2. HA: add real Home Assistant flow/setup tests for manual form, invalid/unreachable host, duplicate MAC, restart persistence, fixed-port setup, legacy entries, binding failures; run red, implement, run green. Add English and German strings.
3. Compatibility: preserve the published mobilealerts 0.1.13 behavior required by HA (the upstream Git tree has older sensor code). Document provenance, retain MIT notices. Pin the fork by immutable commit in manifest.
4. Document fork relations, HACS setup, two host-specific firewall rules and Matrix proxy handover. Run targeted and existing tests, JSON/syntax/changelog validation, package install and independent review.

Decisions: work on feature branches in fresh clones in the user-selected folder. No rename of Python package or HA domain. Existing automatic entries keep broadcast and dynamic port. Manual entries default to port 8088. Each gateway requires its own fixed listener port. IP changes can be edited in options without changing identity.

Verification: 22 library tests, 17 HA tests passed; UDP probe of actual gateway found MAC 001D8C0DF7E1 and read-only config refresh succeeded. Independent code review reported no critical/important findings. Immutable source archive installed successfully in an isolated target; signature and version verified. HA requirement parsing verified. HA warning originates in HA HTTP server aiohttp inheritance. No live proxy/firewall handover performed.
