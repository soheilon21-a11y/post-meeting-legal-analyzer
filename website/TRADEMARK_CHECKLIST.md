# Trademark clearance checklist — "Mithra"

This is a **checklist and evidence log**, not legal advice. It exists so that
the name "Mithra" is cleared for use as a software brand before launch. All
search results below must be filled in by a human and dated; nothing here is
pre-populated or assumed.

- **Owner / applicant:** soheilon21-a11y
- **Mark as used:** `Mithra` (word mark) + the seal/M wordmark
- **Goods & services:** local legal-analysis software
- **Prepared:** 2026-09-20

## 1. Terms to search

| # | Term | Notes |
|---|------|-------|
| 1 | `Mithra` | Primary mark |
| 2 | `Mithra Legal` | Combined mark |
| 3 | `Mithra Analyzer` | Combined mark |
| 4 | `Mitra` | Common phonetic/transliteration variant |
| 5 | `Mithras` | Variant spelling |

## 2. Registries to search (official, free)

| Registry | Jurisdiction | URL |
|----------|--------------|-----|
| DPMAregister | Germany | https://register.dpma.de/ |
| EUIPO eSearch plus | European Union | https://euipo.europa.eu/eSearch/ |
| USPTO Trademark Search | United States | https://tmsearch.uspto.gov/ |
| WIPO Global Brand Database | International (Madrid) | https://branddb.wipo.int/ |
| TMview (aggregator) | Multi-office | https://www.tmdn.org/tmview/ |

## 3. Relevant Nice classes

| Class | Covers |
|-------|--------|
| **009** | Downloadable software; computer software for legal analysis |
| **042** | Software as a service (SaaS); software development and hosting |
| **045** | Legal services; legal research and advisory services |

Also consider class **041** (education/training) only if training material is
commercialized later.

## 4. Results log (fill in — do not assume)

| Term | Registry | Class | Result (none / similar / identical) | Mark & owner found | Status | Date checked | Checked by |
|------|----------|-------|-------------------------------------|--------------------|--------|--------------|------------|
| Mithra | DPMAregister | 009 | | | | | |
| Mithra | DPMAregister | 042 | | | | | |
| Mithra | DPMAregister | 045 | | | | | |
| Mithra | EUIPO | 009 | | | | | |
| Mithra | EUIPO | 042 | | | | | |
| Mithra | EUIPO | 045 | | | | | |
| Mithra | USPTO | 009 | | | | | |
| Mithra | USPTO | 042 | | | | | |
| Mithra | USPTO | 045 | | | | | |
| Mithra | WIPO | 009/042/045 | | | | | |
| Mitra | (all) | 009/042/045 | | | | | |

## 5. Decision rules

1. **Identical or highly similar mark in classes 009, 042, or 045** in a
   jurisdiction where the software will be offered → **stop**; do not launch
   under this name without a trademark attorney's opinion.
2. **Similar mark in unrelated classes only** (e.g. food, cosmetics) → proceed
   with caution; record the reference and monitor.
3. **No confusingly similar mark found** → proceed, and file an application in
   the classes/jurisdictions that matter before public launch.
4. Any doubt at all → treat as rule 1. A rename is cheaper than litigation.
5. Keep this file updated; re-run the search at least every 12 months and
   before entering a new market.

## 6. DNS / domain check

`dig` and `whois` are **not installed** in this environment, so the checks were
run with PowerShell's native `Resolve-DnsName` (NS records).

- **Tool:** `Resolve-DnsName -Type NS`
- **Date:** 2026-09-20
- **Caveat:** a resolving domain means a name server exists — it does **not**
  mean a trademark is registered, and non-resolution (NXDOMAIN) does **not**
  mean a name is unregistered or available to buy.

| Domain | NS result | Interpretation |
|--------|-----------|----------------|
| mithra.ai | resolves (ns3/ns4.afternic.com) | registered / parked (Afternic) |
| mithra.io | resolves (pete/sreeni.ns.cloudflare.com) | registered |
| mithra.dev | resolves (dns1/dns2.registrar-servers.com) | registered |
| mithra.app | resolves (ali/augustus.ns.cloudflare.com) | registered |
| mithra.legal | NXDOMAIN | no NS record observed |
| mithra.law | NXDOMAIN | no NS record observed |

> A resolving `mithra.*` domain indicates the brand is already in use on the
> internet. Domain availability is **not** a trademark clearance; consult a
> trademark attorney before adopting the name commercially.
