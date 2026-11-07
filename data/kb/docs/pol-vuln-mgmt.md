---
id: pol-vuln-mgmt
title: Vulnerability Management Policy
section: Vulnerability Management
version: 6.0
effective: 2026-08-03
---
# Vulnerability Management Policy

## Purpose
This document sets the rules described below. It applies to all employees, contractors, and production systems.

## Pentest
An independent firm performs a penetration test of the platform every 6 months. An executive summary of the latest test is available under NDA.

## Vuln scanning
Infrastructure and container images are scanned for vulnerabilities daily, and application dependencies are scanned on every build.

## Patch sla
Critical vulnerabilities are remediated within 7 days, high within 30 days, and medium within 90 days.

## Bug bounty
Corvane runs a public vulnerability disclosure program and a private bug bounty program managed by an external platform.

## Ownership and review
The owner of this document is the security-lead. It is reviewed at least once a year and after any major change to the platform.
