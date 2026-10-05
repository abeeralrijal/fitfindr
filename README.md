# FitFindr

FitFindr is an agent that finds secondhand clothing listings matching a natural language request, styles the best match against the user's existing wardrobe, and writes a shareable caption for the result.

## Demo Video

[Watch the demo](https://drive.google.com/drive/folders/1HWcEVxlf6kyu8nLDotarixgqSmPGoE_B?usp=sharing)

## What's Included

```
fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tests/
│   └── test_tools.py          # pytest coverage for all three tools
├── tools.py                   # The three tools
├── agent.py                   # Planning loop + session state
├── app.py                     # Gradio interface
├── planning.md                # Spec, diagram, and design decisions
└── requirements.txt           # Python dependencies
```

Run the app with `python app.py`, the agent's CLI test cases with `python agent.py`, and the test suite with `python -m pytest tests/`.

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

### 1. `search_listings(description, size=None, max_price=None) -> list[dict]`

**Purpose:** Find secondhand listings matching what the user asked for. This is the only tool that touches the dataset, and it's what every later step depends on.

| Parameter | Type | Meaning |
|---|---|---|
| `description` | `str` | Free-text keywords, e.g. `"vintage graphic tee"`. Each listing is scored by how many of these words appear in its title, description, or style tags. |
| `size` | `str \| None` | Size filter, matched case-insensitively as a substring so `"M"` matches `"S/M"`. `None` skips the filter. |
| `max_price` | `float \| None` | Inclusive price ceiling. `None` skips the filter. |

**Returns:** A list of listing dicts sorted by keyword score, highest first, or `[]` if nothing matches. Each dict has `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), and `platform` (str). Listings scoring zero are dropped rather than returned as weak matches.

### 2. `suggest_outfit(new_item, wardrobe) -> str`

**Purpose:** Turn a listing into an actual outfit by pairing it with clothes the user already owns. This is what makes the result useful rather than just a search hit.

| Parameter | Type | Meaning |
|---|---|---|
| `new_item` | `dict` | A listing dict, in the exact format `search_listings` returns. |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key holding wardrobe item dicts (`id`, `name`, `category`, `colors`, `style_tags`, `notes`). The list may be empty. |

**Returns:** A non-empty string describing one or two outfits. With a populated wardrobe it names specific owned pieces; with an empty wardrobe it describes what kinds of pieces would pair well instead. Calls the LLM.

### 3. `create_fit_card(outfit, new_item) -> str`

**Purpose:** Compress the find and the outfit into a short caption the user could actually post, which is the deliverable the whole pipeline builds toward.

| Parameter | Type | Meaning |
|---|---|---|
| `outfit` | `str` | The outfit string returned by `suggest_outfit()`. |
| `new_item` | `dict` | The listing dict, used for the item's title, price, and platform. |

**Returns:** A 2–4 sentence caption mentioning the item name, price, and platform once each. Generated at `temperature=1.0` so repeated calls on identical input read differently. Calls the LLM.

---

## Planning Loop

`run_agent(query, wardrobe)` in `agent.py` runs a fixed three-stage pipeline with two early exits. It is not making an open-ended choice at each step; it is checking whether the previous tool returned enough to justify the next call.

1. **Initialize** a session dict via `_new_session(query, wardrobe)`.
2. **Parse** the query with `_parse_query()`, a regex parser that extracts `description`, `size`, and `max_price`. I used regex rather than an LLM call because the query shapes are predictable (a price after "under $", an optional "size X" token), so parsing stays deterministic and testable without burning an API call. Result goes in `session["parsed"]`.
3. **Search** by calling `search_listings(**session["parsed"])`.
   - If the result is empty, set `session["error"]` and return immediately. Neither LLM tool is called.
   - Otherwise set `session["selected_item"] = search_results[0]` and continue.
4. **Suggest** by calling `suggest_outfit(selected_item, wardrobe)`.
   - If the result is empty or whitespace, set `session["error"]` and return, skipping the fit card. This is a safety net, since `suggest_outfit` is specified to always return something.
   - Otherwise continue.
5. **Create** the fit card via `create_fit_card(outfit_suggestion, selected_item)`.
6. **Return** the session. Callers check `session["error"]` first; if it is `None`, `session["fit_card"]` holds the result.

The loop makes at most one pass and never retries or loops back.

---

## State Management

All state for a single interaction lives in one plain dict created by `_new_session()`. There is no global state and no database. Each tool is a pure function taking plain arguments, and the loop is solely responsible for reading fields out of the session, passing them in, and writing results back.

| Field | Written by | Read by |
|---|---|---|
| `query` | `_new_session` | kept for reference/debugging |
| `parsed` | step 2 | unpacked into `search_listings` |
| `search_results` | step 3 | checked for emptiness; source of `selected_item` |
| `selected_item` | step 3 | passed to **both** `suggest_outfit` and `create_fit_card` |
| `wardrobe` | `_new_session` | passed to `suggest_outfit` |
| `outfit_suggestion` | step 4 | passed to `create_fit_card` |
| `fit_card` | step 5 | final output |
| `error` | either early exit | checked first by any caller |

State flows strictly forward: each tool reads only fields an earlier step wrote, and writes only its own. I verified this holds by identity rather than assuming it — wrapping both LLM tools to capture their actual arguments showed `session["selected_item"] is captured_new_item` was `True` for both calls, and `session["outfit_suggestion"] is captured_outfit` was `True`. Nothing is copied, re-derived, or re-prompted between steps.

---

## Interaction Walkthrough

Everything below is verbatim output from an actual run, not a mock-up.

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 0 — Parse (no tool).** `_parse_query()` reduces the query to `{'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}`. It takes only the first sentence, strips the "I'm looking for a" lead-in, and pulls `30.0` out of "under $30". The wardrobe context in the second sentence is ignored here because the wardrobe arrives as its own argument.

**Step 1 — Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee", size=None, max_price=30.0`
- Why this tool: nothing else can run until there's a concrete item to style, and this is the only tool that reads the dataset.
- Output: 20 listings. Top three by score: `lst_002`, `lst_006`, `lst_033`. Selected: `lst_002`, "Y2K Baby Tee — Butterfly Print," $18.0, depop. All three tie on keyword score (each hits "vintage", "graphic", and "tee"), so the stable sort falls back to dataset order and `lst_002` wins.

**Step 2 — Tool called:**
- Tool: `suggest_outfit`
- Input: `new_item=<lst_002 dict>, wardrobe=<example wardrobe, 10 items>`
- Why this tool: a listing on its own doesn't answer "how would I style it?" — this is the step that connects the find to clothes the user already owns.
- Output: *"**Outfit 1 – Y2K Vibe:** Slip the **Y2K Baby Tee (pink‑purple butterfly)** under the **Vintage black denim jacket**, pair with the **Baggy straight‑leg jeans (dark wash)**, and finish with the **Chunky white sneakers**. Add the **Brown leather belt** for a subtle contrast and toss the **Black crossbody bag** over your shoulder for a low‑key, street‑ready look. **Outfit 2 – Cottagecore Twist:** Tuck the **Y2K Baby Tee (white‑pink butterfly)** into the **Wide‑leg khaki trousers**, layer the **Oversized grey crewneck sweatshirt** on top, and step out in the **Black combat boots** for an edgy‑meets‑pastel vibe..."*

Note it picked out `w_001` (baggy jeans) and `w_007` (chunky sneakers), the exact two pieces the user mentioned owning.

**Step 3 — Tool called:**
- Tool: `create_fit_card`
- Input: `outfit=<the string from step 2>, new_item=<lst_002 dict>`
- Why this tool: the outfit text is long and reads like advice. The fit card compresses it into something postable, which is the actual deliverable.
- Output: see below.

**Final output to user:**

> Just copped this Y2K Baby Tee — Butterfly Print for $18 on Depop and it's already my go-to vibe. I slipped it under a vintage black denim jacket, paired it with baggy straight-leg jeans and chunky white sneakers, then added a brown belt and my trusty black crossbody for that low-key street-ready feel. #thriftfind #Y2Kfashion #outfitoftheday

In the Gradio UI this lands in panel 3, with the formatted listing in panel 1 and the full outfit text in panel 2.

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | Filters exclude everything, or nothing scores above zero on keyword overlap | Returns `[]` rather than raising. The loop detects the empty list, writes a message to `session["error"]` naming both what was searched and three concrete fixes, and returns immediately. `selected_item`, `outfit_suggestion`, and `fit_card` stay `None`, and neither LLM tool is called. |
| `suggest_outfit` | `wardrobe["items"]` is empty (new user with nothing on file) | Not treated as an error. The tool branches before building a prompt and asks the LLM for general styling advice about the item alone, returning a non-empty string either way. The pipeline continues normally and the user still gets a fit card. |
| `create_fit_card` | `outfit` is empty, whitespace-only, or `None` | Returns a descriptive string instead of raising or returning `""`. The guard runs before the Groq client is constructed, so no API call is wasted on input that could never produce a caption. |

**Concrete examples from testing:**

*`search_listings` no-results.* Running `search_listings('designer ballgown', size='XXS', max_price=5)` returns `[]` with no exception. Through the full agent, the user sees:

> No listings matched 'designer ballgown' under $5. Try raising your price limit, dropping the size filter, or using a broader description.

This echoes the parsed query back (so the user can spot a misparse, which is usually the real problem) and names one fix per filter that could have excluded everything. I confirmed the short-circuit is real, not just unused output, by monkeypatching both LLM tools to raise on invocation: they were called **zero** times.

*`suggest_outfit` empty wardrobe.* With `get_empty_wardrobe()`, the tool returned: *"Pair the pastel-hued butterfly tee with high-waisted mom jeans or a flowy midi skirt in a soft lilac or ivory for that dreamy Y2K-cottagecore vibe, then toss on a lightweight denim or corduroy jacket..."* — advice about what to look for rather than pieces the user doesn't own. `session["error"]` stayed `None` and a fit card was still produced.

*`create_fit_card` empty outfit.* All three of `""`, `"   "`, and `None` return:

> Can't create a fit card — no outfit suggestion was generated for this item.

I re-ran this with `GROQ_API_KEY` blanked out and got the same string rather than the `ValueError` that `_get_groq_client()` would raise, proving the guard fires before any network call.

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing out the two early-exit branches before touching `agent.py` meant the planning loop was essentially transcription rather than design work. More usefully, having committed in the spec to "`search_listings` returns `[]`, it never raises" forced a decision I would otherwise have made twice and inconsistently: the tool stays dumb and returns an empty list, and the *loop* owns turning that into a user-facing message. That split is why the error message can mention the parsed description and price — the loop has `session["parsed"]` in hand, which the tool never sees. Had I written the code first, I'd probably have buried a "no results" string inside `search_listings` and then had no clean way to get the query context into it.

**One divergence from your spec, and why:**

The project spec called for Groq's `meta-llama/llama-4-scout-17b-16e-instruct` for both LLM tools, but Groq deprecated that model in June 2026 and my API key returns a 404 for it, along with every other Llama model. Groq's own migration guidance points to `openai/gpt-oss-120b` or `qwen/qwen3.6-27b` as replacements, so I went with `openai/gpt-oss-120b`, which the key can reach and which handled both the outfit prompts and the higher-temperature caption prompts without any change to my tool specs. Nothing about the tool interfaces changed as a result: `suggest_outfit` and `create_fit_card` still take the same arguments and return the same string types described in planning.md, since the model id is isolated to a single `_MODEL` constant in `tools.py`.

---

## AI Usage

I used Claude (via Claude Code) for all four implementation milestones, feeding it one spec section at a time rather than the whole document at once.

**1. `search_listings` — I overrode the doc, not the code.**

*Input:* the Tool 1 block from `planning.md` (the three parameters with types, the full list of listing dict fields, and the "returns `[]`, never raises" failure mode) plus the `load_listings()` docstring from `utils/data_loader.py`, with an instruction not to re-implement file loading.

*Produced:* a filter-then-score implementation — price and size filters first, then a set-intersection keyword score against title, description, and style tags, dropping zero-score listings and sorting descending.

*What I changed:* the code was correct, but testing it against my own spec surfaced a mismatch in the other direction. My `planning.md` walkthrough claimed the top result for "vintage graphic tee under $30" would be `lst_006` ("Graphic Tee — 2003 Tour Bootleg Style"); the code returned `lst_002` ("Y2K Baby Tee"). Both genuinely tie at three keyword matches, and Python's stable sort breaks the tie by dataset order. I could have added title-weighting to force my predicted answer, but the tie is legitimate — so I corrected the walkthrough to match the code and documented the tie-break behavior explicitly, rather than bending the ranking to make my prediction look right.

**2. Planning loop — generated from the diagram, then verified adversarially.**

*Input:* the full Mermaid diagram from the Architecture section, plus the complete Planning Loop and State Management sections, plus the `_new_session()` dict from `agent.py`.

*Produced:* `run_agent()` with both early-exit branches and session writes at each stage, matching the diagram's nodes.

*What I changed:* I didn't accept "the code looks like it branches" as evidence. Reading the code only tells you the early `return` exists; it doesn't prove the LLM tools are unreachable on that path. So I monkeypatched `suggest_outfit` and `create_fit_card` to raise `AssertionError` on any invocation and re-ran the no-results query — both were called zero times. I applied the same standard to state flow, wrapping both tools to capture their real arguments and asserting `session["selected_item"] is captured_new_item` rather than `==`, which rules out a copy being passed. I also added `_parse_query()`, which the diagram doesn't show as its own node but which both spec sections require.

**3. Model selection — I rejected the AI's first two answers.**

*Input:* the Tool 2 and Tool 3 spec blocks, with the project requirement to use Groq's `meta-llama/llama-4-scout-17b-16e-instruct`.

*Produced:* working tool implementations, but with `llama-3.1-8b-instant` filled in as the model — a plausible-looking id that 404'd immediately, as did the required Scout model.

*What I changed:* rather than accepting the next suggested substitute, I queried `client.models.list()` to get the authoritative list for my key, then checked Groq's deprecation notice, which retires Scout as of June 2026 and names `openai/gpt-oss-120b` as the migration target. I went with that, and isolated it to a single `_MODEL` constant so the swap touches one line if it's deprecated too. This is the one place my implementation knowingly departs from the project spec.

---

## Running and Testing

```bash
python app.py                 # Gradio UI (includes a deliberate no-results example query)
python agent.py               # CLI: happy path + no-results path
python -m pytest tests/       # 9 tests covering all three tools and their failure modes
```

Use `python -m pytest`, not bare `pytest` — the `-m` form puts the repo root on the import path so `from tools import ...` resolves.
