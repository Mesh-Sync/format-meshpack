# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of MeshPack seriously. If you discover a security vulnerability within this project, please follow these steps:

1.  **Do NOT create a public GitHub issue.** Security vulnerabilities should be handled discreetly to protect users.
2.  Use GitHub private vulnerability reporting when available, or send an email to **contact@meshsync.net** with the subject prefix `[MeshPack Security]`.
3.  Include a detailed description of the vulnerability, steps to reproduce it, and any relevant logs or potential impact.
4.  You will receive a response within 48 hours acknowledging receipt of your report.
5.  We will work with you to understand and resolve the issue.

We appreciate your responsible disclosure and will credit you in the changelog once a fix has been released (unless you prefer to remain anonymous).

## Supply Chain Controls

Public release CI runs schema validation, generated SDK builds, dependency audits, secret scanning, SBOM generation, and artifact provenance attestations. Release artifacts should not be promoted unless these checks complete successfully.
