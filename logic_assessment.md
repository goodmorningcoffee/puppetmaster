# PUPPETMASTER Logic Assessment

## How the Sock Puppet Detection System Works

**Document Purpose:** This is a human-readable explanation of how PUPPETMASTER detects networks of fake/coordinated websites.

---

## The Core Problem

Imagine someone wants to make their business look more legitimate by creating fake review sites, competitor comparison pages, or "independent" blogs that all secretly promote the same company. These fake sites are called **sock puppets** - like a ventriloquist using multiple puppets that appear separate but are controlled by one person.

The challenge: **How do you prove multiple websites are secretly run by the same person?**

---

## The Key Insight

When someone operates multiple websites, they inevitably leave fingerprints that connect them:

### The "Smoking Gun" Evidence

These are **definitive proof** of same ownership - like finding the same fingerprint at multiple crime scenes:

| Evidence Type | Why It's Definitive |
|--------------|---------------------|
| **Google Analytics ID** | Each GA account has a unique ID (UA-12345678-1). If two sites share the same ID, they're definitively using the same analytics account. |
| **Google AdSense Publisher ID** | Each AdSense account has a unique publisher ID (pub-1234567890). Same ID = same ad account = same operator. |
| **Email Address** | If the same specific email (not generic like admin@domain.com) appears in multiple domains' records, same person. |
| **SSL Certificate** | Custom SSL certificates have unique fingerprints. Same fingerprint = same cert = same operator. |
| **Google Site Verification** | Unique tokens that prove ownership in Google Search Console. |

### Strong Supporting Evidence

These are suggestive but not conclusive alone:

| Evidence Type | What It Suggests |
|--------------|------------------|
| **WHOIS Registration** | Same name, address, or organization in domain registration records |
| **Phone Numbers** | Same contact phone across domains |
| **Custom Nameservers** | Using the same private DNS servers (not generic ones like Google DNS) |
| **Same IP Address** | Hosted on the same server (though could be shared hosting) |

### Noise We Filter Out

These are ignored because they're too common:

- Cloudflare IPs (millions of sites use Cloudflare)
- AWS/Google Cloud/Azure IPs (shared hosting)
- Generic registrar emails (abuse@godaddy.com)
- Common nameservers (ns1.google.com)

---

## The Three-Stage Pipeline

### Stage 1: DISCOVER - Find the Domains

Before we can analyze, we need domains to investigate.

**Option A: Keyword Search**
- Enter industry keywords (e.g., "construction estimating software reviews")
- Tool searches Google and DuckDuckGo
- Filters results through a blacklist (Amazon, Wikipedia, etc. are excluded)
- Result: List of potentially suspicious domains

**Option B: Import a List**
- If you already have domains to investigate, import them from a file

### Stage 2: SCAN - Gather OSINT Data

Each domain is scanned using SpiderFoot, a comprehensive OSINT (Open Source Intelligence) tool.

**What SpiderFoot Collects:**
- IP addresses and hosting information
- DNS records and nameservers
- WHOIS registration data
- SSL/TLS certificate details
- Emails found on the site
- Google Analytics and AdSense IDs
- Social media links
- And hundreds more data types

**Output:** One CSV file per domain containing all discovered data.

### Stage 3: ANALYZE - Find the Connections

This is where the magic happens.

**Step 1: Signal Extraction**
- Read all SpiderFoot CSV exports
- Extract "signals" - pieces of evidence that could connect domains
- Classify each signal by strength (Smoking Gun, Strong, Weak)
- Filter out noise patterns

**Step 2: Build a Network Graph**
- Create a graph where each domain is a node
- Add edges between domains that share signals
- Weight edges by signal strength (smoking guns weigh more)

**Step 3: Community Detection**
- Use the Louvain algorithm to find "communities" (clusters)
- Domains in the same cluster likely share an operator
- Clusters with multiple smoking gun connections are high confidence

**Step 4: Hub Analysis**
- Identify central "hub" domains with many connections
- These are often the main operation (the "puppetmaster")
- Calculate centrality scores to rank importance

---

## Understanding the Results

### Executive Summary (executive_summary.md)

**Start here.** This is a human-readable overview:
- How many domains were analyzed
- How many clusters were found
- Key smoking gun connections
- Top hub domains (likely operators)

### Smoking Guns (smoking_guns.csv)

Every definitive connection with evidence:
```
domain1.com, domain2.com, google_analytics, UA-12345-1, "Same GA tracking code"
```

**Interpretation:** domain1.com and domain2.com definitively share an operator because they use the same Google Analytics ID.

### Clusters (clusters.csv)

Groups of connected domains:
```
Cluster 1: 15 domains, HIGH confidence, hub: mainsite.com
  - site1.com
  - site2.com
  - site3.com
  - ...
```

**Interpretation:** These 15 domains are likely all controlled by whoever operates mainsite.com.

### Hub Analysis (hub_analysis.csv)

Potential command-and-control domains:
```
controller.com: 186 connections, 121 smoking guns, 0.028 centrality
```

**Interpretation:** controller.com is highly connected and likely the central node in a puppet network.

---

## Confidence Levels Explained

| Level | Meaning | Evidence Required |
|-------|---------|-------------------|
| **CONFIRMED** | Definitive connection | At least 1 smoking gun |
| **LIKELY** | Very probably connected | 2+ strong signals |
| **POSSIBLE** | Potentially connected | 1 strong signal |
| **WEAK** | Uncertain | Only weak signals |

---

## False Positives to Watch For

Not every connection means the same operator. Consider:

### Legitimate Shared Services

| Scenario | Why It's Not a Puppet |
|----------|----------------------|
| Same web developer | An agency built multiple client sites |
| Same hosting reseller | Reseller hosts many unrelated sites |
| Same WordPress theme | Popular themes used by thousands |

### How to Verify Suspicious Connections

1. **Check signal uniqueness** - Is the shared Google Analytics ID truly unique, or a template?
2. **Look for multiple independent signals** - One match might be coincidence; three rarely are
3. **Manual website review** - Do the sites look related? Similar design? Same contact info?
4. **Check registration dates** - Were domains registered around the same time?

---

## The Blacklist System

To reduce false positives, we maintain a blacklist of domains that are:

- Major platforms (Amazon, eBay, Facebook, etc.)
- Generic sites (Wikipedia, Reddit, etc.)
- News/media sites
- Government domains
- Educational institutions

These are excluded from both discovery (keyword search) and analysis (signal extraction).

**Current blacklist:** 231 domains (can be customized via [K4] menu)

---

## Kali Linux Integration

When running on Kali Linux, PUPPETMASTER can use additional OSINT tools:

| Tool | What It Does |
|------|--------------|
| theHarvester | Finds emails and subdomains |
| Amass | Advanced DNS enumeration |
| DNSRecon | DNS record analysis |
| Nmap | Port and service scanning |
| WhatWeb | Website fingerprinting |
| SSLScan | SSL/TLS analysis |

**Infrastructure Correlation (K5)** cross-references results from all tools to find additional connections between domains.

---

## Limitations

### What This Tool Cannot Detect

1. **Well-funded operations** - Sophisticated actors use separate infrastructure per site
2. **Privacy-protected domains** - WHOIS privacy hides registration info
3. **No analytics** - Sites without tracking codes leave fewer fingerprints
4. **Different registrars** - Using different services per domain reduces connections

### What This Tool Is Best At

1. **Lazy operators** - Most puppet networks reuse infrastructure
2. **Scale** - Analyzing hundreds of domains quickly
3. **Pattern detection** - Finding non-obvious connections humans would miss
4. **Documentation** - Creating evidence for reports/investigations

---

## Technical Architecture Summary

```
User Input (keywords or domain list)
         |
         v
+-------------------+
|   Discovery       |  Google/DuckDuckGo search or file import
+--------+----------+
         |
         v
+-------------------+
|   SpiderFoot      |  OSINT scanning (one CSV per domain)
+--------+----------+
         |
         v
+-------------------+
|   Signal          |  Extract and classify evidence
|   Extraction      |  (Smoking Gun / Strong / Weak)
+--------+----------+
         |
         v
+-------------------+
|   Network         |  Build graph, detect communities
|   Analysis        |  (Louvain clustering, hub detection)
+--------+----------+
         |
         v
+-------------------+
|   Reporting       |  Generate human-readable reports
|                   |  (MD, CSV, GraphML)
+-------------------+
```

---

## Glossary

| Term | Definition |
|------|------------|
| **Sock Puppet** | A fake online identity or website used to deceive |
| **OSINT** | Open Source Intelligence - publicly available information |
| **Signal** | A piece of evidence that could connect domains |
| **Smoking Gun** | Definitive proof of connection |
| **Cluster** | A group of connected domains (likely same operator) |
| **Hub** | A central domain with many connections |
| **Louvain** | A community detection algorithm for graphs |
| **Centrality** | A measure of how "important" a node is in a network |

---

## Quick Reference: What To Do With Results

1. **Start with executive_summary.md** - Get the big picture
2. **Review smoking_guns.csv** - See definitive connections
3. **Examine clusters.csv** - Understand the network structure
4. **Investigate hub domains** - Find the likely operators
5. **Verify manually** - Confirm suspicious sites by visiting them
6. **Document findings** - Use the CSV exports for reports

---

*PUPPETMASTER: Finding the strings that connect the puppets.*
