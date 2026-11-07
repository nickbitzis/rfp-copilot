---
id: pol-encryption
title: Encryption Standard
section: Encryption
version: 6.3
effective: 2026-01-28
---
# Encryption Standard

## Purpose
This document sets the rules described below. It applies to all employees, contractors, and production systems.

## Enc rest
All customer data is encrypted at rest with AES-256, including databases, object storage, and backups.

## Enc transit
All connections use TLS 1.2 or higher, and TLS 1.3 is preferred. Older protocols are disabled.

## Ownership and review
The owner of this document is the security-lead. It is reviewed at least once a year and after any major change to the platform.
