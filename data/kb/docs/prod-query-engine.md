---
id: prod-query-engine
title: Query Engine Guide
section: Product
version: 4.4
effective: 2026-08-02
---
# Query Engine Guide

## Scope
This document applies to Corvane staff and systems.

## Requirements
The query engine runs SQL over columnar storage. Queries time out after 10 minutes, and results are cached for 15 minutes unless the user forces a refresh.
