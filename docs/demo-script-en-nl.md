# Reusable AWS Workflow Demonstration and Explanation

Use this guide to explain a reusable workflow foundation with synthetic examples.
Follow the [open-source reuse guidance](slides/25-open-source-reuse-and-enterprise-value.md)
for licence, reproducibility and enterprise adaptation requirements. Use the
statements that match the evidence from the run being shown. Until an AWS
run succeeds, say **implemented locally, cloud deployment pending**. A mock answer
does not establish that Bedrock, cloud identity or the vector index works.

This guide describes the verified three-role baseline. It does **not** establish
the full “Inside the Factory” target with five workers, four approval gates and
an isolated execution sandbox. Update and rehearse the journey after that target
has been implemented and verified; do not relabel baseline evidence as full
Factory evidence.

## Start with the evidence actually available

The [implementation backlog](implementation-backlog.md) records a successful
hosted CI run for commit `e24e882046112b45f8b20ebba64e6f268eab7842`: offline tests,
Terraform validation, a Linux container build and an offline workflow inside that
container. This is evidence for that commit. Check the run for the commit being
presented before describing a later build as verified.

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| Local browser/API and denial tests | Application controls over simulated `alpha`/`beta` identities and synthetic data | A real Cognito login or enterprise tenant isolation |
| Real local MCP stdio exchange | The fixed checklist tool is reached through the protocol | That the same process works in the AWS service |
| Hosted offline CI and container smoke | The recorded Linux image builds and runs the mock workflow | AWS deployment, live embeddings or model quality |
| AWS adapters, Terraform and deployment scripts | An implemented deployment candidate with offline checks | Successful account execution or live rollback |

**EN:** “This demonstration separates working local controls from the AWS services
that still need live evidence. I will show the exact environment and run.”

**NL:** “Deze demonstratie maakt onderscheid tussen lokaal werkende controles en
de AWS-diensten die nog in de echte omgeving moeten worden aangetoond. Ik toon
precies welke omgeving en uitvoering ik gebruik.”

## Explain the target architecture in two to three minutes

**Multi-Agentic Workflow on AWS — Yves Schillings, Secloudis.** Use the
[documentation index](README.md), [logical architecture](slides/03-logical-architecture.md),
[AWS architecture](slides/04-aws-deployment-architecture.md) and
[four human gates](slides/05-workflow-and-human-gates.md) as visual support.
The two scripts below explain the same target and evidence boundary. Practise
each aloud; the duration is a rehearsal target, not a measured result.

### English

“This is Multi-Agentic Workflow on AWS, by Yves Schillings, Secloudis. The target
is a controlled software-delivery workflow. A Python controller coordinates
five specialist workers: Analyst, Architect, Code author, Tester and Reviewer.
Amazon Bedrock supplies the language-model inference. The controller owns the
sequence, permissions, time limits and budgets; the model cannot grant itself
extra authority.

The Analyst clarifies requirements. The Architect proposes a design. The Code
author produces a candidate, the Tester proposes checks, and the Reviewer
examines the results. Protected tests run separately from the generated code,
so a worker cannot declare its own output correct simply by writing a report.

Four human gates retain accountability: scope at G1, design at G2, quality at
G3 and release at G4. Humans decide because models can misunderstand a request,
invent facts or repeat another worker’s mistake. Each decision must refer to
the exact version being reviewed. A later change cannot silently reuse an old
approval. Only the protected release pipeline may deploy the approved candidate
to a separate application.

Three shared services support this. The context service retrieves only permitted
documents and keeps source versions and citations. An isolated sandbox runs
candidate code without an application task role or production credentials, with
bounded resources and controlled network access. The evidence store retains
artifacts, tests, decisions and their relationships for review.

Today, the verified local demonstration is smaller: three roles—Analyst,
Designer and Reviewer—and one decision on an exact artifact. It uses mock model
answers and a real local, read-only MCP tool. The five workers, four gates,
generated-code sandbox and candidate release are target work. AWS and Bedrock
must still be deployed and verified; the diagram itself is not that proof.”

### Nederlands

“Dit is Multi-Agentic Workflow on AWS, van Yves Schillings, Secloudis. Het doel
is een gecontroleerd proces voor softwareontwikkeling en oplevering. Een
Python-controller stuurt vijf gespecialiseerde rollen aan: Analyst, Architect,
Code author, Tester en Reviewer. Amazon Bedrock levert de taalmodelaanroepen.
De controller bepaalt de volgorde, toegangsrechten, tijdslimieten en budgetten.
Het model kan zichzelf geen extra bevoegdheden geven.

De Analyst verduidelijkt de vereisten. De Architect stelt een ontwerp voor. De
Code author maakt een kandidaatversie, de Tester stelt controles voor en de
Reviewer beoordeelt de resultaten. Beschermde tests draaien los van de
gegenereerde code. Een agent kan zijn eigen resultaat dus niet correct verklaren
door alleen een positief rapport te schrijven.

Vier menselijke beslismomenten behouden de verantwoordelijkheid: de scope bij
G1, het ontwerp bij G2, de kwaliteit bij G3 en de vrijgave bij G4. Mensen
beslissen omdat modellen een vraag verkeerd kunnen begrijpen, feiten kunnen
verzinnen of dezelfde fout kunnen herhalen. Elke beslissing moet aan de exacte
beoordeelde versie gekoppeld zijn. Een wijziging mag geen oude goedkeuring
stilzwijgend hergebruiken. Alleen de beschermde releasepipeline mag de
goedgekeurde kandidaat als afzonderlijke applicatie uitrollen.

Drie gedeelde diensten ondersteunen dit. De contextdienst haalt uitsluitend
toegestane documenten op en bewaart bronversies en verwijzingen. Een geïsoleerde
sandbox voert kandidaatcode uit zonder applicatie-taskrol of
productietoegangsgegevens, met begrensde middelen en gecontroleerde
netwerktoegang. De bewijsopslag bewaart resultaten, tests, beslissingen en hun
onderlinge verbanden.

Vandaag is de lokaal geverifieerde demonstratie kleiner: drie rollen—Analyst,
Designer en Reviewer—en één beslissing over een exact resultaat. Ze gebruikt
gesimuleerde modelantwoorden en een echt lokaal MCP-hulpmiddel dat alleen leest.
De vijf rollen, vier beslismomenten, sandbox voor gegenereerde code en vrijgave
van een kandidaat moeten nog worden gebouwd. AWS en Bedrock moeten nog worden
uitgerold en geverifieerd. Het architectuurschema alleen bewijst dat niet.”

## Five-minute demonstration

1. Show the GitHub source and the tested commit. If AWS is deployed, also show its
   recorded image digest; otherwise identify the local/offline environment.
2. Show the application mode. Locally, select the simulated `alpha` identity. In
   AWS, sign in as an authorised Cognito user mapped to the `alpha` source scope.
3. Submit: “Prepare a synthetic document checklist. Explain missing evidence, cite
   the available sources and retain a human decision before publication.”
4. Open a cited source. Explain its document identifier, version and tenant.
5. Show analyst, designer and reviewer stages, the fixed MCP checklist result and
   the final artifact hash. Explain that the tool is application-selected.
6. Approve that exact artifact. Show its recorded decision and identity mode.
   Publication here marks the stored synthetic artifact as approved; it sends no
   real business instruction to another system.
7. Select/sign in as the `beta` identity and run the same question; inspect only `beta` sources.
   Show a prepared API denial check: the `beta` identity requests an `alpha` run and
   source endpoints, and receives no artifact or source content. The run lookup
   returns 404. A bare URL in the address bar has no identity header and only
   demonstrates missing authentication. The existing local
   [HTTP isolation test](../tests/test_web.py) is the offline fallback; label it
   as such. Prepare the live check with authorised credentials mapped to the `beta` scope privately before
   presenting, without displaying or saving access tokens.
8. Show a trace, measured latency and returned token counts. If price inputs are
   unavailable, say the cost is unknown. Explain the rollback procedure and its
   offline tests; call it a live rollback only after retaining a real AWS result.

## Explain the deployment sequence in plain language

These are operator steps from [deployment.md](deployment.md), not completed work
or commands to execute during a public demonstration. The infrastructure operator and the
limited GitHub image-deployment role have different permissions.

| Step | English | Nederlands |
|---|---|---|
| 1. Check inputs | First I verify the account, region, permitted models, cost allowance and exact GitHub identity. Offline validation cannot confirm model access. | Eerst controleer ik het account, de regio, de toegestane modellen, het kostenbudget en de exacte GitHub-identiteit. Offline validatie bewijst geen modeltoegang. |
| 2. Create the foundations | Terraform creates storage, identity, the empty knowledge base, roles and image registry. The application service is initially disabled. | Terraform maakt opslag, identiteit, de lege kennisbank, rollen en het imageregister aan. De applicatiedienst staat eerst uit. |
| 3. Publish the first image | The publish-only workflow tests and uploads the application image. I retain its exact digest, a fingerprint of its content. This does not start the service. | De workflow voor alleen publiceren test en uploadt de applicatie-image. Ik bewaar de exacte digest, een vingerafdruk van de inhoud. Dit start de dienst nog niet. |
| 4. Start and configure the service | Terraform starts that image in Express Mode. Once AWS returns the HTTPS address, I apply it as the Cognito callback and application address. A healthy process alone does not prove login works. | Terraform start die image in Express Mode. Zodra AWS het HTTPS-adres geeft, stel ik dat in als Cognito-terugkeeradres en applicatieadres. Een gezond proces bewijst nog geen werkende login. |
| 5. Add knowledge and users | An operator uploads synthetic files and their metadata, waits for ingestion, and enrolls two users in the correct groups. GitHub's deployment role cannot do this. | Een beheerder uploadt fictieve bestanden met metadata, wacht tot de verwerking klaar is en koppelt twee gebruikers aan de juiste groepen. De GitHub-deployrol mag dit niet doen. |
| 6. Prove the whole journey | I verify real login, scoped retrieval, Bedrock calls, the tool and the exact human decision. Then I try the denied cases and retain the results. | Ik controleer echte login, ophalen binnen de toegangsrechten, Bedrock-aanroepen, het hulpmiddel en de exacte menselijke beslissing. Daarna test ik geweigerde toegang en bewaar ik de resultaten. |
| 7. Update and recover | Later workflows change the existing service's image digest. Terraform still owns configuration. Image rollback needs a known-good digest and a new authenticated smoke test. | Latere workflows wijzigen de image-digest van de bestaande dienst. Terraform blijft de configuratie beheren. Terugzetten vereist een eerder werkende digest en een nieuwe test met ingelogde gebruikers. |

## Explanations to practise

Use the AWS component descriptions as the implemented design until live evidence
exists. Start with ordinary words, then use the service name. In particular, a
tenant is a separate demonstration workspace, and an embedding is a numerical
representation used to find related text.

| Component | English | Nederlands |
|---|---|---|
| Overall flow | I built a small platform that retrieves authorized documents, passes them through three bounded agent roles and records a human decision on the exact result. | Ik heb een klein platform gebouwd dat toegelaten documenten ophaalt, ze door drie afgebakende agentrollen verwerkt en een menselijke beslissing over het exacte resultaat vastlegt. |
| Fargate | Fargate runs the application container. ECS Express Mode prepares the service and its HTTPS entry point. | Fargate voert de applicatiecontainer uit. ECS Express Mode maakt de dienst en het HTTPS-toegangspunt aan. |
| Cognito | Cognito's hosted sign-in authenticates the user. My API verifies the signed access token and derives document permissions from a server-owned group policy. | Het gehoste aanmeldscherm van Cognito authenticeert de gebruiker. Mijn API controleert het ondertekende toegangstoken en bepaalt documentrechten op basis van een groepsbeleid op de server. |
| Retrieval | The server adds a mandatory tenant and access-level filter. It checks the returned metadata again before any text reaches the model. | De server voegt een verplicht filter voor tenant en toegangsniveau toe. Hij controleert de teruggegeven metadata opnieuw voordat de tekst naar het model gaat. |
| Knowledge base | Bedrock Knowledge Bases creates embeddings from the synthetic source files and searches the S3 vector index. | Bedrock Knowledge Bases maakt embeddings van de fictieve bronbestanden en doorzoekt de vectorindex in S3. |
| Agent roles | The analyst extracts requirements, the designer drafts a proposal, and the reviewer checks it. At most two correction rounds are allowed. | De analist haalt de vereisten uit de bronnen, de ontwerper maakt een voorstel en de beoordelaar controleert het. Er zijn maximaal twee correctierondes toegestaan. |
| MCP | MCP is the protocol used to call one fixed, read-only checklist tool. It does not grant permissions and does not execute generated commands. | MCP is het protocol om één vast hulpmiddel voor een controlelijst aan te roepen. Dat hulpmiddel leest alleen gegevens. MCP verleent geen rechten en voert geen gegenereerde opdrachten uit. |
| Human decision | A model review cannot grant human approval. The user's decision is bound to the SHA-256 hash of the exact artifact. | Een beoordeling door een model is geen menselijke goedkeuring. De beslissing van de gebruiker is gekoppeld aan de SHA-256-hash van het exacte resultaat. |
| Storage | S3 stores the result and decision in one versioned object. Conditional writes reject concurrent or stale decisions. | S3 bewaart het resultaat en de beslissing in één object met versiebeheer. Voorwaardelijke schrijfacties weigeren gelijktijdige of verouderde beslissingen. |
| GitHub delivery | The pipeline tests and builds the image. GitHub exchanges a short-lived OIDC token for a scoped AWS role, so the repository needs no permanent AWS key. | De pipeline test en bouwt de image. GitHub wisselt een tijdelijk OIDC-token in voor een afgebakende AWS-rol. De repository heeft daardoor geen permanente AWS-sleutel nodig. |
| Operations | OpenTelemetry records the duration and relationship of steps as safe JSON log summaries. CloudWatch is the configured AWS log destination; no Langfuse or Dynatrace export is configured. | OpenTelemetry legt de duur en samenhang van stappen vast als veilige JSON-logregels. CloudWatch is de ingestelde AWS-logbestemming; export naar Langfuse of Dynatrace is niet geconfigureerd. |
| Recovery | A failed worker does not resume automatically. Its stored record remains inspectable, and the user starts a new run. | Een onderbroken worker wordt niet automatisch hervat. Het opgeslagen resultaat blijft raadpleegbaar en de gebruiker start een nieuwe uitvoering. |
| Scope | This is a synthetic proof of concept. Enterprise federation, document-rights synchronization, production availability and operating ownership require further work. | Dit is een proof of concept met fictieve gegevens. Federatie, synchronisatie van documentrechten, beschikbaarheid in productie en operationeel eigenaarschap vragen nog verdere uitwerking. |

## Questions to answer without reading

| Reviewer question | Short English answer | Kort Nederlands antwoord |
|---|---|---|
| Why does a green health check not prove the demo works? | `/healthz` only proves the process responds. I still need real login, ingestion, inference and denied-access results. | `/healthz` bewijst alleen dat het proces antwoordt. Echte login, verwerking, modelaanroepen en geweigerde toegang moeten apart worden getest. |
| Who decides which documents a user may read? | The API verifies the token, maps its groups to one server-owned scope, and filters retrieval. The prompt cannot choose that scope. Returned metadata and later reads are checked again. | De API controleert het token, koppelt de groepen aan één toegangsbereik op de server en filtert de zoekopdracht. De prompt kiest die rechten niet. Metadata en latere leesacties worden opnieuw gecontroleerd. |
| Are these independent autonomous agents? | They are bounded roles coordinated by Python. The model generates content; the controller controls order and limits. The fixed MCP tool runs before the agents and cannot execute model-generated commands. | Het zijn afgebakende rollen die Python aanstuurt. Het model maakt inhoud; de controller bepaalt de volgorde en grenzen. Het vaste MCP-hulpmiddel draait vóór de agenten en voert geen modelopdrachten uit. |
| Do citations and reviewer approval guarantee correctness? | No. Citation checks validate source identifiers, not every claim. I inspect the cited text, evaluate expected evidence and retain a separate human decision. | Nee. Broncontroles valideren identificatoren, niet elke bewering. Ik controleer de brontekst, beoordeel het verwachte bewijs en behoud een aparte menselijke beslissing. |
| Why both a hash and a conditional write? | The hash binds approval to exact content. The conditional write rejects a changed stored version. Neither makes the record tamper-proof or coordinates every workflow step as one transaction. | De hash koppelt goedkeuring aan exacte inhoud. De voorwaardelijke schrijfactie weigert een gewijzigde opgeslagen versie. Dit maakt het dossier niet onvervalsbaar en maakt niet alle stappen samen atomair. |
| What happens if execution fails? | Calls and corrections are bounded. A rejected review or exhausted limit blocks approval. A wrong hash or repeated decision is rejected. Interrupted work does not resume automatically; start a new run. | Aanroepen en correcties zijn begrensd. Een afgekeurde beoordeling of bereikte limiet blokkeert goedkeuring. Een verkeerde hash of herhaalde beslissing wordt geweigerd. Onderbroken werk hervat niet automatisch; start opnieuw. |
| What exactly does rollback restore? | Only a previously verified image digest. It does not undo IAM, Cognito, source content or stored data. The current alarm neither sends notifications nor triggers rollback. | Alleen een eerder geverifieerde image-digest. IAM, Cognito, broninhoud en opgeslagen gegevens worden niet teruggedraaid. Het huidige alarm verstuurt geen meldingen en start geen rollback. |
| Why Fargate, and what remains for production? | It keeps this small container demo manageable. One configured task is not high availability. Production needs durable execution, federation, rights synchronization, recovery, operational ownership and measured limits. | Het houdt deze kleine containerdemo beheersbaar. Eén ingestelde taak betekent geen hoge beschikbaarheid. Productie vereist duurzame uitvoering, federatie, synchronisatie van rechten, herstel, operationeel eigenaarschap en gemeten grenzen. |

## Rehearsal for a reproducible demonstration

First exercise: in 45 seconds, explain the path from a user request to the exact
human decision in English, then in Dutch, using the architecture drawing only.
For each arrow, name who authorizes the action and the evidence that would prove
it worked. If a service is unfamiliar, say what you still need to verify.

Then practise the five-minute journey and answer three questions above without
reading. A colleague should ask one follow-up about a failed or denied request.
Keep the local fallback ready and announce the mode before showing it. These are
practice tasks, not a record of a completed rehearsal.

- [ ] Record the real rehearsal date, elapsed time and questions that caused hesitation.
- [ ] Resolve those questions using the code or runbook; repeat the explanation.
- [ ] Privately record the tested commit, environment, run ID and observed outcome;
      add the URL, deployed digest, model and region only if actually exercised.
- [ ] Explain one measured limitation and one remaining AWS check without implying
      they have already passed. Use [operations.md](operations.md) and
      [rollback.md](rollback.md) for recovery and cleanup questions.
