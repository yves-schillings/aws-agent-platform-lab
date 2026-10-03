# Factory UI deployment verification

- **Deployed source:** [`f777eadc9f0c95e3b34633ca021a6f779d1838de`](https://github.com/yves-schillings/aws-agent-platform-lab/tree/f777eadc9f0c95e3b34633ca021a6f779d1838de).
- **Image:** ECR repository `aws-agent-lab`, immutable digest `sha256:7e74d04c801bb393306dd0ffd4fcd2c3509e467d9efde662267b2f78875cd777`.
- **Image tag:** ECR reports `f777eadc9f0c95e3b34633ca021a6f779d1838de` for that digest. GitHub stores the [Dockerfile](../Dockerfile) and [build workflow](../.github/workflows/deploy.yml); the image binary is held in private ECR rather than GitHub Packages.
- **Promotion:** The image was built and pushed locally, then promoted with [`deploy_express.py`](../scripts/deploy_express.py). This record does not claim that GitHub Actions performed this promotion.
- **Observed AWS state:** Region `eu-west-1`, ECS service `aws-agent-lab`, desired count 2, running count 2 and deployment rollout `COMPLETED`. Both load-balancer targets reported healthy.
- **Observed application:** `/healthz` returned `{"status":"ok"}`. The live `/factory` page displayed the official Secloudis logo, its title on one line and its introductory sentence on one line in the captured desktop view.
- **Screenshots:** [Live Factory entry](images/factory-aws-home.jpg), [empty Cognito sign-in form](images/cognito-sign-in.jpg), [source-to-browser diagram](images/factory-page-hosting.png) and [local Docker Desktop container](images/docker-desktop-local-test.png).
- **Checks before promotion:** Six Factory web tests, fifteen baseline web tests and the built container's offline smoke check passed.
- **Local test scope:** [container_smoke.py](../scripts/container_smoke.py) exercised the installed baseline application through internal loopback, reaching a human approval gate with synthetic data and simulated identity. [Factory web tests](../tests/test_factory_web.py) separately exercised the five-role application and four-gate journey with failure paths. The Docker Desktop screen shows the container running; the successful smoke result comes from executing the test script.
- **Remaining verification:** A complete browser sign-in and Factory run using the requester and distinct approver, with live model output and decisions at all four gates, still needs to be recorded. Public entry-page availability and service health do not establish that result.
- **Earlier console evidence:** The earlier task screenshots show the previous image digest beginning `d746663d`. They remain evidence of that earlier revision, rather than screenshots of this UI promotion.
