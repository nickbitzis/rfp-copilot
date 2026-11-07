---
id: arch-overview
title: Architecture Overview
section: Infrastructure
version: 6.1
effective: 2026-06-02
---
# Architecture Overview

## Purpose
This document sets the rules described below. It applies to all employees, contractors, and production systems.

## Hosting
Corvane Insight runs on a major public cloud provider across multiple availability zones in each region. Corvane does not operate its own data centers.

## Multi tenancy
The platform is multi-tenant. Each customer workspace is isolated by a tenant id enforced in the data access layer and has a separate encryption key per tenant.

## Architecture
The platform consists of a web application, a REST API, a query engine, and a columnar storage layer, deployed as containers on managed Kubernetes.

## Ownership and review
The owner of this document is the security-lead. It is reviewed at least once a year and after any major change to the platform.
