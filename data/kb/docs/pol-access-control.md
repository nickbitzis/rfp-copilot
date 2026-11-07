---
id: pol-access-control
title: Access Control Policy
section: Access Control
version: 2.3
effective: 2026-01-14
---
# Access Control Policy

## Purpose
This document sets the rules described below. It applies to all employees, contractors, and production systems.

## Mfa
Multi-factor authentication is enforced for all Corvane workforce accounts and is available to customers for local logins, with TOTP apps and WebAuthn security keys supported.

## Rbac
The platform provides role-based access control with 5 built-in roles, and custom roles are available on the Enterprise plan.

## Access review
Access to production systems is reviewed every 90 days by system owners, and access is revoked within 24 hours of termination.

## Password
Local passwords must be at least 12 characters, are checked against a breached password list, and the account locks after 10 failed attempts.

## Privileged access
Engineers have no standing production access. Access is granted just in time for up to 4 hours, requires a ticket and peer approval, and every session is recorded.

## Support access
Corvane support staff can open a customer workspace only after the customer grants time-limited access from the admin console, and every action is written to the customer audit log.

## Session timeout
Web sessions expire after 30 minutes of inactivity by default, and administrators can set a value between 5 and 480 minutes.

## Ownership and review
The owner of this document is the security-lead. It is reviewed at least once a year and after any major change to the platform.
