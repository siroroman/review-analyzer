# Review Analyzer

Turns the public reviews of a company and its branches into a dashboard: rating, sentiment over time, topics, explanations of drops and suggestions for improvement.

## Language

### What is analyzed

**Company**:
A set of one or more Places that the user confirmed as belonging together. It has no external key: the same set of Places is the same Company.
_Avoid_: Business, client, organization

**Place**:
One branch of a Company on one Source, identified by that Source's external ID.
_Avoid_: Location, branch (as a data term), listing

**Source**:
A public site that hosts reviews: Google Maps or Firmy.cz.
_Avoid_: Platform, provider (a provider is an external service such as Apify or a model API)

**Review**:
One public rating with text and date of a Place on a Source, stored without any personal data.
_Avoid_: Comment, feedback, opinion

**Flagged review**:
A Review in which the injection detector found instructions aimed at a model. It is excluded from the analysis and only counted.
_Avoid_: Spam, malicious review

### What the analysis says

**Topic**:
A subject reviews talk about (e.g. staff, waiting, prices), part of a Taxonomy.
_Avoid_: Category, tag, theme

**Taxonomy**:
The frozen list of Topics for one industry, generated once from a sample of Reviews.
_Avoid_: Topic list, ontology

**ReviewTopic**:
The assignment of one Topic to one Review with a sentiment and a confidence.
_Avoid_: Label, classification (classification is the act, ReviewTopic is its result)

**TrendPoint**:
The average rating, count and sentiment of one Source in one period; a point of the timeline.
_Avoid_: Data point, datapoint

**Metrics**:
Everything computed by code from Reviews and ReviewTopics: averages, TrendPoints, topic shares, detected drops and rises.
_Avoid_: Stats, analytics

**Insight**:
A statement by the strong model (summary, anomaly explanation or suggestion) that cites the IDs of the Reviews it rests on.
_Avoid_: Finding, recommendation, conclusion

**Grounding**:
The rule and the check that every Insight cites Review IDs that exist.
_Avoid_: Validation, fact-checking

### How it runs

**Run**:
One execution of the pipeline for a Company, with a status, a Budget and a measured cost.
_Avoid_: Job, analysis, task (a task is a queue message)

**Budget**:
The cost cap of one Run (and the monthly cap across Runs) over all paid services; the Gateway enforces it, and exceeding it ends the Run with a partial result.
_Avoid_: Quota, limit

**Gateway**:
The one module through which every paid external service (model providers, Apify, Google Places) is called. It applies the allow-list, the traffic limits and the Budget, and writes a Service call for each call.
_Avoid_: Proxy, middleware, client (a client is one provider's adapter behind the Gateway)

**Service call**:
One call through the Gateway to a paid service, with its service, operation, status, cost, units and latency, never its request or response body.
_Avoid_: Request, API call, transaction

**Call log**:
The stored list of Service calls; the admin screen reads it.
_Avoid_: Audit trail, history, trace (a trace is a Langfuse record of a model call)

**Partial result**:
The result of a Run that stopped early (Budget exceeded or a step failed past retry) and shows what was finished.
_Avoid_: Failed run, incomplete run

**Demo token**:
A link token that gives access to the dashboard in the demo, in place of a login.
_Avoid_: API key, session

**Admin token**:
A secret token from configuration that gives access to the admin screen (spend and Call log), in place of a login. It is not the Demo token.
_Avoid_: Admin password, API key, session
