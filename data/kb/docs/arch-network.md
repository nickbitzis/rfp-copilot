---
id: arch-network
title: Network Security Architecture
section: Infrastructure
version: 2.4
effective: 2026-07-06
---
# Network Security Architecture

## Purpose
This document sets the rules described below. It applies to all employees, contractors, and production systems.

## Network security
Production runs in private subnets with no public IP addresses. Only load balancers are internet-facing, and a web application firewall filters all inbound traffic.

## Ddos
DDoS protection is provided at the network edge by the cloud provider and the content delivery network, with rate limiting at the API gateway.

## Ownership and review
The owner of this document is the security-lead. It is reviewed at least once a year and after any major change to the platform.
