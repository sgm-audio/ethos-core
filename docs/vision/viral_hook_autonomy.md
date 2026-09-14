# Project Constitution: Viral Hook Autonomy
## 1. Mission
To automate the ingestion, translation, and distribution of high-leverage content hooks using Google Antigravity's agentic nodes. The system must scrape raw viral formats, "Scott-ify" them (injecting deep technical authority), and queue them for review without human intervention.

## 2. Data Schema (The "Payload")
**Input (Raw Signal):**
- Source: `content_hooks` (Supabase Table) or Manual Text Input
- Fields: `raw_template`, `category` (Educational/Contrarian), `status_level`

**Transformation (The "Scott-ify" Agent):**
- Logic: Agent must reject "fluff" and enforce "Systems Architect" tone.
- Formatting: Markdown with specific H1/H2 hierarchy for readability.

**Output (The Asset):**
- Destination: Notion ("Ideas OS" Database) or Slack (Private Channel)
- Structure:
  {
    "hook_id": "UUID",
    "variations": ["Script A", "Script B", "Script C"],
    "sex_appeal_score": 1-10,
    "technical_depth": "High"
  }

## 3. Architecture Constraints (A.N.T. Layers)
- **Agent Layer:** Use `google-vertex-agent` for the cognitive translation.
- **Node Layer:** Python scripts in `/tools` must be stateless.
- **Trigger:** Time-based (Daily @ 0800) or Event-based (New row in Supabase).

## 4. Behavioral Rules
1. **Zero Hallucination:** If the agent cannot find a specific "Librosa" or "Python" metaphor, it must query the `User Summary` vector store before generating generic advice.
2. **High Status:** Content must never sound pleading ("Please like this"). It must sound declarative ("Here is the protocol").