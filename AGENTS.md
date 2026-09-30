# Project requirements

## Identity and scope

- The presentation and publication title is **Multi-Agentic Workflow on AWS**.
- Attribute the work to **Yves Schillings, Secloudis** and refer to https://secloudis.com/.
- Use the actual approved Secloudis slide layout, logo, typography and visual assets for published presentation material. Preserve source reference files.
- Complete and verify the AWS/Bedrock deployment first. An Azure edition is a separate later phase.
- Keep client identities, private source documents and credentials outside this repository and public material.

## Architecture fidelity and readable labels

- Slide 03 is the complete logical architecture. Preserve its individual components, responsibility labels, flow labels and arrow directions. Do not merge or simplify a user-supplied reference diagram without an explicit request.
- Keep the context service, sandbox runner, evidence store, run-state store, repository/pipeline and target application as distinct components.
- Define acronyms on every slide where they appear. Definitions on a later slide, in speaker notes or in a final glossary are insufficient.
- **G means Gate, a human approval checkpoint.** Use the explicit labels **G1 Scope**, **G2 Design**, **G3 Quality** and **G4 Release**. Show all four together in the global logical and AWS architecture diagrams.
- Never leave a label such as G4 unexplained. Release approval authorises deployment of the exact reviewed version. Use the gate name beside its code on other slides too.
- Slides and native bulleted speaker notes are in English. Keep diagrams editable and verify the rendered slides, including their acronym definitions and Secloudis branding.
- Increment delivered PPTX/PDF filenames together and preserve earlier deliveries. Document release numbers belong in filenames, not visible slide content or notes.

## Evidence and documentation

- Separate implemented local behavior, cloud adapters/infrastructure definitions, target architecture and verified AWS results.
- The baseline three-role/one-decision workflow must not be described as the completed five-worker/four-gate Factory.
- Keep README links, the sixteen numbered engineering pages, slide exports and the article aligned with the delivered deck.
- Record actual test/deployment evidence for its exact revision. A diagram, mock result or Terraform validation is not proof of a live AWS deployment.
