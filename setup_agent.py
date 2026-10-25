"""Create or update the Metaview Pipeline Coach on ElevenLabs and attach a Twilio number.

Usage
  export ELEVENLABS_API_KEY=...
  python caller/setup_agent.py                 # create the agent and upload the knowledge base
  python caller/setup_agent.py --update        # re-upload briefs and update the existing agent
  # optional phone step (inbound calls):
  export TWILIO_ACCOUNT_SID=AC... TWILIO_AUTH_TOKEN=... TWILIO_NUMBER=+44...
  python caller/setup_agent.py --phone

State (agent id, document ids) is kept in caller/agent_state.json.
"""
import json, os, sys, time
import requests

API = "https://api.elevenlabs.io/v1/convai"
HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "kb")
STATE = os.path.join(HERE, "agent_state.json")
KEY = os.environ.get("ELEVENLABS_API_KEY")
if not KEY:
    sys.exit("Set ELEVENLABS_API_KEY first.")
H = {"xi-api-key": KEY}

LLM = os.environ.get("COACH_LLM", "claude-sonnet-4-5")
VOICE = os.environ.get("COACH_VOICE_ID")  # leave unset to use the ElevenLabs default voice

FIRST_MESSAGE = ("Hi, this is the Metaview pipeline check-in. Three minutes before the review. "
                 "Who am I speaking with?")

# One column per field. These become the columns of the VP prep sheet (vp_sheet.py).
# Seven columns. These are the columns of the VP prep sheet (vp_sheet.py).
DATA_COLLECTION = {
    "rep_name": {"type": "string", "description": "Full name of the rep who called."},
    "what_changed": {"type": "string", "description": "What the rep said has changed in their pipeline since last week, in two or three lines. Include anything closed won or lost."},
    "month_number": {"type": "number", "description": "Dollar amount the rep said they will close this month. Empty if not given."},
    "month_commit": {"type": "number", "description": "Dollar amount of that they called committed. Empty if not given."},
    "flagged_deals": {"type": "string", "description": "For each flagged top-20 deal asked about: 'amount | next step | date or no date'. Separate deals with ' ; '. Empty if none."},
    "salesforce_fixes": {"type": "string", "description": "Anything the rep said is wrong in Salesforce (stage, close date, amount) or wrong in the data. Empty if none."},
    "help_needed": {"type": "string", "description": "What the rep asked Mark or leadership for, and on which deal. Empty if none."},
}

EVALUATION = [
    {"id": "no_invented_numbers", "name": "No invented numbers",
     "conversation_goal_prompt": "The agent only stated figures, dates and facts that appear in the knowledge base. Fail if it gave any number that is not in the briefs.",
     "use_knowledge_base": True},
    {"id": "dated_next_steps", "name": "Dated next steps captured",
     "conversation_goal_prompt": "For each deal discussed, the agent asked for and recorded a next step with a date."},
    {"id": "read_back", "name": "Commitments read back",
     "conversation_goal_prompt": "Before ending, the agent read back the rep's commitments and asked them to confirm."},
]


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def check(r):
    if r.status_code >= 300:
        sys.exit(f"{r.request.method} {r.url} -> {r.status_code}: {r.text[:500]}")
    return r.json() if r.text else {}


def upload_briefs(state):
    # Remove documents from an earlier run so the agent never reads stale briefs.
    for doc in state.get("docs", []):
        requests.delete(f"{API}/knowledge-base/{doc['id']}", headers=H, params={"force": "true"})
    docs = []
    index = json.load(open(os.path.join(KB, "rep_index.json")))
    for rep, fn in sorted(index.items()):
        with open(os.path.join(KB, fn), "rb") as f:
            j = check(requests.post(f"{API}/knowledge-base/file", headers=H,
                                    files={"file": (fn, f, "text/markdown")}, data={"name": f"Rep brief: {rep}"}))
        docs.append({"type": "file", "name": f"Rep brief: {rep}", "id": j["id"], "usage_mode": "auto"})
        print("uploaded", rep)
    with open(os.path.join(KB, "01_manager_guidance.md"), "rb") as f:
        j = check(requests.post(f"{API}/knowledge-base/file", headers=H,
                                files={"file": ("01_manager_guidance.md", f, "text/markdown")}, data={"name": "Manager guidance"}))
    docs.append({"type": "file", "name": "Manager guidance", "id": j["id"], "usage_mode": "auto"})
    for d in docs:
        check(requests.post(f"{API}/knowledge-base/{d['id']}/rag-index", headers=H, json={"model": "e5_mistral_7b_instruct"}))
    # Wait for indexing
    for _ in range(60):
        statuses = [check(requests.post(f"{API}/knowledge-base/{d['id']}/rag-index", headers=H,
                                        json={"model": "e5_mistral_7b_instruct"})).get("status") for d in docs]
        bad = [s for s in statuses if s in ("failed", "rag_limit_exceeded")]
        if bad:
            sys.exit(f"RAG indexing failed: {bad}")
        if all(s == "succeeded" for s in statuses):
            break
        print("indexing...", sum(s == "succeeded" for s in statuses), "of", len(docs))
        time.sleep(5)
    state["docs"] = docs
    return docs


def agent_body(docs):
    team = open(os.path.join(KB, "00_team_brief.md")).read()
    prompt = open(os.path.join(HERE, "agent_prompt.md")).read().replace("{{TEAM_BRIEF}}", team)
    tts = {"model_id": "eleven_flash_v2_5"}
    if VOICE:
        tts["voice_id"] = VOICE
    return {
        "name": "Metaview Pipeline Check-in",
        "conversation_config": {
            "agent": {
                "first_message": FIRST_MESSAGE,
                "language": "en",
                "prompt": {
                    "prompt": prompt,
                    "llm": LLM,
                    "temperature": 0.2,
                    "knowledge_base": docs,
                    "rag": {"enabled": True, "embedding_model": "e5_mistral_7b_instruct",
                            "max_retrieved_rag_chunks_count": 20, "max_documents_length": 50000},
                },
            },
            "tts": tts,
            "conversation": {"max_duration_seconds": 240},
        },
        "platform_settings": {
            "data_collection": DATA_COLLECTION,
            "evaluation": {"criteria": EVALUATION},
        },
    }


def main():
    state = load_state()
    if "--phone" in sys.argv:
        return attach_phone(state)
    docs = upload_briefs(state)
    body = agent_body(docs)
    if "--update" in sys.argv and state.get("agent_id"):
        check(requests.patch(f"{API}/agents/{state['agent_id']}", headers=H, json=body))
        print("updated agent", state["agent_id"])
    else:
        j = check(requests.post(f"{API}/agents/create", headers=H, json=body))
        state["agent_id"] = j["agent_id"]
        print("created agent", state["agent_id"])
    save_state(state)
    print("Talk to it in the browser: https://elevenlabs.io/app/talk-to?agent_id=" + state["agent_id"])


def attach_phone(state):
    if not state.get("agent_id"):
        sys.exit("Create the agent first.")
    num = os.environ["TWILIO_NUMBER"]
    existing = check(requests.get(f"{API}/phone-numbers", headers=H))
    existing = existing if isinstance(existing, list) else existing.get("phone_numbers", [])
    match = [p for p in existing if p.get("phone_number") == num]
    if match:
        pid = match[0]["phone_number_id"]
        old = (match[0].get("assigned_agent") or {}).get("agent_name")
        if old and "--force" not in sys.argv:
            sys.exit(f"{num} is already assigned to '{old}'. Re-run with --force to move it to the coach.")
        check(requests.patch(f"{API}/phone-numbers/{pid}", headers=H, json={"agent_id": state["agent_id"]}))
    else:
        j = check(requests.post(f"{API}/phone-numbers", headers=H, json={
            "provider": "twilio", "phone_number": num, "label": "Metaview Pipeline Check-in",
            "sid": os.environ["TWILIO_ACCOUNT_SID"], "token": os.environ["TWILIO_AUTH_TOKEN"],
            "agent_id": state["agent_id"]}))
        pid = j["phone_number_id"]
    state["phone_number_id"] = pid
    state["phone_number"] = num
    save_state(state)
    print(f"Inbound calls to {num} now reach the Pipeline Coach.")


if __name__ == "__main__":
    main()
