# Project requirements

## Identity and scope

- The presentation and publication title is **Multi-Agentic Workflow on AWS**.
- Attribute the work to **Yves Schillings, Secloudis** and refer to https://secloudis.com/.
- Use **Yves Schillings** as the Git author name with the owner's existing Git email. Do not add AI-tool co-author trailers, generated-by signatures or session links to commits or pull requests unless the owner explicitly requests them.
- Use the actual approved Secloudis slide layout, logo, typography and visual assets for published presentation material. Preserve source reference files.
- Complete and verify the AWS/Bedrock deployment first. An Azure edition is a separate later phase.
- Keep client identities, private source documents and credentials outside this repository and public material.
- Position the project as an intended open-source foundation that companies can reuse and adapt, with code on GitHub, a demonstration and a Secloudis publication. Distinguish this intention from verified publication and licensing status.
- Public slides and documentation must remain useful over time. Use delivery stages and acceptance outcomes rather than Monday, interview dates or the author's personal preparation calendar.
- Explain reusable platform components, company-specific integration work and measurable business value without claiming proven return on investment or production readiness.
- The approved cover uses the original multi-agent illustration at `docs/assets/cover/multi-agentic-workflow-secloudis.png`. Preserve the Secloudis circular layout and logo when using it.
- Multiple companies must be able to use the same Factory through authenticated APIs. Explain the shared platform, company-specific identities/data/execution/releases and explicitly authorised collaboration projects as distinct concerns.
- Derive company and project authority from verified identity and server-owned policy. Sharing a workflow never implies permission to another company's data or release environment.
- Distinguish multi-company use from multi-cloud deployment. The first shared Factory runs on AWS; cross-cloud connectors and an Azure edition are later, separately verified work.
- The agreed application-generation demonstration is the existing CSV-to-consultation case: one shared, read-only application for synthetic affiliation records from three anonymised companies. Show search, filters, effective dates and company-specific permissions. Retrieval of design documents is context for the Factory; it is not a replacement business case.
- The global architecture must visibly include all three companies, their people, owned data and API boundaries, the shared Factory, and the shared generated application. Label the permitted exchanges and their return paths. A common platform does not imply reciprocal or unrestricted data access.
- Use only the generic labels **Company 1**, **Company 2** and **Company 3** in public target architecture diagrams, with no specific or fictional company names. Explain human actors and responsibilities: business requesters/owners, data and API owners, authorised gate approvers, platform engineers, operators and application users. Distinguish these people from the five software worker roles.
- Distinguish Company 1/2/3 from three separately visible external examples, **External organisation A/B/C**. The source says external bodies such as these; do not infer an exhaustive six-company legal requirement. Keep the shared platform team/operator and implementation partner as separate delivery responsibilities. Do not substitute them for the external organisations.
- Call the common application **Shared Business Platform**. Explain each box with its business function, synthetic example, hosting and exchanges. All three companies retain the same general member/affiliation/rights capability. Proposed external fixture roles are A exchange intermediary, B versioned illustrative reference, C coverage institution; no automatic legal decision or verified live external API is claimed.
- AWS hosts the proposed Factory and POC application. Real company and external hosting may be AWS, Azure, another cloud or on-premises and remains unverified. External business connectors are selective, not a mandatory chain; no MCP server or Factory tenant is presumed for an external organisation.
- Public runtime contracts remain target work. Use separate backend service identity and owner-registered grants; plain company/project fields are not authority. Cognito client-credentials M2M does not support resource binding/aud: use custom API scopes and client_id allowlists with verified issuer/signature/expiry/token_use plus resource policy. Never forward a human or MCP token to a business API.
- Use a code-first target: Python/FastAPI for service entry and authorization, LangGraph for the explicit workflow, LangChain AWS for the Bedrock model adapter, and the MCP Python SDK for approved company tools. Distinguish the preserved plain-Python baseline from the local deterministic LangGraph Factory increment and from the complete cloud target. Simulated local gates, inert code proposals and proposed tests are not real human authentication, generated application execution or an AWS release.
- Show one company-owned remote MCP interface per company, linked to its authorized business APIs. Spell out MCP as Model Context Protocol. The generated application's ordinary business API calls run independently of the agent workflow used to build it.

## Architecture fidelity and readable labels

- Slide 03 is the complete logical architecture. Preserve its individual components, responsibility labels, flow labels and arrow directions. Do not merge or simplify a user-supplied reference diagram without an explicit request.
- Keep the context service, sandbox runner, evidence store, run-state store, repository/pipeline and target application as distinct components.
- Define acronyms on every slide where they appear. Definitions on a later slide, in speaker notes or in a final glossary are insufficient.
- Whenever a slide mentions Fargate, explain its role directly below the relevant label or component: it runs application containers while AWS manages the underlying servers. Apply this to the Factory runtime and separate sandbox tasks. Do not rely on a later slide or speaker notes for this explanation.
- Explain a worker profile as a software role with a task, instructions, permitted tools and an expected result. Show the five roles' business functions and their location in the Python/LangGraph application, distinguish the application container infrastructure from Bedrock model inference, and retain the separate sandbox boundary. The five roles are Analyst, Architect, Code Author, Tester and Reviewer; Reviewer is one role.
- Keep the architecture responsibility labels `Amazon Bedrock: inference` and `Secloudis: builds pipeline` each on one line. Widen their capsules instead of wrapping the labels.
- **G means Gate, a human approval checkpoint.** Use the explicit labels **G1 Scope**, **G2 Design**, **G3 Quality** and **G4 Release**. Show all four together in the global logical and AWS architecture diagrams.
- Never leave a label such as G4 unexplained. Release approval authorises deployment of the exact reviewed version. Use the gate name beside its code on other slides too.
- Slides and native bulleted speaker notes are in English. Keep diagrams editable and verify the rendered slides, including their acronym definitions and Secloudis branding.
- Increment delivered PPTX/PDF filenames together and preserve earlier deliveries. Document release numbers belong in filenames, not visible slide content or notes.

## Evidence and documentation

- Separate implemented local behavior, cloud adapters/infrastructure definitions, target architecture and verified AWS results.
- The baseline three-role/one-decision workflow must not be described as the completed five-worker/four-gate Factory.
- Keep README links, numbered engineering pages, slide exports and the article aligned with the delivered deck.
- Record actual test/deployment evidence for its exact revision. A diagram, mock result or Terraform validation is not proof of a live AWS deployment.
