# Verity privacy notice

Effective date: October 7, 2026

Verity is an open-source forensic surface comparison project maintained by Eric
Hare. This notice covers Verity's hosted API at `api.verity.codes` and the Verity
plugins that connect to it. Contact `ericrhare@gmail.com` with privacy questions.

## Information processed

When you request a comparison or mark-type assessment, your agent sends the X3P
scan contents and the tool arguments needed for that request to Verity. Scan
files, filenames, and acquisition metadata may contain names or identifiers that
you included. Other tools process the score, physical mark domain, and
configuration values you supply. Service-health and reference-listing calls do
not require scan uploads.

The service and its infrastructure may process technical information such as IP
addresses, request times, request paths, status codes, and error diagnostics to
operate the service, prevent abuse, and investigate failures. Verity does not need
your full conversation history, unrelated local files, or account credentials.
The plugins instruct your agent to send only files you supply or identify for
the requested comparison.

## Purpose and recipients

Verity processes submitted data to perform the requested analysis, return results
and provenance, and maintain service reliability and security. The comparison
pipeline does not train models on your submitted scans. Verity does not sell
scan data or use it for advertising.

Requests pass through the hosting infrastructure that serves Verity. Error
diagnostics may also be processed by Sentry when error monitoring is enabled.
Relevant provider policies include [Railway](https://railway.com/legal/privacy),
[Cloudflare](https://www.cloudflare.com/privacypolicy/),
[Vercel](https://vercel.com/legal/privacy-policy), and
[Sentry](https://sentry.io/privacy/). These providers support hosting, delivery,
or monitoring rather than providing a separate forensic comparison service.

The agent platform you use, such as Claude or Codex, separately processes your
conversation, tool arguments, and returned results under its own policies.
Verity cannot delete copies held in your agent platform, downloads, or records
you maintain.

## Retention and control

Verity's service-retained data received through these plugins, including scan
data, intermediate artifacts, and associated operational logs, is deleted
within 30 days. The application uses a temporary in-memory artifact cache with
a default one-hour expiry. The cache is not a durable case-record repository.

For a privacy or deletion request, email `ericrhare@gmail.com`. Include only
enough non-sensitive information to identify the request, such as its approximate
time and recipe handle. Anonymous processing can limit our ability to associate
data with a particular person. Do not send scan contents or sensitive case
details in a public GitHub issue.

## Appropriate data and self-hosting

Use synthetic or appropriately de-identified research scans with the public
service. Do not send confidential case records, personal identifiers, or data
you are not authorized to disclose. The service is intended for adult researchers
and practitioners, not for children.

Hosted plugin comparisons transmit data off your machine. The optional local
stdio server also uploads scan bytes unless configured to use your own local
API. Self-hosted deployments are controlled by their operators and may have
different policies and retention settings.

## Changes and contact

Policy changes will be published with an updated effective date. Contact Eric
Hare at `ericrhare@gmail.com` for privacy or security concerns. Public product
support is available through [GitHub issues](https://github.com/erichare/verity/issues).
