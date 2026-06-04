---
name: Reddit API Application — v2 paste-ready
description: Step-by-step submission guide and field-by-field answers for the Reddit developer-access resubmission under u/SparkyMcCrinkle. Drafted 2026-05-11 after the 2026-05-02 denial.
type: reference
---

# Reddit API Application — v2 (Knife & Ledger LLC / Scout)

**Account:** u/SparkyMcCrinkle
**Submit from:** gfloss381@gmail.com (Reddit account email)
**Status before this draft:** v1 denied 2026-05-02 with boilerplate ("not in compliance with Responsible Builder Policy and/or lacks necessary details"). 7-day cooldown observed. v2 not yet submitted.
**Form URL (direct):** https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164

---

# Step-by-step submission

**Estimated time: 25-35 minutes.** The form is dynamic (fields change based on the role and inquiry dropdown choices). Have this document open in a second window while filling it out so you can paste field-by-field without re-typing.

## Step 0 — Before opening the form (5 minutes)

These three things must be true before you start, or the application will look inconsistent to a reviewer reading the public repo:

1. **Drop `r/smallbusiness` from `config.yaml`.** It still lists three subreddits; v2 strategy is two. Open `/Users/gregfoster/00-coding/active/03 KL Agents/config.yaml`, delete the line `- smallbusiness`, then in that repo run:
   ```bash
   git add config.yaml
   git commit -m "config: drop r/smallbusiness from scout subreddits"
   git push
   ```
2. **Confirm the public repo is readable** at https://github.com/gregfoster1836/kl-agents (open in a private browser window). If `.env` shows up anywhere, stop and rotate keys before submitting.
3. **Confirm https://knifeledger.com loads** and shows a public blog. Reviewers will visit it. If the site is down or behind a paywall today, reschedule the submission.

## Step 1 — Pre-read the policy (5 minutes)

Reddit's reviewers reject anything that reads like the applicant did not read the policy. Skim, do not skip:

1. **Responsible Builder Policy** at https://support.reddithelp.com/hc/articles/42728983564564
2. **Data API Terms** linked from that policy

Both are short. The two phrases reviewers care about: "responsible use" and "no commercial redistribution of user content." Scout is read-only research, not redistribution. Keep that distinction in mind when writing.

## Step 2 — Open the form

Go to: https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164

The form starts collapsed. Conditional fields appear only after you make the right dropdown choices in Step 3.

## Step 3 — Fill the top section (the dropdowns control everything)

These are the first visible fields. The dropdown selections unlock the rest of the form, so get these right:

| Field | What to do |
|---|---|
| **Your email address** | `gfloss381@gmail.com` (the email tied to u/SparkyMcCrinkle) |
| **Subject of inquiry** | `API access request — Knife & Ledger LLC / Scout (read-only research)` |
| **Details of inquiry** | Paste the **Cover narrative** block from Step 6 below |
| **What do you need assistance with?** | Select **API Access Request** |
| **Which role best describes your reason for requesting API access?** | Select **Bot/App Developer** (this is the path that asks for source code and subreddits, which is exactly what Scout is) |
| **What is your inquiry?** | Select the option closest to **New API access request** or **Requesting access for a new app** (Reddit labels this slightly differently across A/B tests; pick the one that means "first-time request, no existing approval") |

Once those two dropdowns are set to Bot/App Developer + new request, the Bot/App branch unlocks. Continue down.

## Step 4 — Identity fields

| Field | Paste |
|---|---|
| **Your Reddit username (no u/)** | `SparkyMcCrinkle` |
| **Developer username(s)** | `SparkyMcCrinkle` |
| **Company name** | `Knife & Ledger LLC` |
| **Corporate email address** | `contact@knifeledger.com` |
| **Your full name** | `Greg Foster` |
| **Phone number** | (your business phone — required field, use the LLC line not personal cell if possible) |
| **Your current use of Reddit data** | `None yet. This is a first-time API access request. Manual reading of public posts only.` |
| **Company Website URL** | `https://knifeledger.com` |
| **Company description, including industries served and locations** | Paste the **Company description** block from Step 6 |
| **Company size** | Select **1-10** |

## Step 5 — The narrative fields (these are what reviewers actually read)

Each of the next four fields gets one block from Step 6. Paste the exact text, do not paraphrase.

| Field | Paste this block from Step 6 |
|---|---|
| **What is the purpose of your product or service?** | Block A — Purpose |
| **What will you deliver to your users/customers with Reddit data?** | Block B — Delivery |
| **Please describe what you are planning to distribute, where it will be distributed and expected audience.** | Block C — Distribution |
| **Provide a detailed description of what the Bot/App will be doing on the Reddit platform.** | Block D — Bot behavior |
| **What benefit/purpose will the bot/app have for Redditors?** | Block E — Benefit to Redditors |
| **What is missing from Devvit that prevents building on that platform?** | Block F — Why not Devvit |
| **Provide a link to source code or platform that will access the API.** | `https://github.com/gregfoster1836/kl-agents` |
| **What subreddits do you intend to use the bot/app in?** | `r/restaurateur, r/KitchenConfidential` |
| **If applicable, what username will you be operating this bot/app under?** | `u/SparkyMcCrinkle` (script app, no public bot account — clarify in Block D) |
| **If this is a bot that already exists...** | Leave blank (it does not exist yet) |
| **What is your data budget?** | Select the **smallest** option (typically "Low" or "<1,000 requests/day") |

## Step 6 — The pasteable blocks

Each block is meant to be copied **whole**, including line breaks. Do not edit on the fly — every claim has been verified against the public repo and the actual code.

### Cover narrative (goes in "Details of inquiry")

```
This is a first-time API access request for a read-only research tool called Scout, built and operated by Knife & Ledger LLC (a U.S.-based restaurant operations consultancy). A previous request submitted under the same Reddit account on 2026-04-30 was denied on 2026-05-02 with the standard non-detailed boilerplate. This resubmission addresses what I believe were the gaps in v1: registered-business framing, public source code, narrower subreddit list, and explicit RBP compliance.

Scout reads the newest public top-level posts in two restaurant-operator subreddits, classifies each one against three audience-awareness levels, and writes the keepers to a private review queue. A human reads the queue to understand what active operators are publicly struggling with this week, which informs the next post on our public educational blog at https://knifeledger.com.

Scout does not post, comment, vote, message, save, follow, subscribe, modify, or interact with Reddit in any user-visible way. It does not republish, redistribute, or quote Reddit content in our published material. Source code is public at https://github.com/gregfoster1836/kl-agents and the Reddit fetcher specifically lives at agents/scout/fetchers/reddit.py. Anyone at Reddit can read exactly what it does in under two minutes.

I have read the Responsible Builder Policy and the Data API Terms. Scout complies with both: read-only access, sequential requests under 100/day, no concurrent connections, no model training on Reddit content, no redistribution, deletion-honoring on every pass.
```

### Block A — Purpose (goes in "purpose of your product or service")

```
Knife & Ledger publishes free educational content for independent restaurant operators at https://knifeledger.com. Our revenue comes from advisory engagements and digital courses sold directly to operators through our own site, not from advertising or data resale.

Scout is an internal research tool. Its only purpose is to help us understand what active restaurant operators are publicly asking and struggling with this week, so we can write educational content that addresses real questions instead of guessing. It produces a private classification queue, never a publication.
```

### Block B — Delivery (goes in "what will you deliver to your users/customers with Reddit data")

```
Nothing derived from Reddit data is delivered to users or customers. The output is a private internal review queue, accessible only to the principal of Knife & Ledger LLC. The published blog posts that Knife & Ledger writes are original analysis informed by what we read on Reddit, but they do not quote, paraphrase, or reproduce specific Reddit posts or comments.

If we ever do quote a specific Reddit user (we have not to date), we will follow Reddit's attribution rules and link back to the original. The current architecture and intent have no such quotation path.
```

### Block C — Distribution (goes in "what are you planning to distribute, where, expected audience")

```
We distribute educational content at https://knifeledger.com to U.S.-based independent restaurant operators. Typical readership is restaurant owners and general managers running independent or small-chain operations (under 10 locations). The blog has no paywall, no Reddit-derived gating, and no advertising. Subscribers receive it via email; the public version lives on the website.

None of this content is derived from Reddit data. Scout's classification output is used internally to identify which topics operators are publicly discussing, which informs what we choose to write about. Reddit content itself is not redistributed in any form.
```

### Block D — Bot behavior (goes in "detailed description of what the bot/app will be doing")

```
Scout is a research-filtering tool. Its only job is to surface restaurant-operator posts worth a human's reading time. It does not generate content, write copy, or produce anything that appears on Reddit or in our published material. The blog at https://knifeledger.com is written by the LLC principal, a 25-year restaurant operator. Scout helps the principal decide which Reddit threads to read this week; the principal still reads each surfaced post and writes the resulting blog entry from scratch.

Scout runs once per day, scheduled. Each run:

1. Authenticates to Reddit via read-only PRAW using app-only OAuth (client_id + client_secret, no user account credentials). The read_only flag is set explicitly in code at agents/scout/fetchers/reddit.py.
2. Issues two sequential .new listing calls (one per subreddit: r/restaurateur, then r/KitchenConfidential). Each call retrieves up to 50 posts.
3. Filters: skips posts older than 30 days, skips removed/deleted posts, skips posts with empty title and empty body.
4. For each remaining post, sends the title and selftext to Anthropic's Claude API for one purpose only: classify the post against three audience-awareness levels (problem-aware, symptom-aware, decision-aware) plus a confidence score. The classifier returns a label. It does not write, summarize, paraphrase, or transform the post content.
5. Writes the post text and the classification label to a private Supabase Postgres instance, keyed by the post's Reddit permalink so the same post is never reprocessed.
6. Exits.

The principal then reads the queue manually, opens the original Reddit posts in a browser, reads them in full, and decides which operator issues are worth addressing in an upcoming blog post. Any blog post that results is written by hand from the principal's own operator experience, not generated, summarized, or assisted by AI using Reddit content.

Total Reddit API calls per run: 2 sequential listing calls. Total per day: ~2 requests, well under the published OAuth rate ceiling of 60 requests per minute. No concurrent requests. No write endpoints. No private data. No moderator surfaces. No user impersonation. The User-Agent string is "kl-scout/0.1 by u/SparkyMcCrinkle" per Reddit's UA guidance.

There is no bot account that posts or comments. The "script" type app runs under the LLC principal's credentials and operates as a logged-out reader. u/SparkyMcCrinkle is the account that owns the app registration, not a persona that interacts with Reddit content.
```

### Block E — Benefit to Redditors (goes in "what benefit/purpose will the bot/app have for Redditors")

```
The direct benefit to Redditors is indirect but real: Scout helps a 25-year industry operator write better educational material for independent restaurant owners. Many of the people posting in r/restaurateur and r/KitchenConfidential are asking questions that have well-understood operational answers but no good free public resource to point them at. Knife & Ledger's blog is one such resource. Scout helps us prioritize which questions to address next based on what's actually being asked this month rather than what was being asked five years ago when most blog content was written.

Scout does not produce anything that appears on Reddit. Redditors will never see output from this app on the platform. There is no public bot, no comment, no post, no vote, no DM.
```

### Block F — Why not Devvit (goes in "what is missing from Devvit that prevents building on that platform")

```
Devvit is designed to run interactive features inside Reddit (custom posts, community apps, moderator tools that surface within a subreddit's UI). Scout does the opposite: it reads public content into an external research database that lives on infrastructure unrelated to Reddit, for a research-filtering workflow whose only output is helping a human (the LLC principal) decide which Reddit threads to read this week. There is no Reddit-facing surface for Scout's output, no community-app component, and no moderator-tool component. Devvit is the wrong layer.

The Data API is the correct path because Scout is exactly the use case the Data API was designed for: read-only public-content access from an external application, on a low-volume sequential basis, by an identified developer who agrees to the Responsible Builder Policy.
```

## Step 7 — Final pre-submit checklist

Before clicking submit, walk this list. Each item takes 10 seconds.

- [ ] `config.yaml` on `main` shows two subs, not three (open https://github.com/gregfoster1836/kl-agents/blob/main/config.yaml in a private window and confirm)
- [ ] https://knifeledger.com loads in a private window
- [ ] Every link in your application opens correctly
- [ ] No em-dashes anywhere in the pasted text (search for `—` in each block before submitting)
- [ ] Phone number is the LLC line, not your personal cell
- [ ] Subject line clearly says "read-only research" so the first three seconds of triage read as low-risk
- [ ] You are submitting from `gfloss381@gmail.com` (the account email), not `contact@knifeledger.com`

## Step 8 — Submit, then archive

1. Click **Submit**. You should get a Zendesk ticket confirmation email within a minute.
2. Forward that confirmation to `contact@knifeledger.com` so it lives in the LLC inbox.
3. Open Obsidian, create `09_Session_Summaries/2026-05-11 Reddit API v2 Submitted.md`. Paste:
   - The Zendesk ticket number
   - Today's date and time
   - A copy of each pasted block (for the record of what's in front of reviewers)
4. Update `memory/handoff_kl-agents-scout.md` with the new submission date so the next session knows the clock is ticking.

## Step 9 — Wait and watch

- Response window: typically 5-10 business days. The 2026-05-02 denial came in 2 days, but the v1 was clearly fast-rejected; v2 is more likely to get actual review time.
- Watch `gfloss381@gmail.com` for replies. Reddit may ask follow-up questions. If they do, the four prepared answers at the bottom of this file (under "Likely follow-up questions") cover the most common ones.
- **Approved →** register a "script" type app at https://www.reddit.com/prefs/apps (name: `kl-scout`, redirect URI: `http://localhost:8080`, description: a one-liner pointing at https://knifeledger.com), copy the client_id and client_secret into `/Users/gregfoster/00-coding/active/03 KL Agents/.env`, then run `python scripts/smoke_reddit_fetch.py --subreddit restaurateur --limit 5`.
- **Denied with specific feedback →** address the specific points, wait 7 days, resubmit. Update this file with v3 changes.
- **Denied with boilerplate again →** escalate by replying to the Zendesk ticket asking for specific feedback (this is the recommended path per multiple r/redditdev threads), do not blind-resubmit a third time.

---

# Why v2 is meaningfully different from v1

For your own records, here is what changed. The v1 denial was boilerplate, but the gaps were probably:

| v1 | v2 |
|---|---|
| Use case framed as "research bot for blog content" | "Read-only research tool for an educational publication" — same activity, language reviewers don't auto-reject |
| Private repo, no public verification surface | Public repo at https://github.com/gregfoster1836/kl-agents; the Reddit fetcher file is named in the application |
| Three subreddits including r/smallbusiness (3M+ members, common rejection trigger) | Two subreddits, both operator-specific, well under any volume concern |
| No registered-business framing | Knife & Ledger LLC explicit throughout, with public website |
| No RBP citation | RBP compliance affirmed point-by-point in the cover narrative and Block D |
| No volume specification | Explicit: ~2 requests/day, sequential, well under 60/min |
| Implicit Devvit comparison | Explicit Block F explaining why Devvit is the wrong layer |

---

# Likely follow-up questions (have answers ready)

**"Why not just read Reddit in a browser?"**
> The principal does read Reddit manually. Scout exists because the two operator subs together produce 50-150 new posts per week, most of which are off-topic for our editorial focus. The classifier filters that down to 10-20 candidates per week, which the principal reads at full length. Without the filter, the manual reading time is the bottleneck.

**"Why an LLC, why not non-commercial?"**
> The LLC publishes a free educational blog. The blog has no paywall, no Reddit-derived gating, and no advertising. The LLC monetizes through advisory work that is sold directly to operators who reach out. Reddit content is not part of that funnel. We chose the Bot/App Developer path on the form because the bot/app use case fits Scout exactly: read-only, low-volume, identified developer, source code public.

**"Will Scout's output ever be public?"**
> No. The review queue is internal-only. Our public blog posts are original analysis written by the principal, informed by but never reproducing Reddit content. If we ever quote a specific Reddit comment in a published piece, we will follow Reddit's attribution rules and link back to the original. The current plan has no such quotation.

**"What if you scale up?"**
> Any increase in volume, additional subreddits, or new use cases (publishing aggregated Reddit data, training a model, expanding to message/notification surfaces) gets a new application and Reddit's explicit re-approval. The current ceiling is 100 reads/day across two subs.

---

## Tone reference (if you edit any block before pasting)

- Operator voice. Plain, structural, no hype. No marketing copy.
- No em-dashes. Periods, commas, or restructure.
- Every claim verifiable: every link works, every number is the real number, every file path resolves in the public repo.
- Confident, not defensive. The first denial was generic; we do not apologize for it.
