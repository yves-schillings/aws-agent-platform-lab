# Monday demonstration and explanation

Use the statements that match the evidence from the run being shown. Until an AWS
run succeeds, say **implemented locally, cloud deployment pending**. A mock answer
does not establish that Bedrock, cloud identity or the vector index works.

## Five-minute demonstration

1. Show the GitHub source and the deployed image's commit identifier.
2. Show the application mode. Sign in as the Alpha demonstration user.
3. Submit: “Prepare a synthetic document checklist. Explain missing evidence, cite
   the available sources and retain a human decision before publication.”
4. Open a cited source. Explain its document identifier, version and tenant.
5. Show analyst, designer and reviewer stages, the fixed MCP checklist result and
   the final artifact hash. Explain that the tool is application-selected.
6. Approve that exact artifact. Show the recorded authenticated decision. In local
   mode the identity is explicitly simulated.
7. Sign in as Beta and attempt the Alpha run URL. The service must refuse access.
   Run the same question again and inspect only Beta sources.
8. Show a trace, measured latency and returned token counts. If price inputs are
   unavailable, say the cost is unknown. Explain the tested rollback procedure.

## Explanations to practise

| Component | English | Nederlands |
|---|---|---|
| Overall flow | I built a small platform that retrieves authorized documents, passes them through three bounded agent roles and records a human decision on the exact result. | Ik heb een klein platform gebouwd dat toegelaten documenten ophaalt, ze door drie afgebakende agentrollen verwerkt en een menselijke beslissing over het exacte resultaat vastlegt. |
| Fargate | Fargate runs the application container. ECS Express Mode prepares the service and its HTTPS entry point. | Fargate voert de applicatiecontainer uit. ECS Express Mode maakt de dienst en het HTTPS-toegangspunt aan. |
| Cognito | Cognito authenticates the user. My API verifies the signed access token and derives document permissions from a server-owned group policy. | Cognito authenticeert de gebruiker. Mijn API controleert het ondertekende toegangstoken en bepaalt documentrechten op basis van een groepsbeleid op de server. |
| Retrieval | The server adds a mandatory tenant and access-level filter. It checks the returned metadata again before any text reaches the model. | De server voegt een verplicht filter voor tenant en toegangsniveau toe. Hij controleert de teruggegeven metadata opnieuw voordat de tekst naar het model gaat. |
| Knowledge base | Bedrock Knowledge Bases creates embeddings from the synthetic source files and searches the S3 vector index. | Bedrock Knowledge Bases maakt embeddings van de fictieve bronbestanden en doorzoekt de vectorindex in S3. |
| Agent roles | The analyst extracts requirements, the designer drafts a proposal, and the reviewer checks it. At most two correction rounds are allowed. | De analist haalt de vereisten uit de bronnen, de ontwerper maakt een voorstel en de beoordelaar controleert het. Er zijn maximaal twee correctierondes toegestaan. |
| MCP | MCP is the protocol used to call one fixed, read-only checklist tool. It does not grant permissions and does not execute generated commands. | MCP is het protocol om één vast hulpmiddel voor een controlelijst aan te roepen. Dat hulpmiddel leest alleen gegevens. MCP verleent geen rechten en voert geen gegenereerde opdrachten uit. |
| Human decision | A model review cannot grant human approval. The user's decision is bound to the SHA-256 hash of the exact artifact. | Een beoordeling door een model is geen menselijke goedkeuring. De beslissing van de gebruiker is gekoppeld aan de SHA-256-hash van het exacte resultaat. |
| Storage | S3 stores the result and decision in one versioned object. Conditional writes reject concurrent or stale decisions. | S3 bewaart het resultaat en de beslissing in één object met versiebeheer. Voorwaardelijke schrijfacties weigeren gelijktijdige of verouderde beslissingen. |
| GitHub delivery | The pipeline tests and builds the image. GitHub exchanges a short-lived OIDC token for a scoped AWS role, so the repository needs no permanent AWS key. | De pipeline test en bouwt de image. GitHub wisselt een tijdelijk OIDC-token in voor een afgebakende AWS-rol. De repository heeft daardoor geen permanente AWS-sleutel nodig. |
| Operations | I inspect structured logs and OpenTelemetry spans. The application logs identifiers and measurements, not prompt or document bodies. | Ik controleer gestructureerde logs en OpenTelemetry-spans. De applicatie logt identificatoren en meetwaarden, geen volledige prompts of documenten. |
| Recovery | A failed worker does not resume automatically. Its stored record remains inspectable, and the user starts a new run. | Een onderbroken worker wordt niet automatisch hervat. Het opgeslagen resultaat blijft raadpleegbaar en de gebruiker start een nieuwe uitvoering. |
| Scope | This is a synthetic proof of concept. Enterprise federation, document-rights synchronization, production availability and operating ownership require further work. | Dit is een proof of concept met fictieve gegevens. Federatie, synchronisatie van documentrechten, beschikbaarheid in productie en operationeel eigenaarschap vragen nog verdere uitwerking. |

## Questions to answer without reading

- Which component authenticates a person, and which code authorizes a document?
- Why cannot a prompt ask the model to remove the mandatory retrieval filter?
- What is the difference between the model, agent orchestration and an MCP tool?
- What happens after a timeout, a rejected review, a wrong hash or a concurrent decision?
- Which steps were actually deployed and tested in AWS? Which remain local or planned?
- How do you identify the deployed commit, inspect a trace, roll back and remove resources?

Practise one full explanation in English, then in Dutch. Keep technical service
names unchanged. Explain unfamiliar words in ordinary language before naming the
abbreviation. Record the actual URL, image digest, model identifier and successful
run identifier in a private demonstration note after the AWS smoke test.
