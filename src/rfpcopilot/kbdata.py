"""Source facts for the synthetic knowledge base of Corvane, a made-up B2B analytics SaaS vendor.

Each topic is one fact the vendor answers often. From these the generator builds:
- policy and product docs (markdown), where the current fact lives,
- the approved answer library, with several phrasings per topic, plus outdated answers that
  carry the old value (superseded by a newer policy) and a few contradictory current answers,
- the labeled eval set, using a phrasing that is not in the library.

Nothing here is real: the company, customers, people, and numbers are invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Topic:
    key: str
    section: str
    doc: str
    compliance: str  # yes / no / partial
    answer: str
    facts: tuple[str, ...]
    library_questions: tuple[str, ...]
    eval_question: str
    old_answer: str | None = None
    old_date: str | None = None
    contra_answer: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


def T(key, section, doc, compliance, answer, facts, lib, ev, old=None, old_date=None, contra=None):
    return Topic(key, section, doc, compliance, answer, tuple(facts), tuple(lib), ev, old, old_date, contra,
                 (section.lower().replace(" & ", "-").replace(" ", "-"), key))


C, AC, EN, DP, IN, BC, IR, VM, LG, VE, SL, PR, CO, HR, SD = (
    "Compliance", "Access Control", "Encryption", "Data Protection", "Infrastructure", "Business Continuity",
    "Incident Response", "Vulnerability Management", "Logging", "Vendor Management", "SLA & Support",
    "Product", "Commercial", "HR Security", "Secure Development",
)

TOPICS: list[Topic] = [
    # Compliance
    T("soc2", C, "pol-compliance-program", "yes",
      "Yes. Corvane holds a SOC 2 Type II report covering the Security, Availability, and Confidentiality criteria. "
      "The latest audit period ended 2026-06-30 and the report is shared under NDA.",
      ["SOC 2 Type II"],
      ["Do you have a SOC 2 report?", "Can you provide your most recent SOC 2 Type II report?",
       "Has your organization completed a SOC 2 audit?"],
      "Please confirm whether an independent SOC 2 attestation exists and which trust criteria it covers.",
      old="Yes. Corvane holds a SOC 2 Type I report dated 2022-11-30. A Type II audit is planned.", old_date="2023-01-15"),
    T("iso27001", C, "pol-compliance-program", "yes",
      "Yes. Corvane is certified to ISO/IEC 27001:2022. The certificate covers the Corvane Insight platform and "
      "corporate IT and is valid until 2028-03-31.",
      ["27001:2022"],
      ["Are you ISO 27001 certified?", "Do you hold an ISO/IEC 27001 certification?",
       "Which version of ISO 27001 are you certified against?"],
      "Is your information security program certified under ISO 27001, and which version?",
      old="Yes. Corvane is certified to ISO/IEC 27001:2013 for the Corvane Insight platform.", old_date="2023-05-02"),
    T("gdpr", C, "pol-privacy", "yes",
      "Yes. Corvane acts as a processor under GDPR and signs a Data Processing Agreement with Standard Contractual "
      "Clauses for any transfer outside the EEA.",
      ["Data Processing Agreement"],
      ["Are you GDPR compliant?", "Will you sign a DPA?", "Do you comply with the EU General Data Protection Regulation?"],
      "Describe how you meet GDPR obligations when acting as our data processor."),
    T("hipaa", C, "pol-compliance-program", "partial",
      "Partial. Corvane signs a Business Associate Agreement for customers on the Enterprise plan only. HIPAA "
      "workloads must run in the US region.",
      ["Business Associate Agreement", "Enterprise"],
      ["Will you sign a BAA?", "Do you support HIPAA compliance?", "Can Corvane act as a HIPAA business associate?"],
      "Is the platform suitable for HIPAA protected health information, and will you sign a business associate agreement?"),
    T("pci", C, "pol-compliance-program", "no",
      "No. Corvane Insight is not in scope for PCI DSS and customers must not upload cardholder data. Payments to "
      "Corvane are handled by a PCI DSS Level 1 payment subprocessor.",
      ["not in scope for PCI DSS"],
      ["Are you PCI DSS compliant?", "Can we store credit card numbers in the platform?",
       "Is the service certified for PCI DSS?"],
      "May we load payment card data into the service, and is it covered by PCI DSS?"),
    T("pentest", VM, "pol-vuln-mgmt", "yes",
      "Yes. An independent firm performs a penetration test of the platform every 6 months. An executive summary of "
      "the latest test is available under NDA.",
      ["6 months"],
      ["Do you conduct penetration testing?", "How often are third-party penetration tests performed?",
       "Can you share your latest penetration test results?"],
      "How frequently does an outside firm run a penetration test against the application?",
      old="Yes. An independent firm performs a penetration test of the platform every 12 months.", old_date="2023-08-21"),
    T("audit-rights", C, "legal-msa", "partial",
      "Partial. Customers may review our SOC 2 report and send one security questionnaire per year. On-site audits are "
      "available to Enterprise customers with 30 days notice.",
      ["30 days"],
      ["Do you allow customer audits?", "Can we perform an on-site audit of your facilities?",
       "What audit rights do customers have?"],
      "Will you permit our auditors to perform an on-site audit of your controls?"),
    # Access control
    T("sso", AC, "prod-sso-scim", "yes",
      "Yes. Corvane Insight supports SAML 2.0 and OpenID Connect single sign-on with any compliant identity provider.",
      ["SAML 2.0"],
      ["Do you support SSO?", "Does the application support SAML single sign-on?",
       "Can users authenticate with our corporate identity provider?"],
      "Is federated single sign-on through our identity provider available?"),
    T("scim", AC, "prod-sso-scim", "yes",
      "Yes. User provisioning and deprovisioning are supported through SCIM 2.0 on the Business and Enterprise plans.",
      ["SCIM 2.0"],
      ["Do you support SCIM?", "Is automated user provisioning supported?",
       "Can accounts be deprovisioned automatically from our directory?"],
      "How are user provisioning changes synced from our directory into your product?"),
    T("mfa", AC, "pol-access-control", "yes",
      "Yes. Multi-factor authentication is enforced for all Corvane workforce accounts and is available to customers "
      "for local logins, with TOTP apps and WebAuthn security keys supported.",
      ["WebAuthn"],
      ["Do you require MFA?", "Is multi-factor authentication available for customer users?",
       "Is MFA enforced for employees?"],
      "Do staff and end users have to use multi-factor authentication?"),
    T("rbac", AC, "pol-access-control", "yes",
      "Yes. The platform provides role-based access control with 5 built-in roles, and custom roles are available on "
      "the Enterprise plan.",
      ["5 built-in roles"],
      ["Do you support role-based access control?", "Can we define custom user roles?",
       "What permission model does the application use?"],
      "How granular are the role-based permissions for different kinds of users?"),
    T("access-review", AC, "pol-access-control", "yes",
      "Yes. Access to production systems is reviewed every 90 days by system owners, and access is revoked within "
      "24 hours of termination.",
      ["90 days", "24 hours"],
      ["How often are user access rights reviewed?", "Do you perform periodic access reviews?",
       "How quickly is access removed when an employee leaves?"],
      "How frequently are production access rights reviewed, and how fast is access revoked at termination?",
      old="Yes. Access to production systems is reviewed every 180 days by system owners, and access is revoked "
          "within 72 hours of termination.", old_date="2023-03-09"),
    T("password", AC, "pol-access-control", "yes",
      "Yes. Local passwords must be at least 12 characters, are checked against a breached password list, and the "
      "account locks after 10 failed attempts.",
      ["12 characters"],
      ["What is your password policy?", "What are the minimum password length requirements?",
       "Do you enforce password complexity?"],
      "Explain the password rules for accounts that do not use single sign-on.",
      old="Yes. Passwords must be at least 8 characters and are rotated every 90 days.", old_date="2022-11-14"),
    T("privileged-access", AC, "pol-access-control", "yes",
      "Yes. Engineers have no standing production access. Access is granted just in time for up to 4 hours, requires a "
      "ticket and peer approval, and every session is recorded.",
      ["4 hours"],
      ["How is privileged access to production controlled?", "Do engineers have standing access to production?",
       "Do you enforce least privilege for administrators?"],
      "Explain the approval process before engineers can access production environments."),
    T("support-access", AC, "pol-access-control", "yes",
      "Yes. Corvane support staff can open a customer workspace only after the customer grants time-limited access "
      "from the admin console, and every action is written to the customer audit log.",
      ["time-limited access"],
      ["Can Corvane employees access our data?", "How is support access to customer tenants controlled?",
       "Do your staff need permission to view customer data?"],
      "Under what conditions can your support staff access our workspace?"),
    T("session-timeout", AC, "pol-access-control", "yes",
      "Yes. Web sessions expire after 30 minutes of inactivity by default, and administrators can set a value between "
      "5 and 480 minutes.",
      ["30 minutes"],
      ["Do sessions time out?", "What is the idle session timeout?", "Can administrators configure session expiry?"],
      "After how long does an inactive session expire?"),
    T("ip-allowlist", AC, "prod-admin-console", "yes",
      "Yes. Enterprise administrators can restrict workspace access to a list of up to 50 IP ranges.",
      ["50 IP ranges"],
      ["Do you support IP allowlisting?", "Can access be restricted to our corporate network?",
       "Can we limit logins to specific IP addresses?"],
      "Is it possible to restrict sign-ins to our office IP ranges?"),
    # Encryption
    T("enc-rest", EN, "pol-encryption", "yes",
      "Yes. All customer data is encrypted at rest with AES-256, including databases, object storage, and backups.",
      ["AES-256"],
      ["Is data encrypted at rest?", "What encryption is used for stored data?", "Are backups encrypted?"],
      "Describe the encryption applied to customer data while it is stored at rest."),
    T("enc-transit", EN, "pol-encryption", "yes",
      "Yes. All connections use TLS 1.2 or higher, and TLS 1.3 is preferred. Older protocols are disabled.",
      ["TLS 1.2"],
      ["Is data encrypted in transit?", "Which TLS versions do you support?", "Do you encrypt network traffic?"],
      "What TLS protocol versions protect data moving between our users and your service?",
      old="Yes. All connections use TLS 1.0 or higher.", old_date="2022-06-30"),
    T("key-mgmt", EN, "pol-key-mgmt", "yes",
      "Yes. Encryption keys are managed in a cloud key management service backed by FIPS 140-2 Level 3 hardware "
      "security modules and are rotated every 12 months.",
      ["12 months"],
      ["How are encryption keys managed?", "How often are encryption keys rotated?",
       "Do you use hardware security modules for key storage?"],
      "Describe the management and rotation of the encryption keys that protect our data."),
    T("byok", EN, "pol-key-mgmt", "partial",
      "Partial. Customer managed keys (BYOK) are available on the Enterprise plan for data at rest in the US and EU "
      "regions. Hold your own key is not supported.",
      ["Enterprise"],
      ["Do you support BYOK?", "Can we bring our own encryption keys?", "Are customer managed keys supported?"],
      "Can we control the encryption keys that protect our stored data with our own keys?"),
    # Data protection
    T("retention-termination", DP, "pol-data-retention", "yes",
      "Yes. Customer data is deleted within 30 days after contract termination, and deletion from backups completes "
      "within a further 35 days.",
      ["30 days"],
      ["What happens to our data at contract termination?", "How long do you retain customer data after termination?",
       "Will you delete our data when the contract ends?"],
      "Describe your data deletion timeline once our contract terminates.",
      old="Yes. Customer data is deleted within 90 days after contract termination.", old_date="2023-02-27"),
    T("log-retention", LG, "pol-logging", "yes",
      "Yes. Security and audit logs are retained for 13 months, with the most recent 90 days searchable online.",
      ["13 months"],
      ["How long are logs retained?", "What is your log retention period?", "How long do you keep audit logs?"],
      "For what period are security and audit logs kept?",
      old="Yes. Security and audit logs are retained for 6 months.", old_date="2023-06-12"),
    T("data-export", DP, "prod-data-export", "yes",
      "Yes. Administrators can export all workspace data at any time in CSV or Parquet format through the console or "
      "the export API.",
      ["Parquet"],
      ["Can we export our data?", "In what formats can data be exported?", "Is data portability supported?"],
      "If we leave, how do we export a complete copy of our data?"),
    T("data-residency", DP, "arch-regions", "yes",
      "Yes. Customers choose one of 3 hosting regions at signup: US (Virginia), EU (Frankfurt), or UK (London). "
      "Customer data stays in the selected region.",
      ["3 hosting regions"],
      ["Where is customer data stored?", "Can we choose the region where our data is hosted?",
       "Do you offer EU data residency?"],
      "In which hosting regions can our data be stored?",
      old="Yes. Customers choose one of 2 hosting regions at signup: US (Virginia) or EU (Frankfurt).",
      old_date="2024-01-18"),
    T("deletion-request", DP, "pol-privacy", "yes",
      "Yes. Individual records can be deleted on request through the API, and data subject requests are completed "
      "within 30 days.",
      ["30 days"],
      ["Can individual records be deleted on request?", "How do you handle data subject requests?",
       "How quickly do you process a right to erasure request?"],
      "How are requests from individuals to delete their personal records fulfilled?"),
    T("data-classification", DP, "pol-data-classification", "yes",
      "Yes. Corvane classifies information as Public, Internal, Confidential, or Restricted. All customer data is "
      "classified as Restricted.",
      ["Restricted"],
      ["Do you have a data classification policy?", "How is customer data classified?",
       "What data classification levels do you use?"],
      "What classification level applies internally to customer data we upload?"),
    T("test-data", DP, "pol-sdlc", "no",
      "No. Production customer data is never copied into development or test environments. Engineers use synthetic "
      "data sets.",
      ["never copied"],
      ["Is production data used for testing?", "Do developers have access to customer data in test environments?",
       "Is customer data copied to non-production environments?"],
      "Could our production data end up in your development or test environments?"),
    T("ai-training", DP, "pol-ai-use", "no",
      "No. Corvane does not use customer data to train machine learning models, and no customer data is sent to a "
      "third-party model provider unless the customer enables the AI assistant.",
      ["does not use customer data to train"],
      ["Do you use customer data to train AI models?", "Is our data used for machine learning training?",
       "Will our data be shared with AI model providers?"],
      "Will anything we upload be used to train machine learning models?"),
    # Infrastructure
    T("hosting", IN, "arch-overview", "yes",
      "Yes. Corvane Insight runs on a major public cloud provider across multiple availability zones in each region. "
      "Corvane does not operate its own data centers.",
      ["availability zones"],
      ["Where is the service hosted?", "Do you operate your own data centers?",
       "Which infrastructure provider hosts the platform?"],
      "Describe the hosting environment and data centers for the production service."),
    T("multi-tenancy", IN, "arch-overview", "yes",
      "Yes. The platform is multi-tenant. Each customer workspace is isolated by a tenant id enforced in the data "
      "access layer and has a separate encryption key per tenant.",
      ["separate encryption key per tenant"],
      ["Is the platform multi-tenant?", "How is customer data segregated from other customers?",
       "How do you isolate tenants?"],
      "What prevents another tenant from seeing our records in a multi-tenant environment?"),
    T("single-tenant", IN, "arch-deployment-options", "partial",
      "Partial. A dedicated single-tenant deployment is available on the Enterprise plan for an additional fee. "
      "On-premises deployment is not offered.",
      ["single-tenant"],
      ["Do you offer a single-tenant deployment?", "Can the product be installed on premises?",
       "Is a dedicated environment available?"],
      "Can we get a dedicated single-tenant instance or an on-premises install?"),
    T("network-security", IN, "arch-network", "yes",
      "Yes. Production runs in private subnets with no public IP addresses. Only load balancers are internet-facing, "
      "and a web application firewall filters all inbound traffic.",
      ["web application firewall"],
      ["How is the production network segmented?", "Do you use a web application firewall?",
       "Describe your network security controls."],
      "Which network controls, such as a firewall, protect the production servers?"),
    T("architecture", IN, "arch-overview", "yes",
      "Yes. The platform consists of a web application, a REST API, a query engine, and a columnar storage layer, "
      "deployed as containers on managed Kubernetes.",
      ["Kubernetes"],
      ["Describe your application architecture.", "Can you provide an architecture overview?",
       "What are the main components of the platform?"],
      "Give a high-level overview of the platform architecture and how its components are deployed."),
    T("ddos", IN, "arch-network", "yes",
      "Yes. DDoS protection is provided at the network edge by the cloud provider and the content delivery network, "
      "with rate limiting at the API gateway.",
      ["rate limiting"],
      ["Do you have DDoS protection?", "How do you mitigate denial of service attacks?",
       "Is the service protected against volumetric attacks?"],
      "How is the service protected if an attacker floods it with a denial of service attack?"),
    T("os-hardening", IN, "arch-hosts", "yes",
      "Yes. Hosts run a hardened minimal Linux image built from CIS benchmarks and are replaced, not patched in place, "
      "at least every 30 days.",
      ["30 days"],
      ["Are servers hardened?", "Do you follow CIS benchmarks?", "How are operating systems patched?"],
      "How do you keep server operating systems hardened and patched?"),
    # Business continuity
    T("backups", BC, "pol-bcdr", "yes",
      "Yes. Customer data is backed up every 4 hours. Backups are encrypted, stored in a second region, and retained "
      "for 35 days.",
      ["4 hours", "35 days"],
      ["How often is customer data backed up?", "How long are backups retained?", "Are backups stored offsite?"],
      "Describe the frequency, location, and retention of your data backups.",
      old="Yes. Customer data is backed up every 24 hours and backups are retained for 30 days.",
      old_date="2023-04-03"),
    T("rpo-rto", BC, "pol-bcdr", "yes",
      "Yes. The recovery point objective is 4 hours and the recovery time objective is 8 hours for a full region "
      "failure.",
      ["4 hours", "8 hours"],
      ["What are your RPO and RTO?", "What is your recovery time objective?", "What is your recovery point objective?"],
      "What recovery point and recovery time objectives apply if a whole region fails?",
      contra="Yes. The recovery point objective is 1 hour and the recovery time objective is 4 hours."),
    T("dr-test", BC, "pol-bcdr", "yes",
      "Yes. The disaster recovery plan is tested every 12 months with a full regional failover exercise. The last test "
      "was completed on 2026-04-14.",
      ["12 months"],
      ["Do you test your disaster recovery plan?", "When was the last DR test?",
       "How often are failover exercises conducted?"],
      "Is the disaster recovery plan exercised in practice, and when was it last tested?"),
    T("bcp", BC, "pol-bcdr", "yes",
      "Yes. Corvane maintains a business continuity plan, reviewed every 12 months, that covers loss of offices, key "
      "staff, and critical vendors.",
      ["business continuity plan"],
      ["Do you have a business continuity plan?", "Is your BCP reviewed regularly?",
       "How do you plan for business disruption?"],
      "What business continuity arrangements keep the company operating through a major disruption?"),
    T("uptime-history", BC, "prod-status", "yes",
      "Yes. Measured availability over the last 12 months was 99.97%. Historical uptime is published on the public "
      "status page.",
      ["99.97%"],
      ["What was your uptime over the last year?", "Can you share historical availability?",
       "What availability have you achieved?"],
      "What availability did customers actually experience over the last year?"),
    # Incident response
    T("ir-plan", IR, "pol-incident-response", "yes",
      "Yes. Corvane maintains a documented incident response plan with defined severity levels, an on-call rotation, "
      "and a tabletop exercise every 6 months.",
      ["6 months"],
      ["Do you have an incident response plan?", "Is the incident response plan tested?",
       "Describe your incident response process."],
      "How is a security incident handled from detection to closure, and how is the response plan rehearsed?"),
    T("breach-notification", IR, "pol-incident-response", "yes",
      "Yes. Corvane notifies affected customers of a confirmed security breach involving their data within 48 hours.",
      ["48 hours"],
      ["How quickly will you notify us of a breach?", "What is your breach notification timeline?",
       "Will you inform customers of security incidents?"],
      "If our data is affected by a security breach, how soon will you notify us?",
      old="Yes. Corvane notifies affected customers of a confirmed security breach involving their data within 72 hours.",
      old_date="2023-09-05"),
    T("breach-history", IR, "pol-incident-response", "no",
      "No. Corvane has not had a security breach involving customer data in the last 5 years.",
      ["5 years"],
      ["Have you had a data breach?", "Have you experienced any security incidents involving customer data?",
       "Disclose any breaches in recent years."],
      "Has customer data ever been exposed in a security breach of your systems?"),
    T("forensics", IR, "pol-incident-response", "yes",
      "Yes. Corvane keeps an external incident response firm on retainer and preserves forensic evidence for at least "
      "12 months after an incident.",
      ["retainer"],
      ["Do you have forensic capabilities?", "Do you retain an incident response firm?",
       "How long is incident evidence preserved?"],
      "Who would carry out forensic investigation of a serious incident, and how is evidence preserved?"),
    # Vulnerability management
    T("vuln-scanning", VM, "pol-vuln-mgmt", "yes",
      "Yes. Infrastructure and container images are scanned for vulnerabilities daily, and application dependencies "
      "are scanned on every build.",
      ["daily"],
      ["Do you perform vulnerability scanning?", "How often are systems scanned for vulnerabilities?",
       "Are third-party dependencies scanned?"],
      "How do you scan your software and infrastructure for known vulnerabilities?"),
    T("patch-sla", VM, "pol-vuln-mgmt", "yes",
      "Yes. Critical vulnerabilities are remediated within 7 days, high within 30 days, and medium within 90 days.",
      ["7 days"],
      ["What are your patching timelines?", "How quickly are critical vulnerabilities fixed?",
       "Do you have vulnerability remediation SLAs?"],
      "Once a critical vulnerability is found, how long until it is remediated?",
      old="Yes. Critical vulnerabilities are remediated within 30 days and high within 60 days.", old_date="2023-07-17"),
    T("bug-bounty", VM, "pol-vuln-mgmt", "yes",
      "Yes. Corvane runs a public vulnerability disclosure program and a private bug bounty program managed by an "
      "external platform.",
      ["bug bounty"],
      ["Do you have a bug bounty program?", "Do you have a responsible disclosure policy?",
       "How can researchers report vulnerabilities?"],
      "Is there a way for outside researchers to report vulnerabilities, such as a bug bounty?"),
    T("malware", VM, "pol-endpoint", "yes",
      "Yes. All employee laptops run endpoint detection and response software, and files uploaded to the platform are "
      "scanned for malware.",
      ["endpoint detection and response"],
      ["Do you use anti-malware software?", "Are employee devices protected against malware?",
       "Are uploaded files scanned for viruses?"],
      "How do you protect employee laptops and uploaded files against malware?"),
    # Logging
    T("audit-log", LG, "prod-audit-log", "yes",
      "Yes. The customer audit log records logins, permission changes, exports, and API key events, and can be "
      "streamed to a SIEM through a webhook or downloaded as JSON.",
      ["SIEM"],
      ["Do you provide audit logs to customers?", "Can audit logs be exported to our SIEM?",
       "What user activity is logged?"],
      "Can our security team see an audit log of who did what in our workspace and send it to our SIEM?"),
    T("monitoring", LG, "pol-logging", "yes",
      "Yes. Security events are monitored 24 hours a day by an internal security operations team using a SIEM with "
      "automated alerting.",
      ["24 hours a day"],
      ["Do you have 24x7 security monitoring?", "Do you operate a security operations center?",
       "How are security events monitored?"],
      "Who monitors security events in your environment, and at what hours?"),
    # Vendor management
    T("subprocessors", VE, "legal-subprocessors", "yes",
      "Yes. Corvane uses 9 subprocessors. The current list is published on the trust center, and customers are "
      "notified 30 days before a new subprocessor is added.",
      ["9 subprocessors", "30 days"],
      ["Do you use subprocessors?", "Can you provide a list of subprocessors?",
       "Will you notify us of new subprocessors?"],
      "Which subprocessors handle our data, and how are new ones communicated?",
      old="Yes. Corvane uses 6 subprocessors and notifies customers 14 days before a new subprocessor is added.",
      old_date="2023-10-02"),
    T("vendor-risk", VE, "pol-vendor-mgmt", "yes",
      "Yes. Vendors with access to customer data are assessed before onboarding and reviewed every 12 months, "
      "including a review of their SOC 2 or ISO 27001 report.",
      ["before onboarding"],
      ["Do you assess the security of your vendors?", "Do you have a third-party risk management program?",
       "How are suppliers reviewed?"],
      "How do you assess the security of the vendors who handle our data?"),
    T("offshore", VE, "pol-privacy", "partial",
      "Partial. Customer data is stored only in the selected region. Support staff in the US, UK, and Portugal may "
      "access data with customer permission.",
      ["Portugal"],
      ["Is customer data accessed from outside our region?", "Do you use offshore support staff?",
       "From which countries can staff access customer data?"],
      "In which countries are staff located who might access our data?"),
    # SLA and support
    T("sla-uptime", SL, "legal-sla", "yes",
      "Yes. Corvane commits to 99.9% monthly uptime for the Business plan and 99.95% for the Enterprise plan, with "
      "service credits of up to 25% of monthly fees.",
      ["99.9%", "99.95%"],
      ["What is your uptime SLA?", "Do you offer service credits?", "What availability do you guarantee?"],
      "What uptime commitment is in the contract, and what service credits apply if it is missed?",
      old="Yes. Corvane commits to 99.5% monthly uptime for all plans.", old_date="2022-09-12"),
    T("support-hours", SL, "prod-support", "yes",
      "Yes. Standard support is available 9am to 6pm on business days. Enterprise customers get 24x7 support for "
      "Severity 1 issues.",
      ["24x7"],
      ["What are your support hours?", "Is 24x7 support available?", "How can we contact support?"],
      "When is your support team available?"),
    T("response-times", SL, "prod-support", "yes",
      "Yes. Severity 1 issues receive a response within 1 hour for Enterprise customers and within 4 hours for "
      "Business customers.",
      ["1 hour"],
      ["What are your support response times?", "How quickly do you respond to critical issues?",
       "What is the response SLA for Severity 1 tickets?"],
      "If production is down for us, how fast will support respond to a Severity 1 issue?",
      old="Yes. Severity 1 issues receive a response within 2 hours for all customers.", old_date="2023-11-20"),
    T("maintenance", SL, "legal-sla", "yes",
      "Yes. Planned maintenance is announced at least 5 business days in advance and is scheduled on Sundays between "
      "02:00 and 06:00 UTC. Most releases need no downtime.",
      ["5 business days"],
      ["How is planned maintenance communicated?", "When are maintenance windows scheduled?",
       "Do updates cause downtime?"],
      "How much notice do we get before planned maintenance?"),
    T("status-page", SL, "prod-status", "yes",
      "Yes. A public status page shows current availability and incident history, and customers can subscribe to "
      "email or webhook notifications.",
      ["status page"],
      ["Do you have a status page?", "How are outages communicated?", "Can we subscribe to incident notifications?"],
      "Where can we check the current status and incident history of the service?"),
    # Product
    T("api", PR, "prod-api", "yes",
      "Yes. Corvane Insight provides a REST API documented with OpenAPI 3.1, authenticated with scoped API keys or "
      "OAuth 2.0 client credentials.",
      ["OpenAPI 3.1"],
      ["Do you provide an API?", "Is the API documented?", "How is the API authenticated?"],
      "Can our engineers automate the platform through an API, and how is it authenticated?"),
    T("api-rate-limits", PR, "prod-api", "yes",
      "Yes. The API allows 600 requests per minute per workspace on the Business plan and 3,000 requests per minute on "
      "the Enterprise plan.",
      ["600 requests per minute"],
      ["Are there API rate limits?", "How many API calls can we make?", "What are the API throttling limits?"],
      "What request limits apply to the API?"),
    T("integrations", PR, "prod-connectors", "yes",
      "Yes. Native connectors are available for 40 data sources, including cloud data warehouses, object storage, and "
      "relational databases.",
      ["40 data sources"],
      ["What integrations do you support?", "Which data sources can be connected?", "Do you have native connectors?"],
      "Which data sources can we connect through connectors?"),
    T("mobile", PR, "prod-overview", "no",
      "No. Corvane Insight does not offer a native mobile app. The web application is responsive and supported on "
      "current mobile browsers.",
      ["does not offer a native mobile app"],
      ["Do you have a mobile app?", "Is there an iOS or Android application?", "Can the product be used on phones?"],
      "Can field staff use the product from a mobile phone app?"),
    T("accessibility", PR, "prod-accessibility", "partial",
      "Partial. The web application targets WCAG 2.1 AA. A third-party audit in 2026 found 4 open issues, which are "
      "scheduled for remediation.",
      ["WCAG 2.1 AA"],
      ["Is the product accessible?", "Do you conform to WCAG?", "Do you have a VPAT or accessibility statement?"],
      "Is the interface accessible for employees who use assistive technology, for example under WCAG?"),
    T("browsers", PR, "prod-overview", "yes",
      "Yes. The latest two versions of all major desktop browsers are supported.",
      ["latest two versions"],
      ["Which browsers are supported?", "Do you support all major browsers?", "Are there browser requirements?"],
      "Which web browsers do our users need to run the application?"),
    T("ai-assistant", PR, "pol-ai-use", "yes",
      "Yes. The optional AI assistant answers questions about dashboards. It is off by default, an administrator must "
      "enable it, and prompts are not retained by the model provider.",
      ["off by default"],
      ["Does the product include AI features?", "Can AI features be disabled?",
       "Are prompts to the AI assistant retained?"],
      "Is generative AI built into the product, and can an administrator disable the AI assistant?"),
    T("sandbox", PR, "prod-environments", "yes",
      "Yes. Enterprise customers receive 1 non-production sandbox workspace for testing, refreshed on request.",
      ["sandbox"],
      ["Do you provide a sandbox environment?", "Is a test environment available?",
       "Can we test changes outside production?"],
      "Is there a sandbox where our team can test configuration changes?"),
    T("storage-limits", PR, "com-pricing", "yes",
      "Yes. Workspaces on the Business plan include 500 GB of storage and Enterprise plans include 5 TB, with "
      "additional storage billed per TB.",
      ["500 GB"],
      ["What are the storage limits?", "How much data can we store?", "Is additional storage available?"],
      "How much storage is included in each plan?"),
    # Commercial
    T("pricing-model", CO, "com-pricing", "yes",
      "Yes. Corvane Insight is priced per named user per year, with 3 plans: Team, Business, and Enterprise. Volume "
      "discounts start at 100 users.",
      ["per named user"],
      ["How is the product priced?", "What is your pricing model?", "Do you offer volume discounts?"],
      "Explain the pricing model and the plans available."),
    T("payment-terms", CO, "com-order-terms", "yes",
      "Yes. Invoices are issued annually in advance and payment terms are net 30 days.",
      ["net 30"],
      ["What are your payment terms?", "How are invoices issued?", "Do you bill annually or monthly?"],
      "When are we invoiced and what are the payment terms?",
      old="Yes. Invoices are issued annually in advance and payment terms are net 45 days.", old_date="2023-12-01"),
    T("price-increase", CO, "com-order-terms", "yes",
      "Yes. Renewal price increases are capped at 5% per year for multi-year agreements.",
      ["5%"],
      ["Is there a cap on renewal price increases?", "How much can prices rise at renewal?",
       "Do you offer price protection?"],
      "What cap applies to price increases when we renew?",
      old="Yes. Renewal price increases are capped at 7% per year for multi-year agreements.", old_date="2024-02-09"),
    T("termination", CO, "legal-msa", "yes",
      "Yes. Either party may terminate for material breach with 30 days written notice if the breach is not cured, "
      "and prepaid fees are refunded pro rata when Corvane is in breach.",
      ["material breach"],
      ["What are the termination terms?", "Can we terminate for convenience?", "Are fees refunded on termination?"],
      "Under what terms can we terminate the agreement early?"),
    T("liability", CO, "legal-msa", "partial",
      "Partial. Liability is capped at 12 months of fees paid. Uncapped liability is not offered, but a higher cap of "
      "2 times annual fees for data breaches is available on Enterprise agreements.",
      ["12 months of fees"],
      ["What is your limitation of liability?", "Will you accept uncapped liability?",
       "Is there a separate liability cap for data breaches?"],
      "How is liability limited under the contract?"),
    T("trial", CO, "com-pricing", "yes",
      "Yes. A 14 day free trial of the Business plan is available with sample data.",
      ["14 day"],
      ["Do you offer a free trial?", "Can we evaluate the product before buying?", "Is a proof of concept available?"],
      "Can we try the software in a free trial first?"),
    # HR security
    T("background-checks", HR, "pol-hr-security", "yes",
      "Yes. All employees and contractors pass a background check before they start, where local law allows.",
      ["background check"],
      ["Do you perform background checks?", "Are employees screened before hire?", "Are contractors vetted?"],
      "Do new employees and contractors go through background checks?"),
    T("security-training", HR, "pol-hr-security", "yes",
      "Yes. All staff complete security awareness training at hire and every 12 months, engineers complete secure "
      "coding training every 12 months, and phishing simulations run monthly.",
      ["12 months"],
      ["Do employees receive security awareness training?", "How often is security training completed?",
       "Do you run phishing simulations?"],
      "How often does your workforce complete security awareness training?"),
    T("confidentiality", HR, "pol-hr-security", "yes",
      "Yes. All employees and contractors sign confidentiality agreements before they receive system access.",
      ["confidentiality agreements"],
      ["Do employees sign NDAs?", "Are staff bound by confidentiality agreements?",
       "Do contractors sign confidentiality terms?"],
      "Are your employees bound by confidentiality agreements to keep our information private?"),
    # Secure development
    T("code-review", SD, "pol-sdlc", "yes",
      "Yes. Every code change requires review and approval by a second engineer, and automated tests and static "
      "analysis must pass before merge.",
      ["second engineer"],
      ["Do you perform code reviews?", "Do you use static analysis?", "Describe your secure development lifecycle."],
      "What code review and testing does new software go through before release?"),
    T("change-mgmt", SD, "pol-change-mgmt", "yes",
      "Yes. Production changes go through a change management process with peer review, automated deployment, and a "
      "rollback plan. Emergency changes are reviewed within 2 business days.",
      ["rollback plan"],
      ["Do you have a change management process?", "How are production changes approved?",
       "How are emergency changes handled?"],
      "How do you control and approve changes to the production environment?"),
    T("sbom", SD, "pol-sdlc", "yes",
      "Yes. A software bill of materials is generated for every release in CycloneDX format and is available to "
      "Enterprise customers on request.",
      ["CycloneDX"],
      ["Do you provide an SBOM?", "Can you share a software bill of materials?", "Do you track open source components?"],
      "Can we get a software bill of materials for the components in your product?"),
]

# Questions the knowledge base has no answer for. A good system routes these to a subject matter expert.
UNANSWERABLE = [
    "What is the coverage limit of your cyber liability insurance policy?",
    "Do you hold FedRAMP Moderate authorization?",
    "What percentage of annual revenue do you spend on information security?",
    "Do you support quantum-resistant cryptography for data at rest?",
    "Do you hold a CMMC Level 2 certification?",
    "Describe your carbon emissions reporting for data center usage.",
    "How many customers in the aviation sector use your platform?",
    "What is the annual turnover rate on your security team?",
    "Is your company financially audited by a Big Four accounting firm?",
    "Do you support deployment inside our own air-gapped classified enclave with FIPS 140-3 validated modules?",
]

# Docs that hold no single topic fact but make the corpus realistic. Text is plain policy prose.
EXTRA_DOCS = {
    "pol-acceptable-use": ("Acceptable Use Policy", "Compliance",
        "Corvane systems are provided for business use. Employees must not install unapproved software, share "
        "credentials, or move company data to personal storage. Violations are handled by People Operations."),
    "pol-asset-mgmt": ("Asset Management Policy", "Infrastructure",
        "Every laptop, server image, and cloud account is recorded in the asset inventory with an owner. The "
        "inventory is reconciled every quarter, and lost devices are wiped remotely."),
    "pol-physical-security": ("Physical Security Policy", "Infrastructure",
        "Corvane offices use badge access and visitor logs. Production infrastructure is hosted by the cloud "
        "provider, whose facilities are covered by its own audited physical controls."),
    "pol-risk-mgmt": ("Risk Management Policy", "Compliance",
        "The security team maintains a risk register. Risks are scored by likelihood and impact, assigned an owner, "
        "and reviewed by the leadership team every quarter."),
    "pol-secrets": ("Secrets Management Standard", "Secure Development",
        "Application secrets are stored in a managed secrets vault and injected at runtime. Secrets in source code "
        "are blocked by a pre-merge scanner."),
    "pol-mobile-devices": ("Mobile Device Standard", "HR Security",
        "Phones used for work email must be enrolled in device management with a screen lock and encryption enabled."),
    "pol-remote-work": ("Remote Work Standard", "HR Security",
        "Remote staff connect through a zero trust access gateway. Public Wi-Fi is allowed only with the gateway "
        "enabled."),
    "pol-information-security": ("Information Security Policy", "Compliance",
        "The Information Security Policy sets the baseline for all other policies. It is owned by the Head of "
        "Security, approved by the leadership team, and reviewed every 12 months."),
    "prod-dashboards": ("Dashboards Guide", "Product",
        "Dashboards combine charts, tables, and filters. Users can schedule a dashboard to be emailed as a PDF and "
        "share it with other members of the workspace."),
    "prod-query-engine": ("Query Engine Guide", "Product",
        "The query engine runs SQL over columnar storage. Queries time out after 10 minutes, and results are cached "
        "for 15 minutes unless the user forces a refresh."),
    "prod-alerts": ("Metric Alerts Guide", "Product",
        "Metric alerts evaluate a query on a schedule and notify a channel when a threshold is crossed. Alerts can "
        "notify by email or webhook."),
    "prod-release-notes-6-2": ("Release Notes 6.2", "Product",
        "Version 6.2 adds Parquet export, the UK hosting region, and custom roles for Enterprise workspaces. It also "
        "updates the default session timeout behavior."),
    "com-professional-services": ("Professional Services Terms", "Commercial",
        "Onboarding packages include data modeling workshops and dashboard design sessions. Services are billed as "
        "fixed-fee packages and are scheduled after the order form is signed."),
    "legal-trust-center": ("Trust Center Overview", "Compliance",
        "The trust center hosts the subprocessor list, the security whitepaper, and a request form for the SOC 2 "
        "report and penetration test summary."),
    "legal-cookie-policy": ("Cookie Policy", "Data Protection",
        "The web application uses strictly necessary cookies for login sessions. Analytics cookies are off unless a "
        "user consents."),
    "pol-password-standard": ("Password Standard", "Access Control",
        "Service accounts use generated credentials stored in the secrets vault. Shared human accounts are not "
        "permitted."),
    "pol-cryptography-guidelines": ("Cryptography Guidelines", "Encryption",
        "Engineers must use the approved cryptography library. Custom algorithms and deprecated hash functions are "
        "not permitted in new code."),
    "prod-sharing": ("Sharing and Permissions Guide", "Product",
        "Dashboards can be shared with workspace members or groups. Public links are disabled by default and an "
        "administrator can turn them off for the whole workspace."),
    "prod-embedding": ("Embedded Analytics Guide", "Product",
        "Dashboards can be embedded in customer applications with signed embed tokens that expire after a short "
        "period."),
    "pol-capacity": ("Capacity Management Standard", "Infrastructure",
        "Compute and storage capacity is tracked against forecasts, and autoscaling handles daily peaks."),
    "pol-exceptions": ("Policy Exception Procedure", "Compliance",
        "Exceptions to security policy need a written risk acceptance from the Head of Security and expire after "
        "one year at most."),
    "com-renewals": ("Renewals Guide", "Commercial",
        "The account team contacts customers before renewal to review usage, seats, and plan fit."),
}

DOC_TITLES = {
    "pol-compliance-program": "Compliance Program Overview",
    "pol-privacy": "Privacy and Data Processing Policy",
    "pol-vuln-mgmt": "Vulnerability Management Policy",
    "legal-msa": "Master Subscription Agreement Summary",
    "prod-sso-scim": "SSO and SCIM Guide",
    "pol-access-control": "Access Control Policy",
    "prod-admin-console": "Admin Console Guide",
    "pol-encryption": "Encryption Standard",
    "pol-key-mgmt": "Key Management Standard",
    "pol-data-retention": "Data Retention and Deletion Policy",
    "pol-logging": "Logging and Monitoring Standard",
    "prod-data-export": "Data Export Guide",
    "arch-regions": "Hosting Regions",
    "pol-data-classification": "Data Classification Policy",
    "pol-sdlc": "Secure Development Lifecycle Policy",
    "pol-ai-use": "AI Use and Model Data Policy",
    "arch-overview": "Architecture Overview",
    "arch-deployment-options": "Deployment Options",
    "arch-network": "Network Security Architecture",
    "arch-hosts": "Host Hardening Standard",
    "pol-bcdr": "Business Continuity and Disaster Recovery Policy",
    "prod-status": "Status Page and Availability",
    "pol-incident-response": "Incident Response Plan",
    "pol-endpoint": "Endpoint Security Standard",
    "prod-audit-log": "Audit Log Guide",
    "legal-subprocessors": "Subprocessor List",
    "pol-vendor-mgmt": "Vendor Risk Management Policy",
    "legal-sla": "Service Level Agreement",
    "prod-support": "Support Policy",
    "prod-api": "API Reference Overview",
    "prod-connectors": "Data Connectors Guide",
    "prod-overview": "Product Overview",
    "prod-accessibility": "Accessibility Statement",
    "prod-environments": "Environments Guide",
    "com-pricing": "Pricing and Plans",
    "com-order-terms": "Order Form Terms",
    "pol-hr-security": "Personnel Security Policy",
    "pol-change-mgmt": "Change Management Policy",
}

SUBPROCESSORS = [
    ("Cloud infrastructure provider", "Hosting and storage", "Region selected by customer"),
    ("Content delivery network", "Edge caching and DDoS protection", "Global"),
    ("Email delivery service", "Transactional email", "US"),
    ("Support ticketing platform", "Customer support tickets", "US and EU"),
    ("Payment processor", "Subscription billing", "US"),
    ("Error monitoring service", "Application error reports", "US"),
    ("Log analytics service", "Security log storage", "Region selected by customer"),
    ("AI model provider", "AI assistant, only when enabled", "US and EU"),
    ("Identity verification service", "Employee background checks", "US and UK"),
]

APPROVERS = ["security-lead", "legal-counsel", "product-manager", "grc-analyst", "solutions-architect",
             "privacy-officer"]
