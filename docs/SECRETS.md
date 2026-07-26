# Handling API keys

## Short version

**Don't paste your keys into a chat with an AI assistant, including this one.
You never need to.**

Every integration in this project reads credentials from environment
variables. Code can be written, reviewed, and tested without the author of the
code ever seeing a key value. Keys go in exactly two places, both of which you
control:

| Where | What it's for | How |
| --- | --- | --- |
| `.env` in your working copy | Local runs and notebooks | Copy `.env.example`, fill it in. Gitignored. |
| GitHub repository secrets | The scheduled Action | Settings → Secrets and variables → Actions → New repository secret |

Neither location routes through any third party.

## Why the instinct is right

Anything typed into a chat is transmitted to and processed by the model
provider. That's true of any AI assistant, and it's a reasonable thing to not
want for a live credential — not because of any specific expected misuse, but
because credentials should have the smallest possible number of copies in the
smallest possible number of systems. A key that only ever exists in your `.env`
and your GitHub secrets has two copies. One pasted into a chat has more, in
systems you don't administer, with retention policies you don't set.

The same reasoning is why the daily ingest workflow uses **no secrets at all** —
TCGCSV requires no API key, so there's nothing to leak.

## Working on API code without sharing keys

This is the normal workflow, not a workaround:

1. **Code is written against the environment variable**, never a literal.
   `os.environ["EBAY_CLIENT_SECRET"]` — the code doesn't care what it contains.
2. **You run it locally** with your `.env` populated.
3. **If something breaks, share the error, not the environment.** Stack traces,
   HTTP status codes, and response bodies are usually enough to diagnose a
   problem. Redact anything that looks like a token before pasting.

Two things to watch when sharing output:

- eBay's OAuth flow returns an **access token** in the response body. It's
  short-lived, but it's still a credential — redact it.
- Verbose HTTP logging (`curl -v`, `http.client` debug) prints the
  `Authorization` header. Don't paste raw verbose logs.

## Setting up the GitHub secret

The daily ingest needs no secrets, but it accepts one optional value so a
public repo doesn't publish your email address in the User-Agent string:

1. Repo → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Name: `POKEDB_USER_AGENT`
4. Value: `pokemon-price-db/0.1 (+your@email.com)`

If you skip it, the workflow falls back to a generic User-Agent and still
works.

Secrets are encrypted at rest, injected only into workflow runs, and masked in
logs — if a secret value would be printed, GitHub replaces it with `***`. That
masking is a safety net, not a license to print them.

## Phase 3 onward

When eBay ingestion lands, it will need:

```
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
```

Same rule. Put them in your local `.env` to develop against, and in GitHub
secrets if the eBay poll is ever automated. Note that eBay's Browse API has a
5,000 call/day limit tied to your credentials, so automating it needs a
rate budget, not just a key.

## If a key is ever exposed

Rotate it rather than hoping. Every provider here supports it:

- **eBay** — developer portal → your application → regenerate the client secret
- **PokemonPriceTracker** — account settings → regenerate API key

Rotation costs a few minutes. Deciding whether an exposure mattered costs more.
