# Stage 0: create and prepare the AWS account

**Yves Schillings, Secloudis. Account name: `Secloudis Lab`.**

Account console access was confirmed by a user-provided capture on 30 September
2026. Operator access, MFA, the deployment region, budget controls, models and
application services remain unverified. This checklist prepares the remaining
account prerequisites for the [deployment runbook](deployment.md).
It does not create cloud resources or authorise a paid deployment.

## 1. Complete registration and confirm activation

Use the [official AWS registration page](https://signin.aws.amazon.com/signup?request_type=register).
AWS calls this route **Sign up for AWS (advanced)**. It supports explicit account,
region and permission control needed by this project; compare the
[official sign-up options](https://docs.aws.amazon.com/accounts/latest/reference/sign-up-for-aws.html).

Enter `Secloudis Lab` as the account name. Yves completes email/phone verification,
password creation, payment details, plan selection and contractual acceptance
directly in AWS. Keep those details and verification codes out of chat, Git and
screenshots. Review the offered plan and terms; no plan or credit allowance is
assumed here.

Before deployment, verify that the chosen plan permits the required services and
models. Do not assume credits cover every charge; consult
[AWS account-plan details](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

Console access for this lab is now confirmed; the registration instructions above
are retained as reference. Service/model availability and deployment authority
still require separate verification. For a new registration, follow the
[official registration steps](https://docs.aws.amazon.com/accounts/latest/reference/getting-started.html)
if activation remains pending.

## 2. Secure ownership and arrange operator access

The root identity controls the account and recovery. Yves retains its password,
recovery email/phone and multi-factor authentication (MFA). Enable MFA and retain
a protected recovery method. Do not create root access keys. Arrange a separate
authorised operator identity for routine deployment, using temporary credentials.
See [AWS root-user guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html).

Creating that identity or assigning permissions is a separate setup step; this
document does not grant administrator access or assume Identity Center exists.

## 3. Connect the existing CLI when access is ready

The workstation already has AWS CLI 2.37.6. Use the
[documented workstation sign-in procedure](deployment.md#connect-the-operator-workstation):

- If IAM Identity Center is configured, obtain its actual start URL, SSO region,
  account and role, then use the documented SSO profile flow.
- Otherwise, an authorised console identity with the required local-development
  permission can use `aws login --profile aws-agent-lab`.

After sign-in, run this identity check and compare the account and role privately:

```powershell
aws sts get-caller-identity --profile aws-agent-lab
```

Verify Terraform/SDK profile support before planning. Keep credentials in the AWS
profile/cache outside the repository; do not export them into logs.

## 4. Record the actual deployment inputs

Before provisioning, establish:

- The activated 12-digit account ID and authorised operator role.
- The chosen workload region and service/model availability there.
- Bedrock generation/embedding model access and exact model or profile ARNs.
- A reviewed cost allowance, alert recipient and review/teardown date.

No region or budget is selected by this guide. Budget alerts and Terraform cost
acknowledgements are not a hard billing ceiling. Continue with
[explicit deployment inputs](deployment.md#record-the-deployment-inputs), then a
reviewed Terraform plan. Successful account setup alone does not prove the
application, Bedrock or retrieval works.
