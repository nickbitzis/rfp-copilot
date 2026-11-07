---
id: pol-sdlc
title: Secure Development Lifecycle Policy
section: Data Protection
version: 6.2
effective: 2026-02-04
---
# Secure Development Lifecycle Policy

## Purpose
This document sets the rules described below. It applies to all employees, contractors, and production systems.

## Test data
Production customer data is never copied into development or test environments. Engineers use synthetic data sets.

## Code review
Every code change requires review and approval by a second engineer, and automated tests and static analysis must pass before merge.

## Sbom
A software bill of materials is generated for every release in CycloneDX format and is available to Enterprise customers on request.

## Ownership and review
The owner of this document is the security-lead. It is reviewed at least once a year and after any major change to the platform.
